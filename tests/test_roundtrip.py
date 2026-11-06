"""Stage 5c synthetic and local-browser regression checks."""

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from engine import baseline, compare
from engine.capture import detect_browser

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class MoveBoxRegressionTests(unittest.TestCase):
    def test_flat_button_horizontal_move_changed_pixel_bounds(self):
        if detect_browser() is None:
            self.skipTest("Installed local browser required for exact file:// reproduction")
        with tempfile.TemporaryDirectory(prefix="sightdiff-box-repro-") as folder:
            before = baseline("repro", (FIXTURES / "move_104.html").as_uri(), folder)
            self.assertEqual(before["status"], "pass", before)
            result = compare("repro", (FIXTURES / "move_74.html").as_uri(), folder)
            self.assertEqual(result["status"], "check", result)
            rectangles = [{key: b[key] for key in ("x", "y", "w", "h")} for b in result["boxes"]]
            self.assertEqual(rectangles, [{"x": 74, "y": 180, "w": 30, "h": 48},
                                          {"x": 264, "y": 180, "w": 30, "h": 48}])
            self.assertEqual(result["summary"]["changed_px"], 2 * 30 * 48)


if __name__ == "__main__":
    unittest.main()
