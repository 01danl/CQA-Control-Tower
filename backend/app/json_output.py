"""Strict model JSON parsing and safe private storage of malformed output."""

import json


def _reject_constant(_value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON property")
        result[key] = value
    return result


def parse_model_json(raw: str) -> object:
    return json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)


def private_output(raw: dict | str) -> dict | str:
    try:
        json.dumps(raw, allow_nan=False)
    except (ValueError, TypeError):
        # PostgreSQL JSON rejects NaN. Preserve the invalid attempt as text, never repair it.
        return json.dumps(raw, ensure_ascii=False, default=str)
    return raw
