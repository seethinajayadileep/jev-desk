"""One-page server for local use and Railway.

Railway injects PORT and reaches the process over the public network, so the
default listen address is 0.0.0.0. SIGTERM stops the process during deploys.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import signal
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from typesafe_sdk import TypeSafeClient, TypeSafeError

from jev_desk.page import DeskRow, Page, render_page
from jev_desk.questions import TEAM_CRITERIA, URGENCY_CRITERIA
from jev_desk.routing import Thresholds
from jev_desk.samples import sample_for
from jev_desk.triage import present, sort_message
from jev_desk.uploads import (
    Submission,
    UploadError,
    display_name,
    messages_in,
    parse_submission,
)

logger = logging.getLogger("jev_desk")

MAX_CHARS = 8000
MAX_BODY = (2 * 1024 * 1024) + (64 * 1024)
REQUEST_TIMEOUT = 30
DEFAULT_SORTS_PER_MINUTE = 30

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "Cache-Control": "no-store",
}


def api_key_present() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


def bind_address() -> tuple[str, int]:
    host = os.environ.get("HOST", "0.0.0.0").strip() or "0.0.0.0"
    raw = os.environ.get("PORT", "8000").strip() or "8000"
    try:
        port = int(raw)
    except ValueError:
        raise SystemExit(f"PORT must be an integer, got {raw!r}") from None
    if port < 1 or port > 65535:
        raise SystemExit(f"PORT must be from 1 to 65535, got {port}")
    return host, port


def sorts_per_minute() -> int:
    raw = os.environ.get("JEV_DESK_SORTS_PER_MINUTE", str(DEFAULT_SORTS_PER_MINUTE)).strip()
    if not raw:
        return DEFAULT_SORTS_PER_MINUTE
    try:
        limit = int(raw)
    except ValueError:
        raise SystemExit(f"JEV_DESK_SORTS_PER_MINUTE must be an integer, got {raw!r}") from None
    if limit < 0:
        raise SystemExit("JEV_DESK_SORTS_PER_MINUTE must be 0 or greater")
    return limit


class RateLimited(Exception):
    """The desk built the page, and the handler should answer 429."""

    def __init__(self, page: str) -> None:
        self.page = page


class RateLimiter:
    """Fixed window of accepted sorts per client. A limit of 0 turns it off."""

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < self.window]
            if len(recent) >= self.limit:
                self._hits[key] = recent
                return False
            recent.append(now)
            self._hits[key] = recent
            return True


class Desk:
    def __init__(
        self,
        *,
        live: bool | None = None,
        client: Any | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.live = api_key_present() if live is None else live
        self._client = client
        self._owns_client = False
        self.limiter = limiter if limiter is not None else RateLimiter(sorts_per_minute())

    def client(self) -> Any:
        if self._client is None:
            self._client = TypeSafeClient(model="jev-latest")
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
            self._owns_client = False

    def health(self) -> str:
        mode = "live" if self.live else "sample"
        return json.dumps({"status": "ok", "mode": mode})

    def page_for(
        self,
        message: str | None,
        *,
        source: str | None = None,
        client_key: str = "",
    ) -> str:
        def show(draft: str, result: Any, notice: str | None) -> str:
            return render_page(
                Page(live=self.live, draft=draft, result=result, notice=notice, source=source)
            )

        if message is None:
            return show("", None, None)
        text = message.strip()
        if not text:
            return show("", None, "Paste a customer message or upload a file.")
        if len(text) > MAX_CHARS:
            return show(text[:MAX_CHARS], None, "That message is too long to sort.")
        self._take_slot(client_key, show(text[:MAX_CHARS], None, "Too many messages. Wait a minute and try again."))
        if not self.live:
            sample = sample_for(text)
            if sample is None:
                return show(
                    text,
                    None,
                    "Live Jev is off, so this message was not sent. Choose a built-in sample.",
                )
            logger.info("sample mode; no system_one call")
            return show(text, sample, None)
        try:
            result = sort_message(text, self.client())
        except TypeSafeError as exc:
            logger.warning("system_one failed: %s", exc.__class__.__name__)
            return show(text, None, f"Jev did not answer. {public_error(exc)}")
        return show(text, result, None)

    def page_for_submission(self, submission: Submission, *, client_key: str = "") -> str:
        message = submission.message
        source = None
        if submission.data is not None:
            source = display_name(submission.filename or "upload")
            if not submission.data:
                return render_page(
                    Page(
                        live=self.live,
                        draft=message.strip()[:MAX_CHARS],
                        result=None,
                        notice="That file is empty.",
                        source=source,
                    )
                )
            try:
                texts = messages_in(submission.filename or "", submission.data)
            except UploadError as exc:
                return render_page(
                    Page(
                        live=self.live,
                        draft=message.strip()[:MAX_CHARS],
                        result=None,
                        notice=str(exc),
                        source=source,
                    )
                )
            logger.info("upload name=%s bytes=%d messages=%d", source, len(submission.data), len(texts))
            if len(texts) > 1:
                return self.page_for_many(texts, source=source, client_key=client_key)
            message = texts[0]
        return self.page_for(message, source=source, client_key=client_key)

    def page_for_many(self, messages: list[str], *, source: str | None, client_key: str) -> str:
        rows: list[DeskRow] = []
        for index, message in enumerate(messages):
            text = message.strip()
            if not text:
                continue
            if len(text) > MAX_CHARS:
                rows.append(DeskRow(result=None, notice="That message is too long to sort."))
                continue
            try:
                self._take_slot(
                    client_key,
                    render_page(
                        Page(
                            live=self.live,
                            draft=text[:MAX_CHARS],
                            result=None,
                            notice="Too many messages. Wait a minute and try again.",
                            source=source,
                            rows=tuple(rows),
                        )
                    ),
                )
            except RateLimited as limited:
                if not rows:
                    raise limited
                rows.append(DeskRow(result=None, notice="Too many messages. Wait a minute and try again."))
                break
            rows.append(self._one_row(text))
        return render_page(Page(live=self.live, draft="", result=None, notice=None, source=source, rows=tuple(rows)))

    def page_for_replay(self, fields: dict[str, str]) -> str:
        try:
            result = present(
                _replay_message(fields),
                _replay_team(fields),
                _replay_urgency(fields),
                _replay_refund(fields),
                model=_replay_model(fields, live=self.live),
                live=self.live and fields.get("live") == "1",
                thresholds=_replay_thresholds(fields),
            )
        except (KeyError, ValueError):
            return render_page(
                Page(
                    live=self.live,
                    draft="",
                    result=None,
                    notice="Those rules could not be applied.",
                )
            )
        return render_page(Page(live=self.live, draft=result.message, result=result, notice=None))

    def _one_row(self, text: str) -> DeskRow:
        if not self.live:
            sample = sample_for(text)
            if sample is None:
                return DeskRow(
                    result=None,
                    notice="Live Jev is off, so this message was not sent. Choose a built-in sample.",
                )
            logger.info("sample mode; no system_one call")
            return DeskRow(result=sample)
        try:
            return DeskRow(result=sort_message(text, self.client()))
        except TypeSafeError as exc:
            logger.warning("system_one failed: %s", exc.__class__.__name__)
            return DeskRow(result=None, notice=f"Jev did not answer. {public_error(exc)}")

    def _take_slot(self, client_key: str, page: str) -> None:
        if not self.limiter.allow(client_key or "local"):
            raise RateLimited(page)


def public_error(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        text = text.replace(key, "[redacted]")
    return text[:400]


def client_key(headers: Any, address: str) -> str:
    forwarded = headers.get("X-Forwarded-For", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return address


class DeskServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def handler_for(desk: Desk) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        _head_only = False

        def setup(self) -> None:
            super().setup()
            self.request.settimeout(REQUEST_TIMEOUT)

        def do_GET(self) -> None:  # noqa: N802
            self._head_only = False
            self._guard(self._get)

        def do_HEAD(self) -> None:  # noqa: N802
            self._head_only = True
            self._guard(self._get)

        def do_POST(self) -> None:  # noqa: N802
            self._head_only = False
            self._guard(self._post)

        def _guard(self, handle: Any) -> None:
            try:
                handle()
            except Exception:
                logger.exception("request failed")
                if not self.wfile.closed:
                    try:
                        self._send(500, "Something went wrong.", "text/plain; charset=utf-8")
                    except Exception:
                        logger.exception("could not send the error response")

        def _get(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                self._send(200, desk.health(), "application/json")
                return
            if path != "/":
                self._send(404, "Not found", "text/plain; charset=utf-8")
                return
            self._send(200, desk.page_for(None), "text/html; charset=utf-8")

        def _post(self) -> None:
            if urlparse(self.path).path != "/":
                self._send(404, "Not found", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                self._send(400, "Bad request", "text/plain; charset=utf-8")
                return
            if length < 0:
                self._send(400, "Bad request", "text/plain; charset=utf-8")
                return
            if length > MAX_BODY:
                self._send(413, "That upload is too large.", "text/plain; charset=utf-8")
                return
            raw = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            fields = _form_fields(content_type, raw)
            if fields.get("action") == "reroute":
                self._send(200, desk.page_for_replay(fields), "text/html; charset=utf-8")
                return
            try:
                submission = parse_submission(content_type, raw)
            except UploadError:
                self._send(400, "That upload could not be read.", "text/plain; charset=utf-8")
                return
            try:
                page = desk.page_for_submission(
                    submission,
                    client_key=client_key(self.headers, self.client_address[0]),
                )
            except RateLimited as limited:
                self._send(429, limited.page, "text/html; charset=utf-8", {"Retry-After": "60"})
                return
            self._send(200, page, "text/html; charset=utf-8")

        def log_message(self, fmt: str, *args: Any) -> None:
            logging.getLogger("jev_desk.http").info("%s %s", self.address_string(), fmt % args)

        def _send(
            self,
            status: int,
            body: str,
            content_type: str,
            extra: dict[str, str] | None = None,
        ) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if not self._head_only:
                self.wfile.write(data)

    return Handler


def _form_fields(content_type: str, body: bytes) -> dict[str, str]:
    media = (content_type or "").split(";", 1)[0].strip().lower()
    if media == "multipart/form-data":
        return {}
    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[0] if values else "" for key, values in parsed.items()}


def _replay_message(fields: dict[str, str]) -> str:
    message = fields["message"].strip()
    if not message or len(message) > MAX_CHARS:
        raise ValueError
    return message


def _replay_thresholds(fields: dict[str, str]) -> Thresholds:
    return Thresholds(
        refund_queue=_bounded(fields["refund_queue"], 0, 1),
        confidence_floor=_bounded(fields["confidence_floor"], 0, 1),
        urgent_score=_bounded(fields["urgent_score"], 0, 2),
    )


def _replay_team(fields: dict[str, str]) -> Any:
    choice = fields["team_choice"].strip()
    if not choice or len(choice) > 40 or any(ch.isspace() for ch in choice):
        raise ValueError
    probabilities = {label: _bounded(fields[f"team_prob_{label}"], 0, 1) for label in TEAM_CRITERIA}
    return _Answer(
        choice=choice,
        confidence=_bounded(fields["team_confidence"], 0, 1),
        probabilities=probabilities,
    )


def _replay_urgency(fields: dict[str, str]) -> Any:
    probabilities = {
        index: _bounded(fields[f"urgency_prob_{index}"], 0, 1) for index in range(len(URGENCY_CRITERIA))
    }
    return _Answer(
        score=_bounded(fields["urgency_score"], 0, 2),
        confidence=_bounded(fields["urgency_confidence"], 0, 1),
        probabilities=probabilities,
    )


def _replay_refund(fields: dict[str, str]) -> Any:
    return _Answer(noul=_bounded(fields["refund_noul"], 0, 1))


def _replay_model(fields: dict[str, str], *, live: bool) -> str | None:
    if not live or fields.get("live") != "1":
        return None
    model = fields.get("model", "").strip()
    if not model or len(model) > 80 or any(ch in model for ch in "\r\n<>"):
        return None
    return model


def _bounded(raw: str, low: float, high: float) -> float:
    value = float(raw)
    if value != value or value < low or value > high:
        raise ValueError
    return value


class _Answer:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")


def main() -> None:
    configure_logging()
    host, port = bind_address()
    desk = Desk()
    server = DeskServer((host, port), handler_for(desk))
    mode = "live" if desk.live else "sample mode, live Jev is off"

    def stop(signum: int, _frame: Any) -> None:
        logger.info("received signal %s, shutting down", signum)
        threading.Thread(target=server.shutdown, name="jev-desk-shutdown", daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"jev-desk listening on {host}:{port} ({mode})", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        desk.close()
        logger.info("stopped")


if __name__ == "__main__":
    main()
