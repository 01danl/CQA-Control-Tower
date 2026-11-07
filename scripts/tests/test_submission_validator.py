"""All generated JSON stays in test memory/tempdirs; no official results are produced."""

import copy
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts import validate_submission as v
from scripts.tests.submission_fixtures import profile, reference, submission, write

ROOT = Path(__file__).resolve().parents[2]


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="submission-validator-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "synthetic.json"
        self.fmt_path = self.root / "synthetic-format.json"
        write(self.fmt_path, profile())
        self.fmt = v.WireFormat.read(self.fmt_path)
        self.payload = submission()

    def assert_invalid(self, code, payload=None):
        with self.assertRaises(v.ValidationError) as error:
            v.validate(self.payload if payload is None else payload, 1, self.fmt)
        self.assertEqual(error.exception.code, code)

    def test_valid_profile_fixture_and_optional_identity_bounds(self):
        write(self.path, self.payload)
        source = self.root / "private-reference.json"
        write(source, reference())
        report = v.validate_file(self.path, 1, self.fmt, source, self.payload["model"]["name"])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["source_ids"], "PASS")
        self.assertEqual(report["evidence_bounds"], "PASS")
        self.assertEqual(report["bounded_evidence_turns"], 8)

    def test_unconfirmed_format_never_accepts_a_submission(self):
        data = profile()
        data["confirmed"] = False
        write(self.fmt_path, data)
        with self.assertRaises(v.ValidationError) as error:
            v.WireFormat.read(self.fmt_path)
        self.assertEqual(error.exception.code, "FORMAT_NOT_CONFIRMED")

    def test_required_exact_top_level_shape_version_team_and_model(self):
        changes = [
            (lambda p: p.update(schema_version=1.0), "SCHEMA_VERSION_INVALID"),
            (lambda p: p.update(team_name=""), "NONBLANK_STRING_REQUIRED"),
            (lambda p: p.update(team_name="another-team"), "TEAM_NAME_MISMATCH"),
            (lambda p: p.update(extra="unapproved"), "UNEXPECTED_FIELD"),
            (lambda p: p["model"].update(mode="invented"), "MODEL_MODE_INVALID"),
            (lambda p: p["model"].update(name="configured-model"), "MODEL_NAME_PLACEHOLDER"),
            (lambda p: p["model"].update(name=""), "NONBLANK_STRING_REQUIRED"),
            (lambda p: p.pop("model"), "REQUIRED_FIELD_MISSING"),
        ]
        for mutate, code in changes:
            with self.subTest(code=code):
                p = copy.deepcopy(self.payload)
                mutate(p)
                self.assert_invalid(code, p)
        self.assert_invalid("OBJECT_REQUIRED", [])
        with self.assertRaises(v.ValidationError):
            v.validate(self.payload, 1, self.fmt, expected_model="another-real-model")

    def test_counts_duplicate_ids_and_same_count_wrong_source_ids(self):
        p = submission(65)
        self.assertEqual(v.validate(p, 65, self.fmt)["records"], 65)
        p["results"][-1]["conversation_id"] = p["results"][0]["conversation_id"]
        with self.assertRaises(v.ValidationError) as error:
            v.validate(p, 65, self.fmt)
        self.assertEqual(error.exception.code, "DUPLICATE_CONVERSATION_ID")
        for count in (0, 64, 66):
            with self.assertRaises(v.ValidationError):
                v.validate(submission(count), 65, self.fmt)
        with self.assertRaises(v.ValidationError) as error:
            v.validate(self.payload, 1, self.fmt, reference_ids={"another-organizer-id"})
        self.assertEqual(error.exception.code, "SOURCE_ID_SET_MISMATCH")

    def test_all_eight_exact_criteria_required(self):
        for action, code in [
            (lambda r: r["criteria"].pop(), "CRITERION_COUNT_INVALID"),
            (lambda r: r["criteria"][0].update(criterion_id="C99"), "CRITERION_ID_INVALID"),
            (lambda r: r["criteria"][0].update(criterion_id="discovery"), "DUPLICATE_CRITERION_ID"),
            (lambda r: r.update(status="completed"), "STATUS_INVALID"),
        ]:
            with self.subTest(code=code):
                p = copy.deepcopy(self.payload)
                action(p["results"][0])
                self.assert_invalid(code, p)

    def test_binary_types_na_null_and_numeric_exact_scales(self):
        for index, value, code in [
            (0, 1, "BINARY_BOOLEAN_REQUIRED"),
            (0, "yes", "BINARY_BOOLEAN_REQUIRED"),
            (0, None, "NA_NOT_ALLOWED"),
            (7, None, "NA_NOT_ALLOWED"),
            (2, "na", "BINARY_BOOLEAN_REQUIRED"),
            (2, "N/A", "BINARY_BOOLEAN_REQUIRED"),
            (3, True, "NUMERIC_SCALE_INVALID"),
            (3, 7, "NUMERIC_SCALE_INVALID"),
            (5, 5, "NUMERIC_SCALE_INVALID"),
            (3, "15", "NUMERIC_SCALE_INVALID"),
        ]:
            with self.subTest(index=index, value=value):
                p = copy.deepcopy(self.payload)
                p["results"][0]["criteria"][index]["value"] = value
                self.assert_invalid(code, p)
        for index, values in [(3, [0, 5, 10, 15, 20]), (5, [0, 4, 7, 10])]:
            for value in values:
                p = copy.deepcopy(self.payload)
                r = p["results"][0]
                r["criteria"][index]["value"] = value
                values_by_id = {c["criterion_id"]: c["value"] for c in r["criteria"]}
                r["score"]["final_score"] = v.independently_score(values_by_id, "boolean")
                self.assertEqual(v.validate(p, 1, self.fmt)["status"], "PASS")

    def test_evidence_rejects_boolean_zero_negative_float_and_out_of_bounds(self):
        for turns in ([True], [False], [0], [-1], [1.0], ["1"], [], [1, 1]):
            p = copy.deepcopy(self.payload)
            p["results"][0]["criteria"][0]["evidence_turns"] = turns
            with self.subTest(turns=turns), self.assertRaises(v.ValidationError):
                v.validate(p, 1, self.fmt)
        p = copy.deepcopy(self.payload)
        p["results"][0]["criteria"][0]["evidence_turns"] = [3]
        with self.assertRaises(v.ValidationError) as error:
            v.validate(
                p, 1, self.fmt, transcripts={"synthetic-test-0": reference()["data"]["records"][0]}
            )
        self.assertEqual(error.exception.code, "EVIDENCE_OUT_OF_BOUNDS")
        self.assertEqual(v.validate(p, 1, self.fmt)["evidence_bounds"], "NOT TESTED")

    def test_fraction_score_goldens_na_numeric_half_up_and_critical_independence(self):
        cases = [
            ({}, 100),
            ({"identification": None}, 100),
            ({"identification": None, "contact": False}, Decimal("87.50")),
            ({"consultation": 15, "dialogue": 7}, Decimal("90.50")),
            ({"critical": True}, 100),
        ]
        for changes, expected in cases:
            p = copy.deepcopy(self.payload)
            r = p["results"][0]
            for c in r["criteria"]:
                if c["criterion_id"] in changes:
                    c["value"] = changes[c["criterion_id"]]
            r["score"]["final_score"] = expected
            r["score"]["critical_flag"] = changes.get("critical", False)
            self.assertEqual(v.validate(p, 1, self.fmt)["status"], "PASS")
        values = {
            "contact": False,
            "discovery": False,
            "identification": None,
            "consultation": 0,
            "empathy": False,
            "dialogue": 7,
            "closure": False,
            "critical": False,
        }
        self.assertEqual(v.independently_score(values, "boolean"), Decimal("13.13"))
        values.update(discovery=None, consultation=None, dialogue=0, closure=None)
        self.assertEqual(v.independently_score(values, "boolean"), 0)

    def test_finite_score_range_exact_total_and_flag_types(self):
        for value in (True, None, -1, 101, "100", Decimal("NaN"), Decimal("Infinity")):
            p = copy.deepcopy(self.payload)
            p["results"][0]["score"]["final_score"] = value
            self.assert_invalid("FINAL_SCORE_INVALID", p)
        p = copy.deepcopy(self.payload)
        p["results"][0]["score"]["final_score"] = 99
        self.assert_invalid("FINAL_SCORE_MISMATCH", p)
        for flag in (1, None, True):
            p = copy.deepcopy(self.payload)
            p["results"][0]["score"]["critical_flag"] = flag
            self.assert_invalid("CRITICAL_FLAG_MISMATCH", p)
        p = copy.deepcopy(self.payload)
        p["results"][0]["criteria"][-1]["value"] = True
        p["results"][0]["score"]["final_score"] = 0
        p["results"][0]["score"]["critical_flag"] = True
        self.assert_invalid("FINAL_SCORE_MISMATCH", p)

    def test_error_records_empty_safe_and_cannot_claim_clean_or_scored(self):
        p = copy.deepcopy(self.payload)
        r = p["results"][0]
        r.update(
            status="error",
            criteria=[],
            score=None,
            error="Evaluation unavailable after bounded retries.",
        )
        self.assertEqual(v.validate(p, 1, self.fmt)["errors"], 1)
        for changes in (
            {"criteria": self.payload["results"][0]["criteria"]},
            {"score": {"final_score": 0, "critical_flag": False}},
            {"error": ""},
            {"error": "Traceback private stack trace"},
        ):
            q = copy.deepcopy(p)
            q["results"][0].update(changes)
            with self.subTest(changes=list(changes)), self.assertRaises(v.ValidationError):
                v.validate(q, 1, self.fmt)

    def test_privacy_patterns_and_raw_transcripts_rejected_without_echo(self):
        for leaked in (
            "sk-" + "x" * 30,
            "https://example.invalid/data?sig=private-test-signature",
            "Bearer " + "X" * 30,
        ):
            p = copy.deepcopy(self.payload)
            p["results"][0]["criteria"][0]["rationale"] = leaked
            with self.subTest(), self.assertRaises(v.ValidationError) as error:
                v.validate(p, 1, self.fmt)
            self.assertNotIn(leaked, str(error.exception))
        p = copy.deepcopy(self.payload)
        p["results"][0]["transcript"] = []
        self.assert_invalid("PRIVATE_FIELD", p)
        p = copy.deepcopy(self.payload)
        p["results"][0]["criteria"][0]["rationale"] = (
            "Policy reference https://example.invalid/public-policy"
        )
        self.assertEqual(v.validate(p, 1, self.fmt)["status"], "PASS")

    def test_strict_json_duplicate_keys_nonfinite_huge_exponent_and_symlink(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', "{broken"):
            self.path.write_text(text)
            with self.subTest(text=text), self.assertRaises(v.ValidationError):
                v.strict_load(self.path)
        write(self.path, self.payload)
        text = self.path.read_text().replace('"final_score": 100', '"final_score": 1e9999')
        self.path.write_text(text)
        with self.assertRaises(v.ValidationError):
            v.validate_file(self.path, 1, self.fmt)
        link = self.root / "symlink.json"
        link.symlink_to(self.path)
        with self.assertRaises(v.ValidationError):
            v.strict_load(link)

    def test_source_ids_bounds_failures_and_ids_only_coverage(self):
        source = self.root / "source.json"
        write(source, ["synthetic-test-0"])
        ids, turns = v.expected_reference(source, 1)
        self.assertEqual(
            v.validate(self.payload, 1, self.fmt, reference_ids=ids, transcripts=turns)[
                "evidence_bounds"
            ],
            "NOT TESTED",
        )
        bad = reference()
        bad["isSuccess"] = False
        write(source, bad)
        with self.assertRaises(v.ValidationError):
            v.expected_reference(source, 1)
        duplicate = reference(2)
        duplicate["data"]["records"][1]["conversation_id"] = "synthetic-test-0"
        write(source, duplicate)
        with self.assertRaises(v.ValidationError):
            v.expected_reference(source, 2)

    def test_cli_nonzero_and_no_sensitive_content_in_stdout_or_stderr(self):
        secret = "sk-" + "Z" * 30
        self.payload["results"][0]["criteria"][0]["rationale"] = secret
        write(self.path, self.payload)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/validate_submission.py"),
                str(self.path),
                "--expected-count",
                "1",
                "--format",
                str(self.fmt_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["code"], "SECRET_PATTERN")

    def test_alternate_format_cannot_override_official_schema(self):
        data = profile()
        for key, value in (
            ("criteria_container", "object"),
            ("binary_encoding", "yes_no"),
            ("explanation_key", "explanation"),
            ("model_modes", ["single"]),
        ):
            bad = {**data, key: value}
            write(self.fmt_path, bad)
            with self.assertRaises(v.ValidationError) as error:
                v.WireFormat.read(self.fmt_path)
            self.assertEqual(error.exception.code, "OFFICIAL_PROFILE_MISMATCH")
        p = copy.deepcopy(self.payload)
        r = p["results"][0]
        r.update(r.pop("score"))
        self.assert_invalid("REQUIRED_FIELD_MISSING", p)
        p = copy.deepcopy(self.payload)
        p["results"][0]["criteria"][0]["criterion_id"] = "C01"
        self.assert_invalid("CRITERION_ID_INVALID", p)

    def test_all_5184_legal_values_match_separate_decimal_reference(self):
        from decimal import ROUND_HALF_UP, localcontext

        choices = [
            [False, True],
            [False, True, None],
            [False, True, None],
            [0, 5, 10, 15, 20, None],
            [False, True],
            [0, 4, 7, 10],
            [False, True, None],
            [False, True],
        ]
        weights = [10, 15, 20, 20, 15, 15, 5, 0]
        for row in itertools.product(*choices):
            denominator = sum(w for value, w in zip(row, weights, strict=True) if value is not None)
            with localcontext() as context:
                context.prec = 40
                numerator = sum(
                    Decimal(w)
                    * (
                        Decimal(value) / (20 if i == 3 else 10)
                        if i in (3, 5)
                        else Decimal(int(value))
                    )
                    for i, (value, w) in enumerate(zip(row, weights, strict=True))
                    if value is not None
                )
                expected = (100 * numerator / denominator).quantize(
                    Decimal(".01"), rounding=ROUND_HALF_UP
                )
            actual = v.independently_score(dict(zip(v.WEIGHTS, row, strict=True)), "boolean")
            self.assertEqual(actual, expected)

    def test_malformed_cli_does_not_echo_argument_secrets(self):
        secret = "sk-" + "Q" * 30
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/validate_submission.py"),
                str(self.path),
                "--expected-count",
                secret,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stderr)["code"], "CLI_ARGUMENT_INVALID")
