import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_submission_delivery import check
from scripts.tests.submission_fixtures import profile, reference, submission, write
from scripts.validate_submission import (
    ValidationError,
    WireFormat,
    expected_reference,
    strict_load,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="submission-delivery-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fmt = self.root / "synthetic-format.json"
        write(self.fmt, profile())

    def test_development_checks_only_existing_artifacts(self):
        report, code = check(self.root, self.fmt)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "NOT TESTED")
        write(self.root / "results/dev/results.json", submission(65))
        report, code = check(self.root, self.fmt)
        self.assertEqual(code, 0)
        self.assertEqual(report["files"]["dev"]["status"], "PASS")
        self.assertEqual(report["files"]["prod"]["status"], "NOT TESTED")
        self.assertFalse(report["format_gate_passed"])

    def test_final_requires_both_and_correct_counts(self):
        report, code = check(self.root, self.fmt, final=True)
        self.assertEqual(code, 1)
        write(self.root / "results/dev/results.json", submission(65))
        report, code = check(self.root, self.fmt, final=True)
        self.assertEqual(code, 1)
        write(self.root / "results/prod/results.json", submission(9))
        report, code = check(self.root, self.fmt, final=True)
        self.assertEqual(code, 1)
        self.assertEqual(report["files"]["prod"]["code"], "RECORD_COUNT_MISMATCH")
        write(self.root / "results/prod/results.json", submission(10))
        report, code = check(self.root, self.fmt, final=True)
        self.assertEqual(code, 0)
        self.assertTrue(report["format_gate_passed"])

    def test_existing_artifact_cannot_bypass_unconfirmed_or_missing_profile(self):
        write(self.root / "results/dev/results.json", submission(65))
        pending = profile()
        pending["confirmed"] = False
        write(self.fmt, pending)
        report, code = check(self.root, self.fmt)
        self.assertEqual(code, 1)
        self.assertEqual(report["code"], "FORMAT_NOT_CONFIRMED")
        self.fmt.unlink()
        self.assertEqual(check(self.root, self.fmt)[1], 1)

    def test_reference_datasets_are_checked_separately_per_group(self):
        sources = {}
        for group, count in (("dev", 65), ("prod", 10)):
            write(self.root / f"results/{group}/results.json", submission(count))
            sources[group] = self.root / f"private-{group}.json"
            write(sources[group], reference(count))
        report, code = check(self.root, self.fmt, final=True, sources=sources)
        self.assertEqual(code, 0)
        self.assertTrue(all(row["source_ids"] == "PASS" for row in report["files"].values()))
        bad = reference(10)
        bad["data"]["records"][-1]["conversation_id"] = "not-a-submitted-id"
        write(sources["prod"], bad)
        report, code = check(self.root, self.fmt, final=True, sources=sources)
        self.assertEqual(code, 1)
        self.assertEqual(report["files"]["prod"]["code"], "SOURCE_ID_SET_MISMATCH")

    def test_full_private_call_cannot_be_smuggled_through_explanations(self):
        payload = submission()
        ref = reference()["data"]["records"][0]
        ref["channel"] = "voice call"
        ref["transcript"][0]["text"] = (
            'Synthetic client with "quoted words" and many private details for this validator test. '
            * 2
        )
        ref["transcript"][1]["text"] = (
            "Synthetic operator reply for this validation test, not a customer transcript. " * 2
        )
        payload["results"][0]["criteria"][0]["rationale"] = ref["transcript"][0]["text"]
        payload["results"][0]["criteria"][1]["rationale"] = ref["transcript"][1]["text"]
        with self.assertRaises(ValidationError) as error:
            validate(payload, 1, WireFormat.read(self.fmt), transcripts={"synthetic-test-0": ref})
        self.assertEqual(error.exception.code, "FULL_PRIVATE_CALL_COPY")
        payload = submission()
        payload["results"][0]["criteria"][0]["rationale"] = json.dumps(ref["transcript"])
        with self.assertRaises(ValidationError):
            validate(payload, 1, WireFormat.read(self.fmt))

    def test_final_cli_nonzero_and_broken_symlink_not_silently_skipped(self):
        path = self.root / "results/dev/results.json"
        path.parent.mkdir(parents=True)
        path.symlink_to(self.root / "nonexistent.json")
        self.assertEqual(check(self.root, self.fmt)[1], 1)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check_submission_delivery.py"),
                "--root",
                str(self.root),
                "--format",
                str(self.fmt),
                "--final",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_simulation_never_writes_repository_official_results(self):
        paths = [ROOT / f"results/{group}/results.json" for group in ("dev", "prod")]
        before = [path.read_bytes() if path.exists() else None for path in paths]
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/drill_submission_delivery.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "SIMULATION_PASS")
        self.assertFalse(report["official_submission"])
        self.assertEqual(before, [path.read_bytes() if path.exists() else None for path in paths])

    def test_independent_validator_never_imports_backend_or_exporter(self):
        import ast

        tree = ast.parse((ROOT / "scripts/validate_submission.py").read_text())
        for node in ast.walk(tree):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            self.assertFalse(
                any(name.startswith(("app", "backend")) or "exporter" in name for name in names)
            )
        with self.assertRaises(ValidationError):
            validate(copy.deepcopy(submission()), 0, WireFormat.read(self.fmt))


class ReferenceGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="submission-reference-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fmt = self.root / "synthetic-format.json"
        write(self.fmt, profile())

    def test_ids_only_reference_enables_source_identity_gate(self):
        from scripts.generate_submission_reference import build_reference

        def row(index):
            return type(
                "Row", (), {"conversation_id": f"synthetic-test-{index}", "transcript": []}
            )()

        document = build_reference([row(0)])
        self.assertEqual(document, {"items": [{"conversation_id": "synthetic-test-0"}], "total": 1})
        rows = [row(i) for i in range(65)]
        path = self.root / "reference.json"
        write(path, build_reference(rows))
        ids, transcripts = expected_reference(path, 65)
        self.assertEqual(len(ids), 65)
        self.assertEqual(transcripts, {})
        write(self.root / "results/dev/results.json", submission(65))
        report, code = check(self.root, self.fmt, sources={"dev": path})
        self.assertEqual(code, 0)
        self.assertEqual(report["files"]["dev"]["source_ids"], "PASS")

    def test_reference_detects_fabricated_conversation_id(self):
        from scripts.generate_submission_reference import build_reference

        def row(index):
            return type(
                "Row", (), {"conversation_id": f"synthetic-test-{index}", "transcript": []}
            )()

        path = self.root / "reference.json"
        write(path, build_reference([row(i) for i in range(65)]))
        payload = submission(65)
        payload["results"][0]["conversation_id"] = "fabricated-id"
        path.parent.mkdir(parents=True, exist_ok=True)
        (self.root / "results/dev").mkdir(parents=True)
        (self.root / "results/dev/results.json").write_text(json.dumps(payload))
        report, code = check(self.root, self.fmt, sources={"dev": path})
        self.assertEqual(code, 1)
        self.assertEqual(report["files"]["dev"]["status"], "FAIL")

    def test_transcript_reference_is_refused_inside_repository(self):
        import scripts.generate_submission_reference as generator

        with self.assertRaises(SystemExit):
            generator._refuse_private_output(ROOT / "scripts" / "leak.json")
        # The gitignored data/ directory is the documented safe location.
        generator._refuse_private_output(ROOT / "data" / "submission-reference" / "prod.json")


class TeamGateTests(unittest.TestCase):
    def test_wrong_team_name_fails_validation(self):
        payload = submission(1)
        payload["team_name"] = "not-bda2402"
        directory = tempfile.TemporaryDirectory(prefix="submission-team-test-")
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "results.json"
        write(path, payload)
        with self.assertRaises(ValidationError) as caught:
            validate(
                strict_load(path),
                1,
                WireFormat.read(Path(__file__).resolve().parents[1] / "submission_format.json"),
            )
        self.assertEqual(caught.exception.code, "TEAM_NAME_MISMATCH")
