import pytest
from pydantic import ValidationError

from app.contracts import RubricDraft
from app.default_rubric import initial_rubric
from app.rubrics import get_rubric, publish, seed_default


def test_default_exact_scales_weights_and_idempotent_seed(session):
    seed_default(session)
    rubric = get_rubric(session, "default", 1)
    assert len(rubric.criteria) == 8
    assert sum(c.weight for c in rubric.criteria) == 100
    assert rubric.criteria[3].allowed_values == [0, 5, 10, 15, 20]
    assert rubric.criteria[5].allowed_values == [0, 4, 7, 10]
    assert rubric.criteria[-1].type == "violation"
    assert rubric.criteria[-1].weight == 0


def test_replace_disable_custom_criterion_versions_immutable(session):
    original = get_rubric(session, "default", 1).model_dump(mode="json")
    draft = initial_rubric().model_dump(mode="json")
    draft["criteria"][0].update(id="custom.replacement", weight=11, instructions="New prompt")
    draft["criteria"][1]["enabled"] = False
    published = publish(session, RubricDraft.model_validate(draft), "default")
    assert published.version == 2
    assert published.criteria[0].id == "custom.replacement"
    assert get_rubric(session, "default", 1).model_dump(mode="json") == original


@pytest.mark.parametrize(
    "change",
    [
        {"weight": -1},
        {"allowed_values": [True, False]},
        {"allows_na": True, "na_rule": ""},
        {"type": "violation", "weight": 1},
        {"type": "numeric_scale", "allowed_values": [0]},
        {"type": "numeric_scale", "allowed_values": [0, 1, 1]},
    ],
)
def test_invalid_rubric_configuration_rejected(change):
    draft = initial_rubric().model_dump(mode="json")
    draft["criteria"][0].update(change)
    with pytest.raises(ValidationError):
        RubricDraft.model_validate(draft)
