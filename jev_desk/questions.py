"""The three typed questions sent together in one system_one call."""

from typesafe_sdk import Choice, Noul, Score

TEAM_INSTRUCTIONS = "Which team should handle this message?"
TEAM_CRITERIA = {
    "billing": "Payment, charge, subscription, or refund",
    "technical": "Bug, outage, or integration failure",
    "sales": "Pricing, plan, or new purchase",
    "other": "None of those",
}

URGENCY_INSTRUCTIONS = "How soon does this need a person?"
URGENCY_CRITERIA = ["Can wait", "This week", "Today"]

REFUND_INSTRUCTIONS = "The customer is asking for a refund or their money back."


def build_questions() -> dict[str, Choice | Score | Noul]:
    return {
        "team": Choice(instructions=TEAM_INSTRUCTIONS, criteria=TEAM_CRITERIA),
        "urgency": Score(instructions=URGENCY_INSTRUCTIONS, criteria=URGENCY_CRITERIA),
        "refund": Noul(instructions=REFUND_INSTRUCTIONS),
    }
