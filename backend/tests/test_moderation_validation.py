import pytest
from pydantic import ValidationError

from app.schemas.moderation import DecisionRequest


@pytest.mark.parametrize(
    "body",
    [
        {"outcome": "rejected"},
        {"outcome": "rejected", "reason": "  "},
        {"outcome": "approved", "reason": "Contradictory"},
        {"outcome": "pending"},
        {"outcome": "approved", "reward": 100},
        {"outcome": "rejected", "reason": "x" * 1001},
    ],
)
def test_invalid_decisions(body):
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate(body)


def test_rejection_reason_is_normalised():
    assert DecisionRequest(outcome="rejected", reason="  Wrong scene  ").reason == "Wrong scene"
