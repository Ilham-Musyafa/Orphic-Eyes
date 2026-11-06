"""Real installed-browser tests; browser absence is a failure, not a skip."""

import json
from pathlib import Path
import tempfile
import unittest

from engine import baseline, capture, compare
from engine.capture import detect_browser
from engine.compare import compare_images

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix="test_browser_")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.browser = detect_browser()
        if cls.browser is None:
            raise AssertionError("integration tests require installed Edge or Chrome")
        for shot, page, width in (("a1", "page_a", 1280), ("a2", "page_a", 1280),
                                  ("b", "page_b", 1280), ("r1", "page_real", 1280),
                                  ("r2", "page_real", 1280), ("small", "page_a", 960)):
            if not capture((FIXTURES / (page + ".html")).as_uri(), cls.folder / (shot + ".png"),
                           browser=cls.browser, width=width):
                raise AssertionError("browser capture failed for " + shot + ": " + cls.browser)

    def diff(self, before, after):
        return compare_images(self.folder / (before + ".png"),
                              self.folder / (after + ".png"), self.folder / "diff.png")

    def test_same_page_twice(self):
        result = self.diff("a1", "a2")
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["changed_px"], 0)
        self.assertEqual(result["boxes"], [])

    def test_button_shift(self):
        result = self.diff("a1", "b")
        self.assertEqual(result["status"], "check", result)
        self.assertGreater(result["changed_px"], 0)
        self.assertLess(result["changed_percent"], 5)
        self.assertGreaterEqual(len(result["boxes"]), 1)
        for box in result["boxes"]:
            self.assertGreaterEqual(box["x"], 30)
            self.assertLessEqual(box["x"] + box["w"], 360)
            self.assertGreaterEqual(box["y"], 150)
            self.assertLessEqual(box["y"] + box["h"], 340)

    def test_realistic_page_twice(self):
        result = self.diff("r1", "r2")
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["changed_px"], 0)
        self.assertEqual(result["boxes"], [])

    def test_very_different_pages(self):
        self.assertEqual(self.diff("a1", "r1")["status"], "fail")

    def test_different_viewports(self):
        result = self.diff("a1", "small")
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["note"], "size_mismatch")
        self.assertEqual(result["boxes"], [])

    def test_real_store_workflow(self):
        url = (FIXTURES / "page_a.html").as_uri()
        result = baseline("workflow", url, self.folder)
        self.assertEqual(result["status"], "pass", result)
        report = compare("workflow", url, self.folder)
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["summary"]["changed_px"], 0)
        self.assertEqual(json.loads((self.folder / "workflow" / "report.json").read_text()), report)


if __name__ == "__main__":
    unittest.main()
