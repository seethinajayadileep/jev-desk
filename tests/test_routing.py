"""Routing rules, driven by fake SDK answers. No network."""

import pytest
from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer

from jev_desk.questions import URGENCY_CRITERIA
from jev_desk.routing import route

LEGEND = {index: label for index, label in enumerate(URGENCY_CRITERIA)}
TEAMS = {"billing": 0.7, "technical": 0.1, "sales": 0.1, "other": 0.1}
LEVELS = {0: 0.2, 1: 0.6, 2: 0.2}


def answers(
    *,
    choice: str = "billing",
    team_confidence: float = 0.9,
    score: float = 1.0,
    urgency_confidence: float = 0.9,
    noul: float = 0.1,
    team_probabilities: dict[str, float] | None = None,
    urgency_probabilities: dict[int, float] | None = None,
):
    team = ChoiceAnswer(
        choice=choice,
        confidence=team_confidence,
        probabilities=team_probabilities or TEAMS,
    )
    urgency = ScoreAnswer(
        score=score,
        confidence=urgency_confidence,
        legend=LEGEND,
        probabilities=urgency_probabilities or LEVELS,
    )
    refund = NoulAnswer(noul=noul)
    return team, urgency, refund


def test_refund_at_threshold_goes_to_billing():
    assert route(*answers(noul=0.7, choice="sales")) == ("Billing", "refund requested")


def test_refund_just_below_threshold_does_not_take_the_refund_queue():
    assert route(*answers(noul=0.69, choice="sales")) == ("Sales", "sales team")


def test_refund_wins_over_low_confidence_and_on_call():
    queued = route(
        *answers(
            noul=0.95,
            choice="technical",
            team_confidence=0.2,
            score=2.0,
            urgency_confidence=0.2,
        )
    )
    assert queued == ("Billing", "refund requested")


@pytest.mark.parametrize(
    ("team_confidence", "urgency_confidence"),
    [(0.59, 0.9), (0.9, 0.59), (0.0, 0.0)],
)
def test_confidence_below_floor_goes_to_human_review(team_confidence, urgency_confidence):
    queued = route(
        *answers(
            choice="technical",
            team_confidence=team_confidence,
            urgency_confidence=urgency_confidence,
            score=2.0,
            noul=0.2,
        )
    )
    assert queued == ("Human review", "low confidence")


def test_confidence_at_floor_is_high_enough_to_route():
    assert route(*answers(choice="sales", team_confidence=0.6, urgency_confidence=0.6)) == (
        "Sales",
        "sales team",
    )


def test_technical_and_urgent_goes_on_call():
    assert route(*answers(choice="technical", score=1.5, noul=0.69)) == (
        "On-call",
        "technical and urgent",
    )


def test_technical_below_urgent_score_stays_with_technical():
    assert route(*answers(choice="technical", score=1.49)) == ("Technical", "technical team")


def test_high_urgency_outside_technical_does_not_page_on_call():
    assert route(*answers(choice="sales", score=2.0)) == ("Sales", "sales team")
    assert route(*answers(choice="billing", score=2.0, noul=0.2)) == ("Billing", "billing team")


def test_other_maps_to_general():
    assert route(*answers(choice="other")) == ("General", "general inbox")


def test_unrecognized_team_waits_for_a_person():
    assert route(*answers(choice="legal")) == ("Human review", "unrecognized team")


def test_low_confidence_beats_on_call():
    queued = route(*answers(choice="technical", score=2.0, team_confidence=0.59, noul=0.1))
    assert queued == ("Human review", "low confidence")
