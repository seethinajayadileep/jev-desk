"""Railway listen address, health check, shutdown, and request limits."""

import json
import os
import signal
import subprocess
import sys
import time
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from jev_desk.server import Desk, RateLimiter, bind_address, handler_for
from tests.test_routing import answers
from tests.test_triage import FakeClient, FakeResult


def _serve(desk: Desk):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(desk))
    thread_started = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread_started.start()
    return server


def test_bind_address_uses_port_and_all_interfaces(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("PORT", "4321")
    assert bind_address() == ("0.0.0.0", 4321)


def test_bind_address_rejects_a_bad_port(monkeypatch):
    monkeypatch.setenv("PORT", "nope")
    with pytest.raises(SystemExit):
        bind_address()


def test_health_is_ok_without_calling_jev(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret-key")

    def explode(*_args, **_kwargs):
        raise AssertionError("health must not construct a client")

    monkeypatch.setattr("jev_desk.server.TypeSafeClient", explode)
    desk = Desk()
    server = _serve(desk)
    port = server.server_address[1]
    try:
        response = urlopen(f"http://127.0.0.1:{port}/health")
        body = json.loads(response.read().decode())
        assert response.status == 200
        assert body == {"status": "ok", "mode": "live"}
        assert "secret-key" not in json.dumps(body)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        connection = HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("HEAD", "/health")
        head = connection.getresponse()
        assert head.status == 200
        assert head.read() == b""
        assert head.headers["Content-Type"].startswith("application/json")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()


def test_sample_health_and_unknown_path():
    server = _serve(Desk(live=False))
    port = server.server_address[1]
    try:
        health = json.loads(urlopen(f"http://127.0.0.1:{port}/health").read().decode())
        assert health == {"status": "ok", "mode": "sample"}
        with pytest.raises(HTTPError) as caught:
            urlopen(f"http://127.0.0.1:{port}/missing")
        assert caught.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_bad_content_length_is_400():
    server = _serve(Desk(live=False))
    port = server.server_address[1]
    try:
        connection = HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("POST", "/", body=b"message=hi", headers={"Content-Length": "nope"})
        response = connection.getresponse()
        assert response.status == 400
        connection.close()
    finally:
        server.shutdown()
        server.server_close()


def test_live_sorts_are_rate_limited_without_a_second_call():
    team, urgency, refund = answers(choice="sales", noul=0.1)
    client = FakeClient(FakeResult(team, urgency, refund, model="jev-1.13.0"))
    desk = Desk(live=True, client=client, limiter=RateLimiter(1))
    server = _serve(desk)
    port = server.server_address[1]
    try:
        first = urlopen(f"http://127.0.0.1:{port}/", data=urlencode({"message": "annual plan"}).encode())
        assert first.status == 200
        assert "Sales" in first.read().decode()
        try:
            urlopen(f"http://127.0.0.1:{port}/", data=urlencode({"message": "annual plan again"}).encode())
            status = 200
            page = ""
        except HTTPError as exc:
            status = exc.code
            page = exc.read().decode()
        assert status == 429
        assert "Too many messages" in page
        assert 'class="queue-name"' not in page
        assert len(client.calls) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_sigterm_stops_the_process():
    probe = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(Desk(live=False)))
    port = probe.server_address[1]
    probe.server_close()
    env = os.environ.copy()
    env.pop("TYPESAFE_API_KEY", None)
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, "-m", "jev_desk"],
        env=env,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                body = json.loads(urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5).read().decode())
                assert body["status"] == "ok"
                break
            except Exception:
                if process.poll() is not None:
                    raise AssertionError(f"server exited early with {process.returncode}")
                time.sleep(0.05)
        else:
            raise AssertionError("server did not open /health")
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
