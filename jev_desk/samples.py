"""Built-in messages for when TYPESAFE_API_KEY is missing.

The numbers are fixtures. The queue still comes from routing.py. Nothing here
calls Jev or pretends that it did.
"""

from dataclasses import dataclass

from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer

from jev_desk.questions import URGENCY_CRITERIA
from jev_desk.triage import SortedMessage, present

URGENCY_LEGEND = {index: label for index, label in enumerate(URGENCY_CRITERIA)}


@dataclass(frozen=True)
class Sample:
    message: str
    team_choice: str
    team_confidence: float
    team_probabilities: dict[str, float]
    urgency_score: float
    urgency_confidence: float
    urgency_probabilities: dict[int, float]
    refund_noul: float

    def sorted_message(self) -> SortedMessage:
        team = ChoiceAnswer(
            choice=self.team_choice,
            confidence=self.team_confidence,
            probabilities=self.team_probabilities,
        )
        urgency = ScoreAnswer(
            score=self.urgency_score,
            confidence=self.urgency_confidence,
            legend=URGENCY_LEGEND,
            probabilities=self.urgency_probabilities,
        )
        refund = NoulAnswer(noul=self.refund_noul)
        return present(self.message, team, urgency, refund, model=None, live=False)


SAMPLES: tuple[Sample, ...] = (
    Sample(
        message="Charged twice, wants the money back today.",
        team_choice="billing",
        team_confidence=0.91,
        team_probabilities={"billing": 0.86, "technical": 0.04, "sales": 0.03, "other": 0.07},
        urgency_score=1.72,
        urgency_confidence=0.84,
        urgency_probabilities={0: 0.05, 1: 0.18, 2: 0.77},
        refund_noul=0.93,
    ),
    Sample(
        message="Stripe integration failing for three days, losing sales, needs help ASAP.",
        team_choice="technical",
        team_confidence=0.86,
        team_probabilities={"billing": 0.05, "technical": 0.88, "sales": 0.04, "other": 0.03},
        urgency_score=1.88,
        urgency_confidence=0.92,
        urgency_probabilities={0: 0.02, 1: 0.08, 2: 0.90},
        refund_noul=0.08,
    ),
    Sample(
        message="Asking what the annual plan costs.",
        team_choice="sales",
        team_confidence=0.93,
        team_probabilities={"billing": 0.04, "technical": 0.02, "sales": 0.91, "other": 0.03},
        urgency_score=0.46,
        urgency_confidence=0.78,
        urgency_probabilities={0: 0.62, 1: 0.30, 2: 0.08},
        refund_noul=0.05,
    ),
    Sample(
        message='A vague "it does not work" with no product or error.',
        team_choice="technical",
        team_confidence=0.44,
        team_probabilities={"billing": 0.16, "technical": 0.38, "sales": 0.12, "other": 0.34},
        urgency_score=1.00,
        urgency_confidence=0.37,
        urgency_probabilities={0: 0.30, 1: 0.40, 2: 0.30},
        refund_noul=0.12,
    ),
)

SAMPLE_BY_MESSAGE = {sample.message: sample for sample in SAMPLES}


def sample_for(message: str) -> SortedMessage | None:
    sample = SAMPLE_BY_MESSAGE.get(message.strip())
    if sample is None:
        return None
    return sample.sorted_message()
