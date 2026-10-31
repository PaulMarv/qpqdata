import pytest
from pydantic import ValidationError

from app.project_schemas import FormDefinition, ProjectDefinition, Question


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"image_count": 0},
        {"image_count": 1.5},
        {"reward_per_image": 0},
        {"min_width": 0},
        {"allowed_formats": ["SVG"]},
        {"allowed_formats": ["JPEG", "JPEG"]},
        {"labels": [{"key": "clean", "name": "Clean"}, {"key": "clean", "name": "Other"}]},
        {"keywords": ["Kitchen", "kitchen"]},
        {"unexpected": True},
    ],
)
def test_invalid_projects(changes) -> None:
    with pytest.raises(ValidationError):
        ProjectDefinition.model_validate({"name": "Kitchen", **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"options": ["one"]},
        {"options": ["same", "Same"]},
        {"type": "short_text", "options": ["one", "two"]},
        {"min_value": 0},
        {"type": "number", "options": [], "min_value": 10, "max_value": 1},
        {"type": "number", "options": [], "min_value": float("inf")},
        {"type": "yes_no", "options": [], "max_length": 20},
        {"type": "multiple_choice", "min_selections": 3, "options": ["one", "two"]},
        {"type": "short_text", "options": [], "min_length": 10, "max_length": 3},
    ],
)
def test_invalid_question_rules(changes) -> None:
    with pytest.raises(ValidationError):
        Question.model_validate(
            {
                "key": "condition",
                "title": "Condition",
                "type": "single_choice",
                "options": ["Clean", "Messy"],
                **changes,
            }
        )


def test_valid_field_types_and_stable_keys() -> None:
    for kind, options in [
        ("single_choice", ["Clean", "Messy"]),
        ("multiple_choice", ["A", "B"]),
        ("short_text", []),
        ("number", []),
        ("yes_no", []),
    ]:
        assert Question(key="question", title="Question", type=kind, options=options).type == kind
    question = Question(key="same", title="Question", type="yes_no")
    with pytest.raises(ValidationError):
        FormDefinition(questions=[question, question])
    assert ProjectDefinition(name="Kitchen").reward_per_image == 1
