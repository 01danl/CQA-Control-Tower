#!/usr/bin/env python3
"""Independent, offline, stdlib-only organizer submission validator.

Never imports exporter/backend scoring, creates submissions, or calls any API.
An explicit confirmed wire-format profile is required: unknown formats fail closed.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

TEAM = "bda2402"
MODEL = "deepseek/deepseek-v4-flash-0731"
OFFICIAL_FIELDS = {
    "records_key": "results",
    "criterion_id_key": "criterion_id",
    "explanation_key": "rationale",
    "evidence_key": "evidence_turns",
    "criteria_container": "list",
    "binary_encoding": "boolean",
    "model_modes": ["external_api"],
    "error_style": "string",
    "error_critical_value": None,
    "evidence_required": True,
    "error_key": "error",
}
WEIGHTS = {
    "contact": 10,
    "discovery": 15,
    "identification": 20,
    "consultation": 20,
    "empathy": 15,
    "dialogue": 15,
    "closure": 5,
    "critical": 0,
}
NA_IDS = {"discovery", "identification", "consultation", "closure"}
SCALES = {"consultation": {0, 5, 10, 15, 20}, "dialogue": {0, 4, 7, 10}}
MAX_BYTES = 32 * 1024 * 1024
SECRET = re.compile(
    r"(?:sk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{16,}|\bAKIA[A-Z0-9]{16}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~-]{12,}|"
    r"(?:api[_ -]?key|client[_ -]?secret|password|authorization)\s*[:=]\s*[\"']?[A-Za-z0-9_./+~-]{12,})",
    re.IGNORECASE,
)
URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
SENSITIVE_QUERY = {
    "sig",
    "signature",
    "token",
    "access_token",
    "api_key",
    "apikey",
    "key",
    "code",
    "credential",
    "x-amz-signature",
    "x-amz-credential",
    "x-goog-signature",
    "x-goog-credential",
    "se",
    "sv",
}


class ValidationError(Exception):
    def __init__(self, code: str, location: str = "$"):
        self.code = code
        self.location = location
        super().__init__(code)


def require(condition: bool, code: str, location: str = "$") -> None:
    if not condition:
        raise ValidationError(code, location)


def strict_load(path: Path) -> object:
    def pairs(items):
        output = {}
        for key, value in items:
            require(key not in output, "DUPLICATE_JSON_KEY")
            output[key] = value
        return output

    def nonfinite(_value):
        raise ValidationError("NONFINITE_JSON")

    try:
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) and not path.is_symlink(), "REGULAR_FILE_REQUIRED")
        require(path.stat().st_size <= MAX_BYTES, "FILE_TOO_LARGE")
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_float=Decimal,
            parse_constant=nonfinite,
        )
    except ValidationError:
        raise
    except (OSError, ValueError, RecursionError):
        raise ValidationError("JSON_OR_FILE_INVALID") from None


def shape(value: object, required: set[str], optional: set[str], location: str) -> dict:
    require(type(value) is dict, "OBJECT_REQUIRED", location)
    require(required <= set(value), "REQUIRED_FIELD_MISSING", location)
    require(set(value) <= required | optional, "UNEXPECTED_FIELD", location)
    return value


def nonblank(value: object, location: str, maximum: int = 4000) -> str:
    require(
        type(value) is str and bool(value.strip()) and len(value) <= maximum,
        "NONBLANK_STRING_REQUIRED",
        location,
    )
    return value


@dataclass(frozen=True)
class WireFormat:
    records_key: str
    criterion_id_key: str
    explanation_key: str
    evidence_key: str
    criteria_container: str
    binary_encoding: str
    model_modes: tuple[str, ...]
    error_style: str
    error_critical_value: bool | None
    evidence_required: bool
    error_key: str = "error"

    @classmethod
    def read(cls, path: Path) -> WireFormat:
        profile = strict_load(path)
        fields = {
            "profile_version",
            "confirmed",
            "authority",
            "records_key",
            "criterion_id_key",
            "explanation_key",
            "evidence_key",
            "criteria_container",
            "binary_encoding",
            "model_modes",
            "error_style",
            "error_critical_value",
            "evidence_required",
            "error_key",
        }
        profile = shape(profile, fields, set(), "$profile")
        require(
            profile["profile_version"] == "1.0" and profile["confirmed"] is True,
            "FORMAT_NOT_CONFIRMED",
            "$profile",
        )
        nonblank(profile["authority"], "$profile/authority")
        require(
            all(profile[k] == value for k, value in OFFICIAL_FIELDS.items()),
            "OFFICIAL_PROFILE_MISMATCH",
            "$profile",
        )
        for key in (
            "records_key",
            "criterion_id_key",
            "explanation_key",
            "evidence_key",
            "error_key",
        ):
            require(
                type(profile[key]) is str
                and re.fullmatch(r"[a-z][a-z0-9_]{0,39}", profile[key]) is not None,
                "PROFILE_FIELD_INVALID",
                "$profile",
            )
        require(
            profile["records_key"] not in {"schema_version", "team_name", "model"},
            "PROFILE_FIELD_COLLISION",
            "$profile",
        )
        require(
            len(
                {profile[k] for k in ("criterion_id_key", "explanation_key", "evidence_key")}
                | {"value"}
            )
            == 4,
            "PROFILE_FIELD_COLLISION",
            "$profile",
        )
        require(
            profile["error_key"] not in {"conversation_id", "status", "criteria", "score"},
            "PROFILE_FIELD_COLLISION",
            "$profile",
        )
        require(
            profile["criteria_container"] in {"list", "object"}
            and profile["binary_encoding"] in {"boolean", "yes_no"},
            "PROFILE_ENUM_INVALID",
            "$profile",
        )
        modes = profile["model_modes"]
        require(
            type(modes) is list
            and bool(modes)
            and all(type(m) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,29}", m) for m in modes)
            and len(set(modes)) == len(modes),
            "PROFILE_MODES_INVALID",
            "$profile",
        )
        require(
            profile["error_style"] in {"string", "object"}
            and (
                profile["error_critical_value"] is None
                or type(profile["error_critical_value"]) is bool
            ),
            "PROFILE_ERROR_INVALID",
            "$profile",
        )
        require(type(profile["evidence_required"]) is bool, "PROFILE_EVIDENCE_INVALID", "$profile")
        return cls(
            **{
                k: tuple(v) if k == "model_modes" else v
                for k, v in profile.items()
                if k not in {"profile_version", "confirmed", "authority"}
            }
        )


def privacy_check(value: object, location: str = "$") -> None:
    """Conservative pattern guard, not proof that arbitrary prose contains no secret."""
    if type(value) is dict:
        for index, (key, child) in enumerate(value.items()):
            require(type(key) is str and not SECRET.search(key), "SECRET_PATTERN", location)
            require(
                key.lower()
                not in {
                    "transcript",
                    "conversation_snapshot",
                    "audio_url",
                    "api_key",
                    "llm_api_key",
                    "openai_api_key",
                    "cqa_dataset_url",
                    "authorization",
                    "raw_output",
                    "messages",
                },
                "PRIVATE_FIELD",
                location,
            )
            privacy_check(child, f"{location}/field[{index}]")
    elif type(value) is list:
        for index, child in enumerate(value):
            privacy_check(child, f"{location}/[{index}]")
    elif type(value) is str:
        require(SECRET.search(value) is None, "SECRET_PATTERN", location)
        require(
            not (re.search(r'"speaker"\s*:', value) and re.search(r'"timestamp"\s*:', value)),
            "SERIALIZED_TRANSCRIPT",
            location,
        )
        for match in URL.finditer(value):
            try:
                url = urlsplit(match.group())
                query = {k.lower() for k, _ in parse_qsl(url.query, keep_blank_values=True)}
                require(
                    not url.username
                    and not url.password
                    and not query.intersection(SENSITIVE_QUERY),
                    "SIGNED_OR_CREDENTIAL_URL",
                    location,
                )
            except ValueError:
                raise ValidationError("UNSAFE_URL", location) from None


def expected_reference(path: Path, count: int) -> tuple[set[str], dict[str, dict]]:
    raw = strict_load(path)
    if type(raw) is dict and "isSuccess" in raw:
        require(raw["isSuccess"] is True and type(raw.get("data")) is dict, "REFERENCE_INVALID")
        rows = raw["data"].get("records")
        if "total_records" in raw["data"]:
            require(
                type(raw["data"]["total_records"]) is int and raw["data"]["total_records"] == count,
                "REFERENCE_COUNT_MISMATCH",
            )
    elif type(raw) is dict:
        rows = raw.get("items")
        if "total" in raw:
            require(type(raw["total"]) is int and raw["total"] == count, "REFERENCE_COUNT_MISMATCH")
    else:
        rows = raw
    require(type(rows) is list and len(rows) == count, "REFERENCE_COUNT_MISMATCH")
    ids = set()
    transcripts = {}
    for index, row in enumerate(rows):
        location = f"$reference/[{index}]"
        if type(row) is str:
            cid = nonblank(row, location, 200)
        else:
            require(type(row) is dict, "REFERENCE_INVALID", location)
            cid = nonblank(row.get("conversation_id"), location, 200)
            if "transcript" in row:
                require(
                    type(row["transcript"]) is list and bool(row["transcript"]),
                    "REFERENCE_TRANSCRIPT_INVALID",
                    location,
                )
                require(
                    all(type(m) is dict and type(m.get("text")) is str for m in row["transcript"]),
                    "REFERENCE_TRANSCRIPT_INVALID",
                    location,
                )
                transcripts[cid] = row
        require(cid not in ids, "REFERENCE_DUPLICATE_ID", location)
        ids.add(cid)
    return ids, transcripts


def independently_score(values: dict[str, object], encoding: str) -> Decimal:
    """Exact Fraction arithmetic; positive HALF_UP via integer division, no backend import."""
    earned = Fraction(0)
    denominator = 0
    for cid, weight in WEIGHTS.items():
        value = values[cid]
        if weight == 0 or value is None:
            continue
        denominator += weight
        fraction = (
            Fraction(value) / max(SCALES[cid])
            if cid in SCALES
            else Fraction(int(value is True if encoding == "boolean" else value == "yes"))
        )
        earned += weight * fraction
    require(denominator > 0, "SCORE_NOT_CALCULABLE")
    exact = 100 * earned / denominator
    whole, remainder = divmod(exact.numerator * 100, exact.denominator)
    cents = whole + int(2 * remainder >= exact.denominator)
    return Decimal(cents) / 100


def check_value(cid: str, value: object, fmt: WireFormat, location: str) -> None:
    if value is None:
        require(cid in NA_IDS, "NA_NOT_ALLOWED", location)
    elif cid in SCALES:
        require(
            type(value) in (int, float, Decimal)
            and Decimal(str(value)).is_finite()
            and value in SCALES[cid],
            "NUMERIC_SCALE_INVALID",
            location,
        )
    elif fmt.binary_encoding == "boolean":
        require(type(value) is bool, "BINARY_BOOLEAN_REQUIRED", location)
    else:
        require(type(value) is str and value in {"yes", "no"}, "BINARY_YES_NO_REQUIRED", location)


def reject_full_call_copy(record: dict, reference: dict | None, location: str) -> None:
    if not reference or reference.get("channel") != "voice call":
        return
    texts = [
        re.sub(r"\s+", " ", m["text"]).strip() for m in reference["transcript"] if m["text"].strip()
    ]

    def strings(value):
        if type(value) is str:
            yield value
        elif type(value) is dict:
            for child in value.values():
                yield from strings(child)
        elif type(value) is list:
            for child in value:
                yield from strings(child)

    prose = re.sub(r"\s+", " ", " ".join(strings(record)))
    if len(texts) >= 2 and sum(map(len, texts)) >= 120:
        require(not all(text in prose for text in texts), "FULL_PRIVATE_CALL_COPY", location)


def validate(
    payload: object,
    expected_count: int,
    fmt: WireFormat,
    *,
    reference_ids: set[str] | None = None,
    transcripts: dict[str, dict] | None = None,
    expected_model: str | None = None,
) -> dict:
    require(type(expected_count) is int and expected_count > 0, "EXPECTED_COUNT_INVALID")
    require(
        all(
            getattr(fmt, k) == (tuple(value) if k == "model_modes" else value)
            for k, value in OFFICIAL_FIELDS.items()
        ),
        "OFFICIAL_PROFILE_MISMATCH",
    )
    privacy_check(payload)
    top = shape(payload, {"schema_version", "team_name", "model", fmt.records_key}, set(), "$")
    require(top["schema_version"] == "1.0", "SCHEMA_VERSION_INVALID", "$/schema_version")
    nonblank(top["team_name"], "$/team_name", 200)
    require(top["team_name"] == TEAM, "TEAM_NAME_MISMATCH", "$/team_name")
    model = shape(top["model"], {"mode", "name"}, set(), "$/model")
    require(
        type(model["mode"]) is str and model["mode"] in fmt.model_modes,
        "MODEL_MODE_INVALID",
        "$/model/mode",
    )
    name = nonblank(model["name"], "$/model/name", 200)
    require(
        not re.search(
            r"placeholder|example|mock|synthetic|your[-_ ]?model|unknown|configured[-_ ]model|^test$|^n/?a$",
            name,
            re.IGNORECASE,
        ),
        "MODEL_NAME_PLACEHOLDER",
        "$/model/name",
    )
    require(name == (expected_model or MODEL), "MODEL_NAME_MISMATCH", "$/model/name")
    records = top[fmt.records_key]
    require(type(records) is list and len(records) == expected_count, "RECORD_COUNT_MISMATCH")
    ids: set[str] = set()
    ok = errors = evidence_count = bounded = 0
    transcripts = transcripts or {}
    for index, record in enumerate(records):
        location = f"$/{fmt.records_key}/[{index}]"
        record = shape(
            record,
            {"conversation_id", "status", "criteria", "score"},
            {fmt.error_key},
            location,
        )
        cid = nonblank(record["conversation_id"], f"{location}/conversation_id", 200)
        require(cid not in ids, "DUPLICATE_CONVERSATION_ID", location)
        ids.add(cid)
        require(
            type(record["status"]) is str and record["status"] in {"ok", "error"},
            "STATUS_INVALID",
            location,
        )
        reference = transcripts.get(cid)
        reject_full_call_copy(record, reference, location)
        criteria = record["criteria"]
        require(
            type(criteria) is (list if fmt.criteria_container == "list" else dict),
            "CRITERIA_CONTAINER_INVALID",
            location,
        )
        if record["status"] == "error":
            errors += 1
            require(not criteria and record["score"] is None, "ERROR_RECORD_NOT_EMPTY", location)
            error = record.get(fmt.error_key)
            if fmt.error_style == "object":
                error = shape(error, {"code", "message"}, set(), location)
                require(
                    type(error["code"]) is str
                    and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", error["code"]) is not None,
                    "ERROR_CODE_UNSAFE",
                    location,
                )
                error = error["message"]
            text = nonblank(error, location, 2000)
            require(
                not re.search(
                    r"traceback|stack trace|sqlalchemy|\b(?:postgres(?:ql)?|sqlite)://|(?:request|response)[_-]?body|\b(?:LLM_API_KEY|OPENAI_API_KEY|CQA_DATASET_URL)\s*=",
                    text,
                    re.IGNORECASE,
                ),
                "ERROR_EXPLANATION_UNSAFE",
                location,
            )
            continue
        ok += 1
        require(record.get(fmt.error_key) is None, "OK_RECORD_HAS_ERROR", location)
        require(len(criteria) == 8, "CRITERION_COUNT_INVALID", location)
        rows = criteria if type(criteria) is list else list(criteria.values())
        keys = None if type(criteria) is list else list(criteria)
        values = {}
        for criterion_index, criterion in enumerate(rows):
            where = f"{location}/criteria/[{criterion_index}]"
            fields = {"value", fmt.explanation_key, fmt.evidence_key}
            if keys is None:
                fields.add(fmt.criterion_id_key)
            criterion = shape(criterion, fields, set(), where)
            criterion_id = (
                criterion[fmt.criterion_id_key] if keys is None else keys[criterion_index]
            )
            require(
                type(criterion_id) is str and criterion_id in WEIGHTS, "CRITERION_ID_INVALID", where
            )
            require(criterion_id not in values, "DUPLICATE_CRITERION_ID", where)
            value = criterion["value"]
            check_value(criterion_id, value, fmt, where)
            values[criterion_id] = value
            nonblank(criterion[fmt.explanation_key], where)
            turns = criterion[fmt.evidence_key]
            require(
                type(turns) is list and (bool(turns) or not fmt.evidence_required),
                "EVIDENCE_ARRAY_REQUIRED",
                where,
            )
            require(
                all(type(turn) is int and turn >= 1 for turn in turns),
                "EVIDENCE_TURN_INVALID",
                where,
            )
            require(len(set(turns)) == len(turns), "EVIDENCE_TURN_DUPLICATE", where)
            evidence_count += len(turns)
            if reference is not None:
                require(
                    all(turn <= len(reference["transcript"]) for turn in turns),
                    "EVIDENCE_OUT_OF_BOUNDS",
                    where,
                )
                bounded += len(turns)
        require(set(values) == set(WEIGHTS), "CRITERION_SET_INVALID", location)
        score_object = shape(
            record["score"], {"final_score", "critical_flag"}, set(), location + "/score"
        )
        score = score_object["final_score"]
        require(
            type(score) in (int, float, Decimal)
            and Decimal(str(score)).is_finite()
            and 0 <= score <= 100,
            "FINAL_SCORE_INVALID",
            location,
        )
        require(
            Decimal(str(score)) == independently_score(values, fmt.binary_encoding),
            "FINAL_SCORE_MISMATCH",
            location,
        )
        critical = (
            values["critical"] is True
            if fmt.binary_encoding == "boolean"
            else values["critical"] == "yes"
        )
        require(
            type(score_object["critical_flag"]) is bool
            and score_object["critical_flag"] is critical,
            "CRITICAL_FLAG_MISMATCH",
            location,
        )
    if reference_ids is not None:
        require(ids == reference_ids, "SOURCE_ID_SET_MISMATCH")
    return {
        "status": "PASS",
        "records": len(records),
        "ok": ok,
        "errors": errors,
        "source_ids": "PASS" if reference_ids is not None else "NOT TESTED",
        "evidence_turns": evidence_count,
        "bounded_evidence_turns": bounded,
        "evidence_bounds": "PASS" if evidence_count and bounded == evidence_count else "NOT TESTED",
        "model_identity": "MATCHED_EXPECTED_NAME"
        if expected_model
        else "DEFAULT_MODEL_NAME_MATCH_NOT_PROVIDER_VERIFIED",
        "privacy": "PATTERN_GUARDS_PASS_MANUAL_REVIEW_STILL_REQUIRED",
    }


def validate_file(
    path: Path,
    count: int,
    fmt: WireFormat,
    source: Path | None = None,
    expected_model: str | None = None,
) -> dict:
    ids, transcripts = expected_reference(source, count) if source else (None, {})
    return validate(
        strict_load(path),
        count,
        fmt,
        reference_ids=ids,
        transcripts=transcripts,
        expected_model=expected_model,
    )


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, json.dumps({"status": "FAIL", "code": "CLI_ARGUMENT_INVALID"}) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument(
        "--format", type=Path, default=Path(__file__).with_name("submission_format.json")
    )
    parser.add_argument("--reference-dataset", type=Path)
    parser.add_argument("--expected-model")
    args = parser.parse_args(argv)
    try:
        require(args.format.is_file(), "FORMAT_PROFILE_MISSING")
        fmt = WireFormat.read(args.format)
        report = validate_file(
            args.submission, args.expected_count, fmt, args.reference_dataset, args.expected_model
        )
        print(json.dumps(report))
        return 0
    except ValidationError as error:
        print(json.dumps({"status": "FAIL", "code": error.code, "location": error.location}))
        return 1
    except Exception:
        # Never echo user content, decoder messages, URLs or exception strings to CI logs.
        print(json.dumps({"status": "FAIL", "code": "VALIDATOR_RUNTIME_ERROR", "location": "$"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
