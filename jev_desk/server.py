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

from jev_desk.page import Page, render_page
from jev_desk.samples import sample_for
from jev_desk.triage import sort_message

logger = logging.getLogger("jev_desk")

MAX_CHARS = 8000
MAX_BODY = 64 * 1024
REQUEST_TIMEOUT = 30
DEFAULT_SORTS_PER_MINUTE = 30

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
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

    def page_for(self, message: str | None) -> str:
        if message is None:
            return render_page(Page(live=self.live, draft="", result=None, notice=None))
        text = message.strip()
        if not text:
            return render_page(
                Page(live=self.live, draft="", result=None, notice="Paste a customer message.")
            )
        if len(text) > MAX_CHARS:
            return render_page(
                Page(
                    live=self.live,
                    draft=text[:MAX_CHARS],
                    result=None,
                    notice="That message is too long to sort.",
                )
            )
        if not self.live:
            sample = sample_for(text)
            if sample is None:
                return render_page(
                    Page(
                        live=False,
                        draft=text,
                        result=None,
                        notice="Live Jev is off, so this message was not sent. Choose a built-in sample.",
                    )
                )
            logger.info("sample mode; no system_one call")
            return render_page(Page(live=False, draft=text, result=sample, notice=None))
        try:
            result = sort_message(text, self.client())
        except TypeSafeError as exc:
            logger.warning("system_one failed: %s", exc.__class__.__name__)
            return render_page(
                Page(
                    live=True,
                    draft=text,
                    result=None,
                    notice=f"Jev did not answer. {public_error(exc)}",
                )
            )
        return render_page(Page(live=True, draft=text, result=result, notice=None))


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
                self._send(413, "Message is too large", "text/plain; charset=utf-8")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            message = (parse_qs(raw, keep_blank_values=True).get("message") or [""])[0]
            if message.strip() and not desk.limiter.allow(client_key(self.headers, self.client_address[0])):
                page = render_page(
                    Page(
                        live=desk.live,
                        draft=message.strip()[:MAX_CHARS],
                        result=None,
                        notice="Too many messages. Wait a minute and try again.",
                    )
                )
                self._send(429, page, "text/html; charset=utf-8", {"Retry-After": "60"})
                return
            self._send(200, desk.page_for(message), "text/html; charset=utf-8")

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
