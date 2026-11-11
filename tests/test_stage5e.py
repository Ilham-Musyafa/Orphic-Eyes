"""Product naming and optional report-page freshness regressions."""

from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import orphic_tools as tools
from engine import store
from engine.report_json import write_report
from tests import test_plugin
from tests.test_plugin import FakeContext, ROOT, load_package


class NamingTests(unittest.TestCase):
    def test_tracked_runtime_and_documentation_use_current_name(self):
        excluded = {f"docs/stage-5{stage}-notes.md" for stage in ("c", "d", "e")}
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        matches = []
        for filename in tracked.decode("utf-8").split("\0"):
            if filename in excluded or Path(filename).suffix.lower() not in {
                    ".py", ".yaml", ".md", ".txt", ".html"}:
                continue
            if ("sight" + "diff") in (ROOT / filename).read_text(encoding="utf-8").lower():
                matches.append(filename)
        self.assertEqual(matches, [])

    def test_manifest_and_registration_identifiers(self):
        manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertEqual(manifest.splitlines()[0], "name: orphic-eyes")
        block = manifest.split("provides_tools:\n", 1)[1].split("provides_hooks:", 1)[0]
        names = [line.strip()[2:] for line in block.splitlines() if line.strip().startswith("- ")]
        expected = ["orphic_" + action for action in ("baseline", "compare", "loop_step", "approve", "accept", "ignore")]
        self.assertCountEqual(names, expected)
        package = "_orphic_naming_test"
        self.addCleanup(lambda: [sys.modules.pop(key, None) for key in list(sys.modules)
                                if key == package or key.startswith(package + ".")])
        context = FakeContext()
        load_package(package).register(context)
        self.assertEqual(set(context.tools), set(expected))
        self.assertTrue(all(entry[0] == "orphic" for entry in context.tools.values()))
        self.assertEqual(set(context.commands), {"orphic"})


class HtmlFreshnessTests(unittest.TestCase):
    setUp = test_plugin.PluginTests.setUp
    call = test_plugin.PluginTests.call
    baseline = test_plugin.PluginTests.baseline

    def assert_page_matches(self, case):
        page = (case / "report.html").read_text(encoding="utf-8")
        embedded = page.split('<script type="application/json" id="orphic-report">', 1)[1].split('</script>', 1)[0]
        self.assertEqual(json.loads(embedded), json.loads((case / "report.json").read_text()))

    def test_every_operation_refreshes_html_and_baseline_removes_it(self):
        self.baseline()
        self.image.paste("black", (10, 10, 30, 30))
        case = tools.resolve_data_dir() / "default"
        region = {"x": 100, "y": 100, "w": 20, "h": 20}
        operations = [(tools.handle_compare, {}), (tools.handle_approve, {"all": True}),
                      (tools.handle_ignore, {"action": "add", "region": region}),
                      (tools.handle_ignore, {"action": "remove", "region": region}),
                      (tools.handle_accept, {}), (tools.handle_compare, {})]
        with patch("engine.report_html.DEFAULT_TEMPLATE", test_plugin.FIXTURES / "report_embed.html"):
            for handler, args in operations:
                with self.subTest(operation=handler.__name__, args=args):
                    if (case / "report.html").exists():
                        (case / "report.html").write_text("stale page", encoding="utf-8")
                    result = self.call(handler, args)
                    self.assertTrue(result["success"], result)
                    self.assertEqual(result["paths"]["html"], str(case / "report.html"))
                    self.assert_page_matches(case)
            self.baseline()
            self.assertFalse((case / "report.json").exists())
            self.assertFalse((case / "report.html").exists())

    def test_engine_baseline_also_removes_report_page(self):
        self.baseline()
        case = tools.resolve_data_dir() / "default"
        with patch("engine.report_html.DEFAULT_TEMPLATE", test_plugin.FIXTURES / "report_embed.html"):
            self.call(tools.handle_compare, {})
            self.assertTrue((case / "report.html").exists())
            result = store.baseline("default", "http://localhost", case.parent)
        self.assertEqual(result["status"], "pass")
        self.assertFalse((case / "report.json").exists())
        self.assertFalse((case / "report.html").exists())

    def test_direct_report_writer_refreshes_without_changing_json_schema(self):
        self.baseline()
        self.call(tools.handle_compare, {})
        case = tools.resolve_data_dir() / "default"
        report = json.loads((case / "report.json").read_text())
        with patch("engine.report_html.DEFAULT_TEMPLATE", test_plugin.FIXTURES / "report_embed.html"):
            result = write_report(report, case / "report.json")
        self.assertIn("html", result["paths"])
        self.assert_page_matches(case)
        self.assertEqual(json.loads((case / "report.json").read_text()), report)
        self.assertNotIn("paths", report)

    def test_no_template_omits_html_for_approve_ignore_and_accept(self):
        self.baseline()
        self.image.paste("black", (10, 10, 30, 30))
        region = {"x": 100, "y": 100, "w": 20, "h": 20}
        with patch("engine.report_html.DEFAULT_TEMPLATE", self.home / "missing.html"):
            for handler, args in [(tools.handle_compare, {}),
                                  (tools.handle_approve, {"all": True}),
                                  (tools.handle_ignore, {"action": "add", "region": region}),
                                  (tools.handle_ignore, {"action": "remove", "region": region}),
                                  (tools.handle_accept, {})]:
                result = self.call(handler, args)
                self.assertTrue(result["success"], result)
                self.assertNotIn("html", result["paths"])
        self.assertFalse((tools.resolve_data_dir() / "default" / "report.html").exists())
