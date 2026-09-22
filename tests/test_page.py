"""The one screen, including sample mode when there is no key."""

import os
from http.server import ThreadingHTTPServer
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

from jev_desk.page import TAGLINE, render_page, Page
from jev_desk.samples import SAMPLES, sample_for
from jev_desk.server import Desk, handler_for
from tests.test_routing import answers
from tests.test_triage import FakeClient, FakeResult


EXPECTED = (
    ("Billing", "refund requested"),
    ("On-call", "technical and urgent"),
    ("Sales", "sales team"),
    ("Human review", "low confidence"),
)


def test_samples_route_through_the_same_code_and_do_not_look_live():
    assert sample_for("something else entirely") is None
    for sample, (queue, reason) in zip(SAMPLES, EXPECTED, strict=True):
        result = sample_for(f"  {sample.message}  ")
        assert result is not None
        assert result.queue == queue
        assert result.reason == reason
        assert result.live is False
        assert result.model is None
        assert result.message == sample.message


def test_sample_page_says_live_jev_is_off_and_shows_the_answers():
    result = sample_for(SAMPLES[0].message)
    html = render_page(Page(live=False, draft=SAMPLES[0].message, result=result, notice=None))
    assert TAGLINE in html
    assert "Live Jev is off" in html
    assert "Billing" in html
    assert "refund requested" in html
    assert "billing" in html
    assert "0.86" in html
    assert "0.91" in html
    assert "Can wait" in html
    assert "This week" in html
    assert "Today" in html
    assert "1.72" in html
    assert "0.93" in html
    assert "not called" in html
    assert "No separate confidence" in html
    assert "jev-latest" not in html
    assert "suggested reply" not in html.lower()


def test_custom_message_in_sample_mode_is_not_invented():
    desk = Desk(live=False)
    html = desk.page_for("Please cancel my account and write me a poem.")
    assert "Live Jev is off, so this message was not sent." in html
    assert "No team, urgency, or refund probability was invented" in html
    assert 'class="queue-name"' not in html
    assert "refund requested" not in html
    assert 'class="probs"' not in html


def test_live_page_shows_the_model_id_from_the_response(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    team, urgency, refund = answers(
        choice="sales",
        team_confidence=0.81,
        score=0.4,
        urgency_confidence=0.77,
        noul=0.02,
        team_probabilities={"billing": 0.05, "technical": 0.04, "sales": 0.9, "other": 0.01},
        urgency_probabilities={0: 0.7, 1: 0.2, 2: 0.1},
    )
    client = FakeClient(FakeResult(team, urgency, refund, model="jev-9.9.9"))
    desk = Desk(live=True, client=client)
    html = desk.page_for("What does the annual plan cost?")
    assert len(client.calls) == 1
    assert "Live Jev is on" not in html
    assert "This message goes out once" not in html
    assert "Live Jev is off" not in html
    assert "Sales" in html
    assert "sales team" in html
    assert "jev-9.9.9" in html
    assert "0.90" in html
    assert "Can wait" in html


def test_message_is_escaped():
    team, urgency, refund = answers()
    client = FakeClient(FakeResult(team, urgency, refund))
    desk = Desk(live=True, client=client)
    html = desk.page_for('<script>alert("x")</script>')
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_missing_key_does_not_construct_a_client(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    def explode(*args, **kwargs):
        raise AssertionError("sample mode must not construct TypeSafeClient")

    monkeypatch.setattr("jev_desk.server.TypeSafeClient", explode)
    desk = Desk()
    assert desk.live is False
    html = desk.page_for(SAMPLES[1].message)
    assert "On-call" in html
    assert "technical and urgent" in html


def test_blank_key_is_sample_mode(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "   ")
    assert Desk().live is False


def test_client_uses_jev_latest(monkeypatch):
    captured = {}

    class FakeTypeSafe:
        def __init__(self, model=None):
            captured["model"] = model

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("jev_desk.server.TypeSafeClient", FakeTypeSafe)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present")
    desk = Desk()
    assert desk.live is True
    desk.client()
    desk.close()
    assert captured == {"model": "jev-latest", "closed": True}


def test_http_sample_roundtrip(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    desk = Desk(live=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(desk))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        home = urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert TAGLINE in home
        assert "Live Jev is off" in home
        assert "Nothing sorted yet" in home
        body = urlencode({"message": SAMPLES[3].message}).encode()
        sorted_page = urlopen(f"http://127.0.0.1:{port}/", data=body).read().decode()
        assert "Human review" in sorted_page
        assert "low confidence" in sorted_page
        assert "A vague" in sorted_page
        assert "no product or error." in sorted_page
    finally:
        server.shutdown()
        server.server_close()


def test_http_unknown_path_is_404():
    desk = Desk(live=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(desk))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        try:
            urlopen(f"http://127.0.0.1:{port}/missing")
            status = 200
        except Exception as exc:
            status = getattr(exc, "code", None)
    finally:
        server.shutdown()
        server.server_close()
    assert status == 404


def test_api_error_is_shown_and_does_not_invent_a_queue(monkeypatch):
    from typesafe_sdk import TypeSafeError

    class Broken:
        def system_one(self, state, questions):
            raise TypeSafeError("upstream unavailable")

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    html = Desk(live=True, client=Broken()).page_for("Hello there")
    assert "Jev did not answer." in html
    assert "upstream unavailable" in html
    assert "On-call" not in html
    assert os.environ.get("TYPESAFE_API_KEY") is None
