"""Stage 5d contract and report embedding regressions."""

import json
import contextlib
import io
import unittest
from unittest.mock import patch

import sightdiff_tools as tools
from engine.report_json import result_message, write_report
from engine.cli import main
from tests import test_plugin


class ContractTests(unittest.TestCase):
    setUp = test_plugin.PluginTests.setUp
    call = test_plugin.PluginTests.call
    baseline = test_plugin.PluginTests.baseline

    def test_request_messages(self):
        self.baseline()
        cases = [({"done": 1}, True, "No unexpected changes | Requests: 1 done"),
                 ({"not_done": 1}, False, "Requests incomplete (1 not_done) | No unexpected changes"),
                 ({"unknown": 1}, False, "Requests incomplete (1 unknown) | No unexpected changes"),
                 ({"skipped": 1}, True, "No unexpected changes | Requests: 1 skipped"),
                 ({"done": 1, "skipped": 2}, True, "No unexpected changes | Requests: 1 done, 2 skipped"),
                 ({"not_done": 1, "unknown": 2}, False,
                  "Requests incomplete (1 not_done, 2 unknown) | No unexpected changes"),
                 ({}, True, "No unexpected changes")]
        case = tools.resolve_data_dir() / "default"
        for counts, ok, expected in cases:
            with self.subTest(counts=counts):
                raw = {"status": "pass", "request_counts": counts, "requests_ok": ok}
                self.assertEqual(result_message(raw), expected)
                result = json.loads(tools._result(raw, "default", tools.resolve_data_dir(), "compare"))
                self.assertEqual(result["message"], expected)
                self.assertTrue(result["success"])
                raw["message"] = "Old visual text"
                write_report(raw, case / "report.json")
                self.assertEqual(json.loads((case / "report.json").read_text())["message"], expected)

    def test_no_requests_keeps_existing_message(self):
        self.baseline()
        result = self.call(tools.handle_compare, {})
        self.assertEqual(result["message"], "No unexpected changes")

    def test_accept_rewrites_report_and_compare_uses_new_baseline(self):
        for cli in (False, True):
            for prior_crops in (False, True):
                with self.subTest(cli=cli, crops=prior_crops):
                    self.baseline(viewport="mobile")
                    self.image.paste("black", (0, 0, 20, 20))
                    self.call(tools.handle_compare, {"requests": [{"id": "PT-1", "type": "comment"}]})
                    case = tools.resolve_data_dir() / "default"
                    if not prior_crops:
                        for child in (case / "crops").iterdir():
                            child.unlink()
                        (case / "crops").rmdir()
                    old_time = json.loads((case / "metadata.json").read_text())["created_at"]
                    if cli:
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertEqual(main(["accept", "default", "--store", str(case.parent)]), 0)
                    else:
                        result = self.call(tools.handle_accept, {})
                        self.assertTrue(result["success"], result)
                        self.assertEqual(result["paths"]["report"], str(case / "report.json"))
                        self.assertIsNone(result["paths"]["diff"])
                    report = json.loads((case / "report.json").read_text())
                    self.assertEqual(report["schema_version"], 1)
                    self.assertEqual(report["status"], "pass")
                    self.assertEqual(report["note"], "baseline_accepted")
                    self.assertTrue(all(value == 0 for value in report["summary"].values()))
                    self.assertEqual(report["boxes"], [])
                    self.assertFalse(any(key.startswith("request") for key in report))
                    self.assertEqual(report["images"], {"before": "baseline.png", "after": "baseline.png", "diff": None})
                    self.assertEqual(report["meta"]["viewport"], {"width": 390, "height": 844, "preset": "mobile"})
                    self.assertNotEqual(report["meta"]["created_at"], old_time)
                    self.assertEqual(json.loads((case / "approvals.json").read_text()), [])
                    self.assertFalse((case / "diff.png").exists())
                    self.assertFalse(list((case / "crops").glob("*")))
                    self.assertEqual(self.call(tools.handle_compare, {})["status"], "pass")
                    self.image.paste("white", (0, 0, 20, 20))

