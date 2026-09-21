"""Queue selection. This stays in code. Jev does not pick the queue."""

from typing import Mapping, Protocol

REFUND_QUEUE = 0.7
CONFIDENCE_FLOOR = 0.6
URGENT_SCORE = 1.5

TEAM_QUEUES = {
    "billing": ("Billing", "billing team"),
    "technical": ("Technical", "technical team"),
    "sales": ("Sales", "sales team"),
    "other": ("General", "general inbox"),
}


class TeamAnswer(Protocol):
    choice: str
    confidence: float
    probabilities: Mapping[str, float]


class UrgencyAnswer(Protocol):
    score: float
    confidence: float
    probabilities: Mapping[int, float]


class RefundAnswer(Protocol):
    noul: float


def route(team: TeamAnswer, urgency: UrgencyAnswer, refund: RefundAnswer) -> tuple[str, str]:
    """Return the queue name and the one-line reason.

    Refund is checked first. Low confidence on either graded answer sends the
    message to a person. On-call is only for a confident technical ticket that
    scores 1.5 or higher. Everything else follows the team label.
    """
    if refund.noul >= REFUND_QUEUE:
        return "Billing", "refund requested"
    if team.confidence < CONFIDENCE_FLOOR or urgency.confidence < CONFIDENCE_FLOOR:
        return "Human review", "low confidence"
    if team.choice == "technical" and urgency.score >= URGENT_SCORE:
        return "On-call", "technical and urgent"
    mapped = TEAM_QUEUES.get(team.choice)
    if mapped is None:
        return "Human review", "unrecognized team"
    return mapped
