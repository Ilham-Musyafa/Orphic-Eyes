"""CLI report serving and real browser same-origin pixel access."""

import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from tests.browser_support import require_browser

from PIL import Image

from engine.serve import ReportServer, REGISTRY
from engine._browser_process import launch_options, stop_browser
from engine._devtools import DevTools
from engine.url_capture import _endpoint

capture_module = importlib.import_module("engine.capture")


class ServeCLITests(unittest.TestCase):
    def test_cli_prints_named_report_url_and_stops_on_timeout(self):
        with tempfile.TemporaryDirectory(prefix="oe_serve_cli_") as temporary:
            root = Path(temporary)
            case = root / "named"
            case.mkdir()
            (case / "report.html").write_text("<html>report</html>", encoding="utf-8")
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
        require_browser()

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
</script></body>''', encoding="utf-8")
            with ReportServer(root) as server, tempfile.TemporaryDirectory(prefix="oe_ch_") as profile:
                # Assert the real canvas read independently of Chromium CLI
                # shutdown and inherited stdout pipes (--dump-dom can stall).
                process = subprocess.Popen([self.browser, "--headless=new", "--disable-gpu", "--no-first-run",
                                            "--disable-extensions", "--disable-background-networking",
                                            "--remote-debugging-port=0", "--user-data-dir=" + profile,
                                            "about:blank"], stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, **launch_options())
                client = None
                try:
                    deadline = time.monotonic() + 20
                    client = DevTools(_endpoint(Path(profile), process, deadline), deadline)
                    client.call("Page.enable")
                    client.call("Page.navigate", {"url": server.base_url + "/"})
                    text = ""
                    while time.monotonic() < deadline:
                        text = client.call("Runtime.evaluate", {
                            "expression": "document.body ? document.body.innerText : ''",
                            "returnByValue": True})["result"].get("value", "")
                        if "PIXELS_" in text:
                            break
                        time.sleep(0.02)
                    self.assertIn("PIXELS_OK:255", text)
                    self.assertNotIn("PIXELS_BLOCKED", text)
                finally:
                    stop_browser(process, client)


if __name__ == "__main__":
    unittest.main()
