"""Optional HTML errors must preserve successful engine and adapter results."""

import json
from pathlib import Path
from unittest.mock import patch
import unittest

import orphic_tools as tools
from engine import compare
from engine.report_html import DEFAULT_TEMPLATE
from tests import test_plugin


class HtmlFailureTests(unittest.TestCase):
    setUp = test_plugin.PluginTests.setUp
    call = test_plugin.PluginTests.call
    baseline = test_plugin.PluginTests.baseline

    def setUp(self):
        test_plugin.PluginTests.setUp(self)
        self.baseline()
        self.image.paste("black", (10, 10, 30, 30))
        self.case = tools.resolve_data_dir() / "default"

    def compare_valid(self):
        result = compare("default", "http://localhost", self.case.parent)
        self.assertEqual(result["status"], "check", result)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["summary"]["changed_px"], 400)
        self.assertEqual(len(result["boxes"]), 1)
        persisted = json.loads((self.case / "report.json").read_text())
        self.assertEqual(persisted["status"], result["status"])
        self.assertEqual(persisted["summary"], result["summary"])
        self.assertNotIn("html_error", persisted)
        return result

    def test_missing_default_template_keeps_compare_valid(self):
        with patch("engine.report_html.DEFAULT_TEMPLATE", self.home / "missing.html"):
            result = self.compare_valid()
        self.assertNotIn("paths", result)
        self.assertNotIn("html_error", result)

    def test_template_disappears_during_read_records_error(self):
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path == DEFAULT_TEMPLATE:
                raise FileNotFoundError("template disappeared")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            result = self.compare_valid()
        self.assertEqual(result["html_error"], "template disappeared")

    def test_html_write_failure_keeps_compare_valid(self):
        original = Path.write_text

        def write(path, *args, **kwargs):
            if path.name == "report.html":
                raise PermissionError("HTML write denied")
            return original(path, *args, **kwargs)

        with patch.object(Path, "write_text", write):
            result = self.compare_valid()
            adapted = self.call(tools.handle_compare, {})
        self.assertEqual(result["html_error"], "HTML write denied")
        self.assertTrue(adapted["success"], adapted)
        self.assertEqual(adapted["status"], "check")
        self.assertEqual(adapted["html_error"], "HTML write denied")

    def test_bad_json_during_html_read_keeps_compare_valid(self):
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path == self.case / "report.json":
                return "invalid JSON"
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            result = compare("default", "http://localhost", self.case.parent)
        self.assertEqual(result["status"], "check", result)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["summary"]["changed_px"], 400)
        self.assertTrue(result["html_error"])
        self.assertEqual(json.loads((self.case / "report.json").read_text())["status"], "check")

    def test_real_template_success_keeps_compare_valid(self):
        result = self.compare_valid()
        self.assertNotIn("html_error", result)
        page = Path(result["paths"]["html"]).read_text(encoding="utf-8")
        tag = '<script type="application/json" id="orphic-report">'
        self.assertNotIn("<!--ORPHIC_REPORT_JSON-->", page)
        self.assertEqual(page.count(tag), 1)
        embedded = json.loads(page.split(tag, 1)[1].split("</script>", 1)[0])
        self.assertEqual(embedded, json.loads((self.case / "report.json").read_text()))

