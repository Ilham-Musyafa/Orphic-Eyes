"""Stage 5d contract and report embedding regressions."""

import json
import contextlib
import io
import unittest
from unittest.mock import patch

import sightdiff_tools as tools
from engine.report_json import result_message, write_report
from engine.cli import main
from engine.report_html import write_report_html
from tests import test_plugin


class ContractTests(unittest.TestCase):
    setUp = test_plugin.PluginTests.setUp
    call = test_plugin.PluginTests.call
    baseline = test_plugin.PluginTests.baseline

    def embedded(self, path):
        text = path.read_text(encoding="utf-8")
        data = text.split('<script type="application/json" id="orphic-report">', 1)[1].split('</script>', 1)[0]
        self.assertNotIn("</", data)
        self.assertNotIn("<!--", data)
        self.assertNotIn("\u2028", data)
        self.assertNotIn("\u2029", data)
        return json.loads(data)

    def test_html_hostile_strings_round_trip_and_relative_paths(self):
        self.baseline()
        self.call(tools.handle_compare, {})
        case = tools.resolve_data_dir() / "default"
        report = json.loads((case / "report.json").read_text())
        hostile = '</script><script>alert("x")</script><!-- \\ \u2028\u2029'
        report["name"] = hostile
        report["request_results"] = [{"why": hostile}]
        report["crops"] = {"items": [{"before": {"path": "crops/box-1-before.png"}}]}
        (case / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        output = write_report_html(case, test_plugin.FIXTURES / "report_embed.html")
        self.assertEqual(output, case / "report.html")
        self.assertEqual(self.embedded(output), report)

    def test_missing_default_template_does_nothing(self):
        case = self.home / "nonexistent"
        with patch("engine.report_html.DEFAULT_TEMPLATE", self.home / "missing.html"):
            self.assertIsNone(write_report_html(case))
        self.assertFalse(case.exists())
        self.baseline()
        result = self.call(tools.handle_compare, {})
        self.assertNotIn("html", result["paths"])
        result = self.call(tools.handle_accept, {})
        self.assertNotIn("html", result["paths"])

    def test_html_requires_one_placeholder(self):
        self.baseline()
        self.call(tools.handle_compare, {})
        case = tools.resolve_data_dir() / "default"
        template = self.home / "template.html"
        output = case / "report.html"
        output.write_text("previous output")
        for count in (0, 2):
            template.write_text("<!--ORPHIC_REPORT_JSON-->" * count)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                write_report_html(case, template)
            self.assertEqual(output.read_text(), "previous output")

    def test_compare_and_accept_embed_only_with_default_template(self):
        self.baseline(viewport="mobile")
        case = tools.resolve_data_dir() / "default"
        with patch("engine.report_html.DEFAULT_TEMPLATE", test_plugin.FIXTURES / "report_embed.html"):
            for handler in (tools.handle_compare, tools.handle_accept):
                result = self.call(handler, {})
                self.assertTrue(result["success"], result)
                self.assertEqual(result["paths"]["html"], str(case / "report.html"))
                self.assertEqual(self.embedded(case / "report.html"),
                                 json.loads((case / "report.json").read_text()))

    def test_html_rejects_hard_link_output(self):
        import os
        self.baseline()
        self.call(tools.handle_compare, {})
        case = tools.resolve_data_dir() / "default"
        target = self.home / "protected.html"
        target.write_text("keep")
        os.link(target, case / "report.html")
        with self.assertRaisesRegex(ValueError, "without links"):
            write_report_html(case, test_plugin.FIXTURES / "report_embed.html")
        self.assertEqual(target.read_text(), "keep")

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

