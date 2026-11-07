"""Pure deterministic scoring. No I/O, model decisions, ID-specific rules or mutation."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.contracts import Criterion, Value


@dataclass(frozen=True)
class Score:
    final_score: Decimal | None
    weighted_points: dict[str, Decimal | None]
    applicable_weight: Decimal
    gross_error: bool


def validate_value(criterion: Criterion, value: object) -> None:
    if value == "na":
        if not criterion.allows_na:
            raise ValueError("N/A is not allowed for this criterion")
        return
    if criterion.type == "numeric_scale":
        if type(value) not in (int, float) or value not in criterion.allowed_values:
            raise ValueError("Value must be an allowed numeric scale step")
    elif type(value) is not str or value not in criterion.allowed_values:
        raise ValueError("Value must be yes or no")


def score_evaluation(criteria: Sequence[Criterion], values: Mapping[str, Value]) -> Score:
    active = [criterion for criterion in criteria if criterion.enabled]
    if set(values) != {criterion.id for criterion in active}:
        raise ValueError("Results must match the enabled criterion IDs exactly")
    points: dict[str, Decimal | None] = {}
    denominator = Decimal(0)
    numerator = Decimal(0)
    gross_error = False
    # Round once, at the end. HALF_UP is a project choice, not a PDF requirement.
    with localcontext() as context:
        context.prec = 40
        for criterion in active:
            value = values[criterion.id]
            validate_value(criterion, value)
            if criterion.type == "violation":
                gross_error |= value == "yes"
                points[criterion.id] = Decimal(0)
                continue
            if value == "na":
                points[criterion.id] = None
                continue
            fraction = (
                Decimal(str(value)) / max(Decimal(str(v)) for v in criterion.allowed_values)
                if criterion.type == "numeric_scale"
                else Decimal(int(value == "yes"))
            )
            contribution = criterion.weight * fraction
            points[criterion.id] = contribution
            if criterion.weight > 0:
                numerator += contribution
                denominator += criterion.weight
        score = (
            (100 * numerator / denominator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if denominator
            else None
        )
    return Score(score, points, denominator, gross_error)
