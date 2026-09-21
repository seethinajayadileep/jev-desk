"""Ask Jev once, then hand the typed answers to the router."""

from dataclasses import dataclass
import logging
from typing import Any, Mapping

from jev_desk.questions import TEAM_CRITERIA, URGENCY_CRITERIA, build_questions
from jev_desk.routing import route

logger = logging.getLogger("jev_desk")


@dataclass(frozen=True)
class Probability:
    label: str
    value: float
    chosen: bool


@dataclass(frozen=True)
class GradedAnswer:
    """A Choice or Score, with the chosen label, every probability, and confidence."""

    chosen_label: str
    confidence: float
    probabilities: tuple[Probability, ...]
    score: float | None = None


@dataclass(frozen=True)
class SortedMessage:
    message: str
    queue: str
    reason: str
    model: str | None
    live: bool
    team: GradedAnswer
    urgency: GradedAnswer
    refund_noul: float


def sort_message(message: str, client: Any) -> SortedMessage:
    """Send one customer message. One system_one call carries all three questions."""
    result = client.system_one(message, build_questions())
    logger.info("system_one model=%s", result.model)
    return present(
        message,
        result.choices["team"],
        result.scores["urgency"],
        result.nouls["refund"],
        model=result.model,
        live=True,
    )


def present(
    message: str,
    team: Any,
    urgency: Any,
    refund: Any,
    *,
    model: str | None,
    live: bool,
) -> SortedMessage:
    queue, reason = route(team, urgency, refund)
    return SortedMessage(
        message=message,
        queue=queue,
        reason=reason,
        model=model,
        live=live,
        team=_team_view(team),
        urgency=_urgency_view(urgency),
        refund_noul=float(refund.noul),
    )


def _team_view(team: Any) -> GradedAnswer:
    probabilities = {str(label): float(value) for label, value in team.probabilities.items()}
    labels = list(TEAM_CRITERIA)
    for label in probabilities:
        if label not in labels:
            labels.append(label)
    chosen = str(team.choice)
    if chosen not in labels:
        labels.append(chosen)
    return GradedAnswer(
        chosen_label=chosen,
        confidence=float(team.confidence),
        probabilities=tuple(
            Probability(label=label, value=probabilities.get(label, 0.0), chosen=label == chosen)
            for label in labels
        ),
    )


def _urgency_view(urgency: Any) -> GradedAnswer:
    probabilities = _score_probabilities(urgency.probabilities)
    chosen_index = 0
    best = -1.0
    for index, _label in enumerate(URGENCY_CRITERIA):
        value = probabilities.get(index, 0.0)
        if value >= best:
            best = value
            chosen_index = index
    return GradedAnswer(
        chosen_label=URGENCY_CRITERIA[chosen_index],
        confidence=float(urgency.confidence),
        score=float(urgency.score),
        probabilities=tuple(
            Probability(
                label=label,
                value=probabilities.get(index, 0.0),
                chosen=index == chosen_index,
            )
            for index, label in enumerate(URGENCY_CRITERIA)
        ),
    )


def _score_probabilities(raw: Mapping[Any, Any]) -> dict[int, float]:
    parsed: dict[int, float] = {}
    for key, value in raw.items():
        parsed[int(key)] = float(value)
    return parsed
