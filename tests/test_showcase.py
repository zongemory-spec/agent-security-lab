"""Evidence must reflect enforced outcomes, not hard-coded success labels."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from showcase_evidence import collect_evidence, main
from tools import ToolRouter


class ShowcaseTests(unittest.TestCase):
    def test_eight_concurrent_attempts_and_preserved_preexecution_target(self):
        report = collect_evidence(8)
        self.assertTrue(report["passed"])
        self.assertEqual(report["concurrency"]["consumed"], 1)
        self.assertEqual(report["concurrency"]["denied"], 7)
        self.assertEqual(len(report["concurrency"]["attempts"]), 8)
        self.assertEqual([s["target_exists"] for s in report["approval_flow"]], [True, True, False])

    def test_unexpected_allowed_access_marks_evidence_failed(self):
        execute = ToolRouter.execute

        def broken(router, tool, args, ctx, *rest, **kwargs):
            result = execute(router, tool, args, ctx, *rest, **kwargs)
            if result.audit == "object_permission_denied":
                result.audit = "executed"
                result.ok = True
            return result

        with patch.object(ToolRouter, "execute", broken):
            report = collect_evidence(2)
        self.assertFalse(report["passed"])
        self.assertFalse(next(c for c in report["cases"] if c["scenario"] == "horizontal_access")["passed"])

    def test_cli_failure_exits_nonzero_and_keeps_report(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "failed.json"
            with patch("showcase_evidence.collect_evidence", return_value={
                "passed": False, "scenario_count": 1, "concurrency": {"consumed": 0, "denied": 2}
            }):
                self.assertEqual(main(["--workers", "2", "--out", str(path)]), 1)
            self.assertFalse(json.loads(path.read_text())["passed"])

    def test_existing_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "existing.json"
            path.write_text("original", encoding="utf-8")
            with self.assertRaises(SystemExit):
                main(["--out", str(path)])
            self.assertEqual(path.read_text(), "original")

    def test_worker_limits(self):
        for workers in (0, 1, 33, True, 2.5):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                collect_evidence(workers)
