"""Queue selection. This stays in code. Jev does not pick the queue."""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Thresholds:
    """The three cutoffs the desk applies after Jev answers."""

    refund_queue: float = REFUND_QUEUE
    confidence_floor: float = CONFIDENCE_FLOOR
    urgent_score: float = URGENT_SCORE


@dataclass(frozen=True)
class RuleCheck:
    """One step in the routing order."""

    name: str
    detail: str
    state: str  # fired, passed, or skipped


def route(
    team: TeamAnswer,
    urgency: UrgencyAnswer,
    refund: RefundAnswer,
    thresholds: Thresholds | None = None,
) -> tuple[str, str]:
    """Return the queue name and the one-line reason."""
    queue, reason, _steps = judge(team, urgency, refund, thresholds)
    return queue, reason


def judge(
    team: TeamAnswer,
    urgency: UrgencyAnswer,
    refund: RefundAnswer,
    thresholds: Thresholds | None = None,
) -> tuple[str, str, tuple[RuleCheck, ...]]:
    """Walk the rules in order and record which one chose the queue.

    Refund is checked first. Low confidence on either graded answer sends the
    message to a person. On-call is only for a confident technical ticket that
    scores at or above the urgent cutoff. Everything else follows the team label.
    """
    limits = thresholds or Thresholds()
    noul = float(refund.noul)
    team_confidence = float(team.confidence)
    urgency_confidence = float(urgency.confidence)
    score = float(urgency.score)
    choice = str(team.choice)
    steps: list[RuleCheck] = []

    if noul >= limits.refund_queue:
        steps.append(
            RuleCheck(
                "Refund",
                f"Refund probability {noul:.2f} is at least {limits.refund_queue:.2f}. Queue is Billing.",
                "fired",
            )
        )
        steps.extend(_skipped())
        return "Billing", "refund requested", tuple(steps)
    steps.append(
        RuleCheck(
            "Refund",
            f"Refund probability {noul:.2f} is below {limits.refund_queue:.2f}.",
            "passed",
        )
    )

    if team_confidence < limits.confidence_floor or urgency_confidence < limits.confidence_floor:
        steps.append(
            RuleCheck(
                "Confidence",
                (
                    f"Team confidence {team_confidence:.2f} or urgency confidence "
                    f"{urgency_confidence:.2f} is below {limits.confidence_floor:.2f}. "
                    "Queue is Human review."
                ),
                "fired",
            )
        )
        steps.extend(_skipped("On-call", "Team label"))
        return "Human review", "low confidence", tuple(steps)
    steps.append(
        RuleCheck(
            "Confidence",
            (
                f"Team confidence {team_confidence:.2f} and urgency confidence "
                f"{urgency_confidence:.2f} are both at least {limits.confidence_floor:.2f}."
            ),
            "passed",
        )
    )

    if choice == "technical" and score >= limits.urgent_score:
        steps.append(
            RuleCheck(
                "On-call",
                (
                    f"Team is technical and urgency score {score:.2f} is at least "
                    f"{limits.urgent_score:.2f}. Queue is On-call."
                ),
                "fired",
            )
        )
        steps.extend(_skipped("Team label"))
        return "On-call", "technical and urgent", tuple(steps)
    if choice != "technical":
        on_call_detail = f"Team is {choice}, so this is not an on-call ticket."
    else:
        on_call_detail = (
            f"Team is technical and urgency score {score:.2f} is below {limits.urgent_score:.2f}."
        )
    steps.append(RuleCheck("On-call", on_call_detail, "passed"))

    mapped = TEAM_QUEUES.get(choice)
    if mapped is None:
        steps.append(
            RuleCheck(
                "Team label",
                (
                    f"Team label {choice} is not billing, technical, sales, or other. "
                    "Queue is Human review."
                ),
                "fired",
            )
        )
        return "Human review", "unrecognized team", tuple(steps)
    queue, reason = mapped
    steps.append(
        RuleCheck(
            "Team label",
            f"Team label {choice} maps to {queue}.",
            "fired",
        )
    )
    return queue, reason, tuple(steps)


def _skipped(*names: str) -> tuple[RuleCheck, ...]:
    pending = names or ("Confidence", "On-call", "Team label")
    return tuple(
        RuleCheck(name, "Not checked. An earlier rule already chose the queue.", "skipped")
        for name in pending
    )
