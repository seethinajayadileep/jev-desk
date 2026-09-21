"""One message, one system_one call. Answers are read off the typed result."""

import logging

from typesafe_sdk import Choice, Noul, Score

from jev_desk.questions import (
    REFUND_INSTRUCTIONS,
    TEAM_CRITERIA,
    TEAM_INSTRUCTIONS,
    URGENCY_CRITERIA,
    URGENCY_INSTRUCTIONS,
    build_questions,
)
from jev_desk.triage import sort_message
from tests.test_routing import answers


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def system_one(self, state, questions):
        self.calls.append((state, questions))
        return self.result

    def __getattr__(self, name):
        raise AssertionError(f"unexpected client call: {name}")


class FakeResult:
    """Only the fields the app is allowed to read. No free text, no answers blob."""

    def __init__(self, team, urgency, refund, model="jev-1.13.0"):
        self.model = model
        self.choices = {"team": team}
        self.scores = {"urgency": urgency}
        self.nouls = {"refund": refund}


def test_build_questions_is_one_dict_of_three_typed_questions():
    questions = build_questions()
    assert list(questions) == ["team", "urgency", "refund"]
    assert isinstance(questions["team"], Choice)
    assert isinstance(questions["urgency"], Score)
    assert isinstance(questions["refund"], Noul)
    assert questions["team"].instructions == TEAM_INSTRUCTIONS
    assert questions["team"].criteria == TEAM_CRITERIA
    assert questions["urgency"].instructions == URGENCY_INSTRUCTIONS
    assert list(questions["urgency"].criteria) == URGENCY_CRITERIA
    assert questions["refund"].instructions == REFUND_INSTRUCTIONS


def test_one_message_makes_one_system_one_call(caplog):
    message = "The export button has been down since Monday and we are blocked."
    team, urgency, refund = answers(
        choice="technical",
        team_confidence=0.88,
        score=1.8,
        urgency_confidence=0.86,
        noul=0.04,
        team_probabilities={"billing": 0.05, "technical": 0.9, "sales": 0.03, "other": 0.02},
        urgency_probabilities={0: 0.04, 1: 0.12, 2: 0.84},
    )
    client = FakeClient(FakeResult(team, urgency, refund, model="jev-1.13.0"))

    with caplog.at_level(logging.INFO, logger="jev_desk"):
        sorted_message = sort_message(message, client)

    assert len(client.calls) == 1
    state, questions = client.calls[0]
    assert state == message
    assert isinstance(state, str)
    assert set(questions) == {"team", "urgency", "refund"}
    assert isinstance(questions["team"], Choice)
    assert isinstance(questions["urgency"], Score)
    assert isinstance(questions["refund"], Noul)
    assert sorted_message.queue == "On-call"
    assert sorted_message.reason == "technical and urgent"
    assert sorted_message.model == "jev-1.13.0"
    assert sorted_message.live is True
    assert sorted_message.team.chosen_label == "technical"
    assert sorted_message.team.confidence == 0.88
    assert [item.label for item in sorted_message.team.probabilities] == [
        "billing",
        "technical",
        "sales",
        "other",
    ]
    assert sorted_message.team.probabilities[1].value == 0.9
    assert [item.label for item in sorted_message.urgency.probabilities] == list(URGENCY_CRITERIA)
    assert sorted_message.urgency.score == 1.8
    assert sorted_message.urgency.chosen_label == "Today"
    assert sorted_message.refund_noul == 0.04
    assert "system_one model=jev-1.13.0" in caplog.text
