"""The playground shows the call, the rule trace, and routes the same answers again."""

from urllib.parse import urlencode
from urllib.request import urlopen

from jev_desk.routing import Thresholds
from jev_desk.samples import SAMPLES, sample_for
from jev_desk.server import Desk
from jev_desk.triage import replay
from jev_desk.uploads import Submission, messages_in
from tests.test_routing import answers
from tests.test_triage import FakeClient, FakeResult


def _fields(result, **overrides):
    limits = result.thresholds or Thresholds()
    fields = {
        "action": "reroute",
        "message": result.message,
        "live": "1" if result.live else "0",
        "model": result.model or "",
        "team_choice": result.team.chosen_label,
        "team_confidence": f"{result.team.confidence:.6f}",
        "urgency_score": f"{result.urgency.score:.6f}",
        "urgency_confidence": f"{result.urgency.confidence:.6f}",
        "refund_noul": f"{result.refund_noul:.6f}",
        "refund_queue": f"{limits.refund_queue:.2f}",
        "confidence_floor": f"{limits.confidence_floor:.2f}",
        "urgent_score": f"{limits.urgent_score:.2f}",
    }
    for item in result.team.probabilities:
        fields[f"team_prob_{item.label}"] = f"{item.value:.6f}"
    for index, item in enumerate(result.urgency.probabilities):
        fields[f"urgency_prob_{index}"] = f"{item.value:.6f}"
    fields.update(overrides)
    return fields


def test_sample_page_shows_the_call_the_trace_and_the_score_math():
    result = sample_for(SAMPLES[0].message)
    html = Desk(live=False).page_for(result.message)
    assert "Why this queue" in html
    assert "Refund probability 0.93 is at least 0.70" in html
    assert "Not checked" in html
    assert "How the urgency score is made" in html
    assert "0.05×0 + 0.18×1 + 0.77×2 = 1.72" in html
    assert "The one call" in html
    assert "team · Choice" in html
    assert "urgency · Score" in html
    assert "refund · Noul" in html
    assert "Which team should handle this message?" in html
    assert "Play with the rules" in html
    assert "Same answers. No new Jev call." in html
    assert 'name="refund_queue"' in html


def test_moving_the_refund_cutoff_routes_again_without_calling_jev():
    result = sample_for(SAMPLES[0].message)
    assert result.reason == "refund requested"
    moved = replay(result, Thresholds(refund_queue=0.99))
    assert moved.queue == "Billing"
    assert moved.reason == "billing team"
    assert moved.refund_noul == result.refund_noul

    client = FakeClient(FakeResult(*answers()))
    desk = Desk(live=True, client=client)
    html = desk.page_for_replay(_fields(result, refund_queue="0.99", live="0"))
    assert client.calls == []
    assert "billing team" in html
    assert "Refund probability 0.93 is below 0.99" in html
    assert "Live Jev is on" not in html


def test_http_replay_does_not_spend_a_rate_limit_on_a_second_call():
    from http.server import ThreadingHTTPServer
    import threading

    from jev_desk.server import RateLimiter, handler_for

    result = sample_for(SAMPLES[2].message)
    team, urgency, refund = answers(choice="sales", noul=0.05, team_confidence=0.93, urgency_confidence=0.8)
    client = FakeClient(FakeResult(team, urgency, refund, model="jev-1.13.0"))
    desk = Desk(live=True, client=client, limiter=RateLimiter(1))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(desk))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        first = urlopen(
            f"http://127.0.0.1:{port}/",
            data=urlencode({"message": "annual plan"}).encode(),
        )
        assert first.status == 200
        replayed = urlopen(
            f"http://127.0.0.1:{port}/",
            data=urlencode(_fields(result, confidence_floor="0.99")).encode(),
        )
        page = replayed.read().decode()
    finally:
        server.shutdown()
        server.server_close()
    assert replayed.status == 200
    assert "Human review" in page
    assert "low confidence" in page
    assert len(client.calls) == 1


def test_csv_rows_are_sorted_one_by_one():
    raw = (SAMPLES[0].message + "\n" + SAMPLES[2].message + "\n").encode()
    assert messages_in("inbox.csv", raw) == [SAMPLES[0].message, SAMPLES[2].message]
    html = Desk(live=False).page_for_submission(Submission(message="", filename="inbox.csv", data=raw))
    assert html.count('class="queue-name"') == 2
    assert "Billing" in html
    assert "refund requested" in html
    assert "Sales" in html
    assert "sales team" in html
    assert "2 messages" in html

    team, urgency, refund = answers(choice="sales", noul=0.01, team_confidence=0.9, urgency_confidence=0.9)
    client = FakeClient(FakeResult(team, urgency, refund, model="jev-1.13.0"))
    desk = Desk(live=True, client=client)
    desk.page_for_submission(Submission(message="", filename="two.csv", data=raw))
    assert len(client.calls) == 2
    assert client.calls[0][0] == SAMPLES[0].message
    assert client.calls[1][0] == SAMPLES[2].message
