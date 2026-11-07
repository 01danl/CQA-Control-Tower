"""Unit/integration test providers only; not importable from the production app."""

from copy import deepcopy

from app.contracts import ConversationDetail, RubricDetail
from app.providers import ProviderReply


def valid_output(rubric: RubricDetail, conversation: ConversationDetail) -> dict:
    index = next((i for i, m in enumerate(conversation.transcript) if m.speaker == "operator"), 0)
    message = conversation.transcript[index]
    return {
        "policy_uncertain": True,
        "results": [
            {
                "criterion_id": c.id,
                "value": max(c.allowed_values)
                if c.type == "numeric_scale"
                else "no"
                if c.type == "violation"
                else "yes",
                "reason": "Synthetic test answer, not a model judgement.",
                "na_reason": None,
                "review_flag": c.type == "numeric_scale",
                "evidence": [{"message_index": index, "quote": message.text, "kind": "support"}],
            }
            for c in rubric.criteria
            if c.enabled
        ],
    }


class TestProvider:
    __test__ = False

    def __init__(self, mutate=None):
        self.calls = []
        self.mutate = mutate

    def generate(self, rubric, conversation, feedback=None):
        self.calls.append(
            deepcopy(
                {
                    "rubric": rubric.model_dump(mode="json"),
                    "conversation": conversation.model_dump(mode="json"),
                    "feedback": feedback,
                }
            )
        )
        output = valid_output(rubric, conversation)
        if self.mutate:
            output = self.mutate(output, len(self.calls))
        return ProviderReply(output, "synthetic-test-provider", 100, 50, 1)
