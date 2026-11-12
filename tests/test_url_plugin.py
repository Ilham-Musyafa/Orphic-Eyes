"""Hermes URL-pair tool schema, errors, and real browser round trip."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from tests.browser_support import require_browser
from unittest.mock import patch

import orphic_tools as tools
from tests.test_url_capture import local_pages, url_capture


class HermesURLTests(unittest.TestCase):
    def test_schema_and_incomplete_or_mixed_pair_arguments(self):
        schema = next(item[1] for item in tools.TOOL_DEFINITIONS if item[0] == "orphic_compare")
        for field in ("before_url", "after_url", "width", "height", "wait_ms", "timeout_ms"):
            self.assertIn(field, schema["parameters"]["properties"])
        self.assertNotIn("allow_local", schema["parameters"]["properties"])
        for args in ({"before_url": "https://example.com"}, {"width": 1440},
                     {"before_url": "https://example.com", "after_url": "https://example.com", "url": "http://localhost"}):
            self.assertFalse(json.loads(tools.handle_compare(args))["success"])

    def test_invalid_pair_error_does_not_leak_secret_or_use_legacy_file_guidance(self):
        result = json.loads(tools.handle_compare({"before_url": "file:///SECRET_QUERY", "after_url": "https://example.com"}))
        self.assertFalse(result["success"])
        self.assertNotIn("SECRET_QUERY", json.dumps(result))
        self.assertIn("public http/https", result["fix"])

    def test_missing_browser_class_is_skipped(self):
        from tests.test_browser import BrowserTests
        with patch("tests.test_browser.detect_browser", return_value=None):
            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromTestCase(BrowserTests).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.skipped), 1)

    def test_installed_but_unusable_browser_class_is_skipped(self):
        from tests.test_browser import BrowserTests
        with patch("tests.test_browser.detect_browser", return_value="installed-browser"), \
                patch("tests.browser_support.probe_browser", return_value="No usable system browser: launch permissions"):
            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromTestCase(BrowserTests).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("launch permissions", result.skipped[0][1])


class URLPluginBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if url_capture.detect_browser(os.environ.get("ORPHIC_BROWSER")) is None:
            raise unittest.SkipTest("Hermes URL E2E requires installed Edge, Chrome or Chromium")
        require_browser()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oe_url_plugin_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_pair_report_and_real_hermes_call(self):
        with local_pages() as server, patch.dict(os.environ, {"HERMES_HOME": str(self.folder)}), \
                patch.object(tools, "plugin_config", return_value={"allow_local": True}):
            base = f"http://127.0.0.1:{server.server_port}"
            result = json.loads(tools.handle_compare({"name": "preview", "before_url": base + "/a?token=SECRET_QUERY",
                                                      "after_url": base + "/b"}))
            self.assertTrue(result["success"], result)
            self.assertEqual(result["summary"]["box_count"], 1)
            self.assertIn("1 changed zone", result["message"])
            self.assertEqual(result["boxes"][0]["bbox"], {"x": 40, "y": 80, "w": 60, "h": 40})
            self.assertLess(len(json.dumps(result).encode()), 4000)
            report_path = Path(result["paths"]["report"])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertNotIn("SECRET_QUERY", report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["images"], {"before": "baseline.png", "after": "current.png", "diff": "diff.png"})
            for path in report["images"].values():
                self.assertTrue((report_path.parent / path).is_file())
            if "html" in result["paths"]:
                html = Path(result["paths"]["html"]).read_text(encoding="utf-8")
                embedded = html.split('<script type="application/json" id="orphic-report">', 1)[1].split('</script>', 1)[0]
                self.assertEqual(json.loads(embedded), report)
                self.assertNotIn("SECRET_QUERY", html)

if __name__ == "__main__":
    unittest.main()
