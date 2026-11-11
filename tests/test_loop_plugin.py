"""Hermes loop tool schema, output budget and real HTTP round trip."""

import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

from tests.browser_support import require_browser
from unittest.mock import patch

from engine.serve import ReportServer
from engine.url_capture import detect_browser
from tests import test_loop
import orphic_tools as tools


class LoopToolTests(unittest.TestCase):
    setUp = test_loop.LoopTests.setUp
    save_source = test_loop.LoopTests.save_source

    def test_report_url_and_tool_schema_and_response(self):
        home = self.root / "hermes"
        with patch.dict(os.environ, {"HERMES_HOME": str(home)}), patch.object(tools, "resolve_data_dir", return_value=self.root), \
                patch.object(tools, "plugin_config", return_value={"allow_local": True}):
            schema = next(schema for name, schema, handler in tools.TOOL_DEFINITIONS if name == "orphic_loop_step")
            self.assertEqual(schema["parameters"]["required"], ["name", "after_url"])
            self.assertNotIn("allow_local", schema["parameters"]["properties"])
            with ReportServer(self.root) as server:
                response = tools.handle_loop_step({"name": "case", "after_url": "http://127.0.0.1/"})
                result = json.loads(response)
                self.assertTrue(result["success"], result)
                self.assertLess(len(response.encode()), tools.MAX_RESULT_BYTES)
                self.assertEqual(result["stop_condition"], "continue")
                self.assertEqual(result["report_url"], server.base_url + "/case/loop/round-001/report.html")

    def test_large_response_keeps_counts_and_points_to_full_prompt(self):
        result = test_loop.LoopTests.step(self)
        result["per_zone"] = [dict(result["per_zone"][0], id="Z" + str(index)) for index in range(1, 51)]
        result["zone_count"] = result["failing_count"] = 50
        result["follow_up_prompt"] = "Fix the listed pixel regions only. " * 200
        with patch.object(tools, "resolve_data_dir", return_value=self.root), patch.object(test_loop.loop, "loop_step", return_value=result), \
                patch.object(tools, "plugin_config", return_value={"allow_local": True}):
            encoded = tools.handle_loop_step({"name":"case", "after_url":"http://127.0.0.1/"})
        compact = json.loads(encoded)
        self.assertLess(len(encoded.encode()), tools.MAX_RESULT_BYTES)
        self.assertEqual(compact["zone_count"], 50)
        self.assertTrue(compact["prompt_truncated"])
        self.assertGreater(compact["per_zone_omitted"], 0)


class LoopBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if detect_browser(os.environ.get("ORPHIC_BROWSER")) is None:
            raise unittest.SkipTest("Loop E2E requires installed Edge, Chrome or Chromium")
        require_browser()

    def test_two_real_http_rounds_via_hermes_then_done(self):
        state = {"color": "blue"}
        class Pages(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                color = "red" if self.path == "/reference" else state["color"]
                body = ("<style>body{margin:0;background:white}.box{position:absolute;left:40px;top:70px;width:48px;height:32px;background:" + color + "}</style><div class=box></div>").encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        pages = ThreadingHTTPServer(("127.0.0.1", 0), Pages)
        thread = threading.Thread(target=pages.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="oe_loop_e2e_") as temporary, patch.dict(os.environ, {"HERMES_HOME": temporary}), \
                    patch.object(tools, "plugin_config", return_value={"allow_local": True}):
                root = tools.resolve_data_dir()
                root.mkdir()
                base = f"http://127.0.0.1:{pages.server_port}"
                with ReportServer(root) as server:
                    initial = json.loads(tools.handle_compare({"name": "review", "before_url": base + "/reference",
                                         "after_url": base + "/current", "width": 400, "height": 300}))
                    self.assertTrue(initial["success"], initial)
                    self.assertTrue(initial["report_url"].startswith(server.base_url))
                    args = {"name": "review", "after_url": base + "/current"}
                    first = json.loads(tools.handle_loop_step(args))
                    self.assertTrue(first["success"], first)
                    self.assertEqual(first["stop_condition"], "continue")
                    self.assertEqual(first["failing_count"], 1)
                    self.assertTrue(first["follow_up_prompt"])
                    state["color"] = "red"
                    second = json.loads(tools.handle_loop_step(args))
                    self.assertTrue(second["success"], second)
                    self.assertEqual(second["round"], 2)
                    self.assertEqual(second["stop_condition"], "done")
                    self.assertEqual(second["unexpected_count"], 0)
        finally:
            pages.shutdown()
            pages.server_close()
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
