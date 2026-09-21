"""Local one-page server. No login and no database."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import os
from typing import Any
from urllib.parse import parse_qs, urlparse

from typesafe_sdk import TypeSafeClient, TypeSafeError

from jev_desk.page import Page, render_page
from jev_desk.samples import sample_for
from jev_desk.triage import sort_message

logger = logging.getLogger("jev_desk")

MAX_CHARS = 8000
MAX_BODY = 64 * 1024
HOST = "127.0.0.1"
PORT = 8000


def api_key_present() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


class Desk:
    def __init__(self, *, live: bool | None = None, client: Any | None = None) -> None:
        self.live = api_key_present() if live is None else live
        self._client = client
        self._owns_client = False

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


def handler_for(desk: Desk) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/":
                self._send(404, "Not found", "text/plain; charset=utf-8")
                return
            self._send(200, desk.page_for(None), "text/html; charset=utf-8")

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/":
                self._send(404, "Not found", "text/plain; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > MAX_BODY:
                self._send(413, "Message is too large", "text/plain; charset=utf-8")
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            message = (parse_qs(raw, keep_blank_values=True).get("message") or [""])[0]
            self._send(200, desk.page_for(message), "text/html; charset=utf-8")

        def log_message(self, fmt: str, *args: Any) -> None:
            logging.getLogger("jev_desk.http").info("%s %s", self.address_string(), fmt % args)

        def _send(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s %(message)s")
    host = os.environ.get("HOST", HOST)
    port = int(os.environ.get("PORT", str(PORT)))
    desk = Desk()
    server = ThreadingHTTPServer((host, port), handler_for(desk))
    mode = "live" if desk.live else "sample mode, live Jev is off"
    print(f"jev-desk at http://{host}:{port} ({mode})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        server.server_close()
        desk.close()


if __name__ == "__main__":
    main()
