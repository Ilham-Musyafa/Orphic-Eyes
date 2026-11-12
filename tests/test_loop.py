"""Fixed-goal loop state, persistence, stop conditions and HTTP browser E2E."""

import importlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from PIL import Image

from engine import loop_step
from engine.serve import ReportServer
from engine.store import _atomic_json, _metadata
from engine.url_capture import CaptureError, detect_browser
from tests.test_locate import texture

loop = importlib.import_module("engine.loop")


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oe_loop_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = self.root / "case"
        self.case.mkdir()
        self.reference = Image.new("RGB", (400, 300), "white")
        self.initial = self.reference.copy()
        self.initial.paste("blue", (40, 70, 88, 102))
        self.save_source()
        self.latest = self.initial.copy()
        def capture(url, output, **kwargs):
            self.latest.save(output)
            return Path(output)
        self.patcher = patch.object(loop, "capture", side_effect=capture)
        self.capture = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def save_source(self):
        self.reference.save(self.case / "baseline.png")
        self.initial.save(self.case / "current.png")
        _atomic_json(self.case / "metadata.json", _metadata("browser.exe", *self.reference.size, 0))

    def step(self, **kwargs):
        result = loop_step("case", "http://127.0.0.1/page?token=SECRET_QUERY", self.root,
                           allow_local=True, **kwargs)
        self.assertTrue(result.get("success"), result)
        return result

    def test_unchanged_wrong_round_then_fixed_round_done_with_immutable_reference(self):
        first = self.step()
        self.assertEqual(first["round"], 1)
        self.assertEqual(first["status"], "pass")  # No *new* changes, but the goal is still wrong.
        self.assertEqual(first["stop_condition"], "continue")
        self.assertEqual(first["per_zone"][0]["status"], "not_done")
        self.assertTrue(first["per_zone"][0]["still_changed"])
        self.assertIn("Restore this area", first["follow_up_prompt"])
        self.latest = self.reference.copy()
        Image.new("RGB", self.reference.size, "black").save(self.case / "baseline.png")
        second = self.step()
        self.assertEqual(second["round"], 2)
        self.assertEqual(second["stop_condition"], "done")
        self.assertTrue(second["should_stop"])
        self.assertEqual(second["per_zone"][0]["status"], "done")
        self.assertEqual(second["unexpected_count"], 0)
        with Image.open(second["paths"]["previous"]) as previous:
            self.assertEqual(previous.getpixel((45, 75)), (0, 0, 255))
        for result in (first, second):
            self.assertNotIn("SECRET_QUERY", json.dumps(result))
            self.assertNotIn("SECRET_QUERY", Path(result["paths"]["round"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(result["paths"]["prompt"]).is_file())
            self.assertEqual(json.loads(Path(result["paths"]["report"]).read_text(encoding="utf-8"))["schema_version"], 1)

    def test_default_max_rounds_and_stopped_session_does_not_capture_again(self):
        for number in range(1, 4):
            result = self.step()
            self.assertEqual(result["round"], number)
        self.assertEqual(result["max_rounds"], 3)
        self.assertEqual(result["stop_condition"], "max_rounds")
        again = self.step()
        self.assertTrue(again["already_stopped"])
        self.assertEqual(again["round"], 3)
        self.assertEqual(self.capture.call_count, 3)

    def test_configured_max_rounds_is_fixed(self):
        result = self.step(max_rounds=1)
        self.assertEqual(result["stop_condition"], "max_rounds")
        result = loop_step("case", "http://127.0.0.1/", self.root, max_rounds=2, allow_local=True)
        self.assertEqual(result["status"], "error")
        self.assertIn("fixed", result["error"])

    def test_persistent_unexpected_zones_and_their_resolution(self):
        self.latest.paste("red", (320, 250, 340, 270))
        first = self.step()
        second = self.step()
        self.assertEqual(first["unexpected_count"], 1)
        self.assertEqual(second["unexpected_count"], 1)
        self.assertEqual(second["summary"]["changed_px"], 0)
        self.assertIn("Unexpected", second["follow_up_prompt"])
        self.latest = self.reference.copy()
        self.assertEqual(self.step()["stop_condition"], "done")

    def request(self, kind="move"):
        request = {"id": "PT-1", "type": kind, "precision": "exact",
                   "from": {"x": 40, "y": 70, "w": 48, "h": 32}}
        if kind == "move":
            request["to"] = {"x": 100, "y": 70, "w": 48, "h": 32}
        return request

    def textured_source(self):
        self.reference.paste(texture(), (40, 70))
        self.initial = self.reference.copy()
        self.latest = self.initial.copy()
        self.save_source()

    def test_explicit_move_requests_reuse_original_anchor_and_existing_matcher(self):
        # A small real matcher fixture leaves ample headroom under the existing
        # search deadline even on shared CI hosts; no engine budget is changed.
        self.reference = Image.new("RGB", (160, 120), "white")
        needle = texture(16, 16)
        self.reference.paste(needle, (20, 30))
        self.initial = self.latest = self.reference.copy()
        self.save_source()
        request = {"id": "PT-1", "type": "move", "precision": "exact",
                   "from": {"x": 20, "y": 30, "w": 16, "h": 16},
                   "to": {"x": 60, "y": 30, "w": 16, "h": 16}}
        first = self.step(requests=[request])
        self.assertEqual(first["per_zone"][0]["status"], "not_done")
        self.assertIn("x=60", first["follow_up_prompt"])
        self.latest = Image.new("RGB", (160, 120), "white")
        self.latest.paste(needle, (60, 30))
        second = self.step()
        self.assertEqual(second["stop_condition"], "done")
        self.assertEqual(second["per_zone"][0]["status"], "done")

    def test_unknown_match_and_comments_require_human(self):
        self.textured_source()
        self.latest = Image.new("RGB", (400, 300), "white")
        result = self.step(requests=[self.request()])
        self.assertEqual(result["stop_condition"], "needs_human")
        self.assertEqual(result["per_zone"][0]["status"], "unknown")
        self.assertIn("Stop automatic retries", result["follow_up_prompt"])
        # A distinct existing target for a comment-only session.
        other = self.root / "comments"
        other.mkdir()
        for name in ("baseline.png", "current.png", "metadata.json"):
            import shutil
            shutil.copyfile(self.case / name, other / name)
        result = loop_step("comments", "http://127.0.0.1/", self.root,
                           requests=[{"id": "PT-1", "type": "comment"}], allow_local=True)
        self.assertEqual(result["stop_condition"], "needs_human")

    def test_viewport_mismatch_needs_human(self):
        self.latest = self.latest.resize((420, 300))
        result = self.step()
        self.assertEqual(result["stop_condition"], "needs_human")
        self.assertEqual(result["per_zone"][0]["status"], "unknown")

    def test_capture_failure_commits_no_round_and_releases_lock(self):
        self.capture.side_effect = CaptureError("URL capture timed out")
        result = loop_step("case", "http://127.0.0.1/", self.root, allow_local=True)
        self.assertEqual(result["status"], "error")
        self.assertFalse((self.case / ".loop-lock").exists())
        self.assertEqual(list((self.case / "loop").glob("round-*")), [])

    def test_invalid_urls_and_arguments_do_not_initialize_session(self):
        for url in ("file:///SECRET_QUERY", "javascript:SECRET_QUERY", "data:text/plain,SECRET_QUERY", "http://127.0.0.1/?SECRET_QUERY"):
            result = loop_step("case", url, self.root)
            self.assertEqual(result["status"], "error")
            self.assertNotIn("SECRET_QUERY", json.dumps(result))
        self.assertFalse((self.case / "loop").exists())
        for value in (0, True, "3", -1):
            result = loop_step("case", "http://127.0.0.1/", self.root, max_rounds=value, allow_local=True)
            self.assertEqual(result["status"], "error")

    def test_unsafe_loop_directory_and_busy_lock_are_preserved(self):
        (self.case / ".loop-lock").write_text("other process", encoding="utf-8")
        result = loop_step("case", "http://127.0.0.1/", self.root, allow_local=True)
        self.assertIn("busy", result["error"])
        self.assertEqual((self.case / ".loop-lock").read_text(encoding="utf-8"), "other process")
        (self.case / ".loop-lock").unlink()
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.case / "loop").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Symlinks unavailable: " + str(exc))
        result = loop_step("case", "http://127.0.0.1/", self.root, allow_local=True)
        self.assertIn("redirect", result["error"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_round_links_to_running_report_server(self):
        with ReportServer(self.root) as server:
            result = self.step()
            self.assertEqual(result["report_url"], server.base_url + "/case/loop/round-001/report.html")


if __name__ == "__main__":
    unittest.main()
