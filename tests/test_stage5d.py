"""Stage 5d contract and report embedding regressions."""

import json
import unittest
from unittest.mock import patch

import sightdiff_tools as tools
from engine.report_json import result_message, write_report
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

