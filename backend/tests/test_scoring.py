from decimal import Decimal

import pytest

from app.contracts import Criterion
from app.default_rubric import initial_rubric
from app.scoring import score_evaluation


def full():
    criteria = initial_rubric().criteria
    values = {
        c.id: max(c.allowed_values)
        if c.type == "numeric_scale"
        else "no"
        if c.type == "violation"
        else "yes"
        for c in criteria
    }
    return criteria, values


def test_full_score_and_na_redistribution():
    criteria, values = full()
    assert score_evaluation(criteria, values).final_score == Decimal("100.00")
    values["C03"] = "na"
    result = score_evaluation(criteria, values)
    assert result.applicable_weight == Decimal(80)
    assert result.final_score == Decimal("100.00")
    assert result.weighted_points["C03"] is None
    values["C01"] = "no"
    assert score_evaluation(criteria, values).final_score == Decimal("87.50")


def test_numeric_contributions_and_violation_separate():
    criteria, values = full()
    values.update(C04=15, C06=7)
    result = score_evaluation(criteria, values)
    assert result.weighted_points["C04"] == Decimal(15)
    assert result.weighted_points["C06"] == Decimal("10.5")
    assert result.final_score == Decimal("90.50")
    values["C08"] = "yes"
    gross = score_evaluation(criteria, values)
    assert gross.gross_error
    assert gross.final_score == result.final_score


@pytest.mark.parametrize("cid,values", [("C04", [0, 5, 10, 15, 20]), ("C06", [0, 4, 7, 10])])
def test_all_exact_numeric_steps(cid, values):
    criteria, outcomes = full()
    for value in values:
        outcomes[cid] = value
        assert score_evaluation(criteria, outcomes).final_score is not None


@pytest.mark.parametrize(
    "cid,value",
    [
        ("C04", 7),
        ("C06", 5),
        ("C01", "na"),
        ("C01", True),
        ("C04", True),
        ("C04", "15"),
        ("C08", "na"),
    ],
)
def test_illegal_values_rejected(cid, value):
    criteria, outcomes = full()
    outcomes[cid] = value
    with pytest.raises(ValueError):
        score_evaluation(criteria, outcomes)


def criterion(cid, weight):
    return Criterion(
        id=cid,
        name=cid,
        section="Synthetic",
        description="Synthetic",
        instructions="Synthetic",
        type="binary",
        weight=weight,
        allowed_values=["yes", "no"],
        allows_na=True,
        na_rule="Synthetic N/A",
    )


def test_custom_no_applicable_weights_is_null_and_all_zero_is_zero():
    c = criterion("custom", 10)
    assert score_evaluation([c], {"custom": "na"}).final_score is None
    c.weight = Decimal(0)
    assert score_evaluation([c], {"custom": "yes"}).final_score is None
    criteria, values = full()
    for item in criteria:
        values[item.id] = "na" if item.allows_na else 0 if item.type == "numeric_scale" else "no"
    assert score_evaluation(criteria, values).final_score == Decimal("0.00")


def test_half_up_is_project_choice_round_once_at_end():
    criteria = [criterion("a", "1.005"), criterion("b", "98.995")]
    assert score_evaluation(criteria, {"a": "yes", "b": "no"}).final_score == Decimal("1.01")
    criteria[0].enabled = False
    assert score_evaluation(criteria, {"b": "yes"}).final_score == Decimal("100.00")
    with pytest.raises(ValueError):
        score_evaluation(criteria, {"a": "yes", "b": "yes"})
