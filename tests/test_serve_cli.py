"""CLI report serving and real browser same-origin pixel access."""

import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from engine.serve import ReportServer, REGISTRY

capture_module = importlib.import_module("engine.capture")


class ServeCLITests(unittest.TestCase):
    def test_cli_prints_named_report_url_and_stops_on_timeout(self):
        with tempfile.TemporaryDirectory(prefix="oe_serve_cli_") as temporary:
            root = Path(temporary)
            case = root / "named"
            case.mkdir()
            (case / "report.html").write_text("<html>report</html>")
            result = subprocess.run([sys.executable, "-B", "-m", "engine.cli", "serve", "--store", str(root),
                                     "--name", "named", "--timeout", "0.15"],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout.strip(), r"^http://127\.0\.0\.1:[0-9]+/named/report\.html$")
            self.assertFalse((root / REGISTRY).exists())


class ServeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browser = capture_module.detect_browser(os.environ.get("ORPHIC_BROWSER"))
        if cls.browser is None:
            raise unittest.SkipTest("Same-origin canvas check requires installed Edge, Chrome or Chromium")

    def test_http_report_can_read_adjacent_image_pixels(self):
        with tempfile.TemporaryDirectory(prefix="oe_http_") as temporary:
            root = Path(temporary)
            case = root / "nested"
            case.mkdir()
            Image.new("RGB", (4, 4), "red").save(case / "baseline.png")
            # A test-owned report fixture exercises the precise browser-origin
            # capability Verify needs, without modifying the application UI.
            (case / "report.html").write_text('''<!doctype html><body><script>
const image = new Image();
image.onload = () => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 4;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(image, 0, 0);
  try { document.body.append('PIXELS_OK:' + ctx.getImageData(0, 0, 1, 1).data[0]); }
  catch (error) { document.body.append('PIXELS_BLOCKED'); }
};
image.src = 'baseline.png';
</script></body>''')
            with ReportServer(root) as server, tempfile.TemporaryDirectory(prefix="oe_ch_") as profile:
                completed = subprocess.run([self.browser, "--headless=new", "--disable-gpu", "--no-first-run",
                                             "--disable-extensions", "--disable-background-networking",
                                             "--virtual-time-budget=2000", "--user-data-dir=" + profile,
                                             "--dump-dom", server.base_url + "/"],
                                            capture_output=True, text=True, timeout=20)
                self.assertEqual(completed.returncode, 0)
                self.assertIn("</script>PIXELS_OK:255", completed.stdout)
                self.assertNotIn("</script>PIXELS_BLOCKED", completed.stdout)


if __name__ == "__main__":
    unittest.main()
