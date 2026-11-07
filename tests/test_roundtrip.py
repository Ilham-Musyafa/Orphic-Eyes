"""Stage 5c synthetic and local-browser regression checks."""

import json
import contextlib
import io
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from engine import baseline, compare
from engine.capture import detect_browser
from engine.requests import validate_requests
from tests.test_locate import texture
import orphic_tools as tools

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class MoveBoxRegressionTests(unittest.TestCase):
    def test_flat_button_horizontal_move_changed_pixel_bounds(self):
        if detect_browser() is None:
            self.skipTest("Installed local browser required for exact file:// reproduction")
        with tempfile.TemporaryDirectory(prefix="orphic-box-repro-") as folder:
            before = baseline("repro", (FIXTURES / "move_104.html").as_uri(), folder)
            self.assertEqual(before["status"], "pass", before)
            result = compare("repro", (FIXTURES / "move_74.html").as_uri(), folder)
            self.assertEqual(result["status"], "check", result)
            rectangles = [{key: b[key] for key in ("x", "y", "w", "h")} for b in result["boxes"]]
            self.assertEqual(rectangles, [{"x": 74, "y": 180, "w": 30, "h": 48},
                                          {"x": 264, "y": 180, "w": 30, "h": 48}])
            self.assertEqual(result["summary"]["changed_px"], 2 * 30 * 48)


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orphic-requests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = Image.new("RGB", (400, 300), "white")
        self.needle = texture()
        self.source = {"x": 40, "y": 70, "w": 48, "h": 32}
        self.target = {**self.source, "x": 100}
        self.before.paste(self.needle, (40, 70))
        self.after = self.before.copy()

        def capture(url, output, **kwargs):
            self.after.save(output)
            return True

        for target, kwargs in (("engine.store.detect_browser", {"return_value": "browser.exe"}),
                               ("engine.store.capture", {"side_effect": capture}),
                               ("engine.capture.capture", {"side_effect": capture})):
            mocked = patch(target, **kwargs)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.assertEqual(baseline("case", "http://localhost", self.root, width=400, height=300)["status"], "pass")
        self.case = self.root / "case"

    def request(self, kind="move", **kwargs):
        result = {"id": "PT-1", "type": kind, "precision": "exact"}
        if kind != "comment":
            result["from"] = dict(self.source)
        if kind == "move":
            result["to"] = dict(self.target)
        return {**result, **kwargs}

    def moved(self, x=100):
        self.after = Image.new("RGB", self.before.size, "white")
        self.after.paste(self.needle, (x, 70))

    def compare(self, requests):
        result = compare("case", "http://localhost", self.root, requests=requests)
        self.assertNotEqual(result["status"], "error", result)
        self.assertEqual(json.loads((self.case / "report.json").read_text()), result)
        return result

    def test_move_done(self):
        self.moved()
        result = self.compare([self.request()])
        self.assertEqual(result["request_results"][0]["status"], "done")
        self.assertEqual(result["request_results"][0]["moved"], {"dx": 60, "dy": 0})
        self.assertEqual(result["request_results"][0]["off"], {"dx": 0, "dy": 0})
        self.assertTrue(result["requests_ok"])
        self.assertEqual(result["status"], "pass")

    def test_move_not_done_with_offset_and_pass_does_not_hide_it(self):
        result = self.compare([self.request()])
        row = result["request_results"][0]
        self.assertEqual(row["status"], "not_done")
        self.assertEqual(row["off"], {"dx": -60, "dy": 0})
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["requests_ok"])

    def test_exact_and_approximate_tolerances(self):
        self.moved(107)
        self.assertEqual(self.compare([self.request()])["request_results"][0]["status"], "not_done")
        self.assertEqual(self.compare([self.request(precision="approximate")])["request_results"][0]["status"], "done")

    def test_move_unknown_hide_done_hide_not_done(self):
        self.after = Image.new("RGB", self.before.size, "white")
        self.assertEqual(self.compare([self.request()])["request_results"][0]["status"], "unknown")
        self.assertEqual(self.compare([self.request("hide")])["request_results"][0]["status"], "done")
        self.after = self.before.copy()
        self.assertEqual(self.compare([self.request("hide")])["request_results"][0]["status"], "not_done")

    def test_revert_and_comment(self):
        result = self.compare([self.request("revert"), self.request("comment", id="PT-2")])
        self.assertEqual([r["status"] for r in result["request_results"]], ["done", "skipped"])
        self.assertTrue(result["requests_ok"])
        self.assertEqual(result["request_counts"], {"done": 1, "not_done": 0, "unknown": 0, "skipped": 1})

    def test_request_done_with_unexpected_side_effect(self):
        self.moved()
        self.after.paste("black", (350, 250, 355, 255))
        result = self.compare([self.request()])
        self.assertTrue(result["requests_ok"])
        self.assertEqual(result["status"], "check")

    def test_flat_and_repeated_are_unknown(self):
        self.after.paste(self.needle, (100, 70))
        self.assertEqual(self.compare([self.request()])["request_results"][0]["status"], "unknown")
        self.before.paste("blue", (40, 70, 88, 102))
        self.before.save(self.case / "baseline.png")
        self.after = self.before.copy()
        self.assertEqual(self.compare([self.request()])["request_results"][0]["status"], "unknown")

    def test_invalid_requests_fail_before_capture(self):
        base = self.request()
        invalid = [None, {}, [base] * 9, [base, base], [{**base, "id": "PT-01"}],
                   [{**base, "id": "PT-0"}], [{**base, "id": "PT-1000"}],
                   [{**base, "type": "resize"}], [{**base, "precision": "maybe"}],
                   [{**base, "from": {**self.source, "x": True}}],
                   [{**base, "to": {**self.target, "w": 49}}],
                   [{**base, "from": {**self.source, "x": 399}}]]
        for requests in invalid:
            with self.subTest(requests=requests), patch("engine.capture.capture") as capture:
                if requests is None:
                    with self.assertRaises(ValueError):
                        validate_requests(requests)
                else:
                    self.assertEqual(compare("case", "http://localhost", self.root, requests=requests)["status"], "error")
                    capture.assert_not_called()

    def test_approve_preserves_request_verdicts(self):
        from engine import approve
        self.moved()
        before = self.compare([self.request()])
        result = approve("case", self.root, all_boxes=True)
        self.assertEqual(result["request_results"], before["request_results"])
        self.assertEqual(result["requests_ok"], before["requests_ok"])

    def test_old_calls_have_no_new_request_fields(self):
        result = compare("case", "http://localhost", self.root)
        self.assertNotIn("request_results", result)
        empty = self.compare([])
        for field in ("schema_version", "name", "status", "summary", "size", "images", "boxes", "ignore_regions"):
            self.assertEqual(result[field], empty[field])

    def test_cli_requests_file_and_invalid_file(self):
        from engine.cli import main
        path = self.root / "requests.json"
        path.write_text(json.dumps([self.request("revert")]))
        argv = ["compare", "case", "http://localhost", "--store", str(self.root), "--requests", str(path)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(argv), 0)
        self.assertTrue(json.loads(output.getvalue())["requests_ok"])
        path.write_text("null")
        with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(argv), 3)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(len(error.getvalue().splitlines()), 1)

    def test_compact_result_preserves_all_eight_ids_and_failing_hint(self):
        raw = self.compare([self.request(id="PT-" + str(i)) for i in range(1, 9)])
        raw["boxes"] = [{"id": i, "x": i * 10, "y": 220, "w": 2, "h": 2, "zone": "bottom-left",
                         "percent": .01, "label": "unexpected", "approved": False} for i in range(1, 21)]
        raw["summary"]["box_count"] = 20
        with patch.object(tools, "resolve_data_dir", return_value=self.root):
            text = tools._result(raw, "case", self.root, "compare")
        result = json.loads(text)
        self.assertLess(len(text.encode()), 4000)
        self.assertEqual([r["id"] for r in result["request_results"]], ["PT-" + str(i) for i in range(1, 9)])
        self.assertTrue(all(r["status"] == "not_done" for r in result["request_results"]))
        self.assertIn("PT-8", result["hint"])
        self.assertNotIn("base64", text.lower())
        self.assertTrue(all("found" in r for r in raw["request_results"]))

    def test_focus_crops_coordinates_and_stale_removal(self):
        self.moved()
        result = self.compare([self.request(), self.request("comment", id="PT-2")])
        folder = self.case / "crops"
        self.assertTrue((folder / "req-PT-1-before.png").is_file())
        self.assertFalse((folder / "req-PT-2-before.png").exists())
        request = next(item for item in result["crops"]["items"] if item["id"] == "req-PT-1")
        self.assertEqual(request["after"]["bbox"], {"x": 84, "y": 54, "w": 80, "h": 64})
        for item in result["crops"]["items"]:
            for side in ("before", "after"):
                with Image.open(self.case / item[side]["path"]) as image:
                    self.assertLessEqual(max(image.size), 640)
        stale = folder / "old-after.png"
        stale.write_bytes(b"stale")
        self.compare([self.request("comment")])
        self.assertFalse(stale.exists())
        self.assertFalse((folder / "req-PT-1-before.png").exists())

    def test_large_focus_crop_caps_size_and_records_scale(self):
        from engine.crops import write_crops
        image = Image.new("RGB", (1200, 900), "white")
        report = {"boxes": [{"id": 1, "x": 0, "y": 0, "w": 1000, "h": 700}]}
        crops = write_crops(self.case, image, image, report)
        info = crops["items"][0]["before"]
        with Image.open(self.case / info["path"]) as saved:
            self.assertEqual(max(saved.size), 640)
            self.assertEqual(saved.size, (info["size"]["width"], info["size"]["height"]))
        self.assertLess(info["scale"], 1)
        self.assertEqual(info["bbox"], {"x": 0, "y": 0, "w": 1016, "h": 716})

    def test_legacy_compare_clears_old_focus_crops(self):
        self.compare([self.request()])
        folder = self.case / "crops"
        self.assertTrue(list(folder.iterdir()))
        result = compare("case", "http://localhost", self.root)
        self.assertNotEqual(result["status"], "error", result)
        self.assertEqual(list(folder.iterdir()), [])
        self.assertNotIn("crops", result)

    def test_expired_budget_never_marks_hide_done(self):
        self.after = Image.new("RGB", self.before.size, "white")
        with patch("engine.requests.REQUEST_BUDGET_SECONDS", 0):
            result = self.compare([self.request("hide"), self.request(id="PT-2")])
        self.assertEqual([row["status"] for row in result["request_results"]], ["unknown", "unknown"])
        self.assertFalse(result["requests_ok"])

    def test_unicode_failure_is_also_under_byte_budget(self):
        text = tools._failure(ValueError("\U0001f4a5" * 600))
        self.assertLess(len(text.encode("utf-8")), 4000)
        self.assertEqual(set(json.loads(text)), {"success", "error", "fix"})

    def test_crop_hard_link_blocks_capture_and_preserves_sentinel(self):
        self.compare([])
        sentinel = self.root / "sentinel.png"
        sentinel.write_bytes(b"do not overwrite")
        link = self.case / "crops" / "stale.png"
        os.link(sentinel, link)
        with patch("engine.capture.capture") as capture:
            result = compare("case", "http://localhost", self.root, requests=[])
        self.assertEqual(result["status"], "error")
        capture.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"do not overwrite")

    def test_crop_directory_and_file_symlinks_rejected(self):
        from engine.crops import validate_crops
        external = self.root / "other"
        external.mkdir()
        folder = self.case / "crops"
        try:
            folder.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Windows symlink privilege unavailable: " + str(exc))
        with self.assertRaises(ValueError):
            validate_crops(self.case)
        folder.unlink()
        folder.mkdir()
        sentinel = external / "sentinel"
        sentinel.write_text("keep")
        (folder / "old.png").symlink_to(sentinel)
        with self.assertRaises(ValueError):
            validate_crops(self.case)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_shift_hint_minus_30(self):
        self.before = Image.new("RGB", (400, 300), "white")
        needle = texture(190, 48)
        self.before.paste(needle, (104, 180))
        self.before.save(self.case / "baseline.png")
        self.after = Image.new("RGB", self.before.size, "white")
        self.after.paste(needle, (74, 180))
        result = compare("case", "http://localhost", self.root, shift_hints=True)
        self.assertNotEqual(result["status"], "error", result)
        shifts = [box["shift"] for box in result["boxes"] if "shift" in box]
        self.assertIn({"dx": -30, "dy": 0}, shifts)
        self.assertEqual(json.loads((self.case / "report.json").read_text()), result)

    def test_flat_diff_has_no_shift_hint(self):
        self.before = Image.new("RGB", (400, 300), "white")
        self.before.paste("blue", (104, 180, 294, 228))
        self.before.save(self.case / "baseline.png")
        self.after = Image.new("RGB", self.before.size, "white")
        self.after.paste("blue", (74, 180, 264, 228))
        result = compare("case", "http://localhost", self.root, shift_hints=True)
        self.assertTrue(all("shift" not in box for box in result["boxes"]))


class ViewportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orphic-presets-")
        self.addCleanup(self.temp.cleanup)
        for patcher in (patch.dict(os.environ, {"HERMES_HOME": self.temp.name}),
                        patch.dict(sys.modules, {"hermes_constants": None})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_preset_dimensions_and_accept_preserve_name(self):
        def capture(url, output, **kwargs):
            Image.new("RGB", (kwargs["width"], kwargs["height"]), "white").save(output)
            return True
        with patch("engine.store.detect_browser", return_value="browser.exe"), \
                patch("engine.store.capture", side_effect=capture), patch("engine.capture.capture", side_effect=capture):
            for preset, size in tools.VIEWPORT_PRESETS.items():
                result = json.loads(tools.handle_baseline({"url": "http://localhost", "name": preset, "viewport": preset}))
                self.assertTrue(result["success"], result)
                self.assertEqual(result["viewport"], {"width": size[0], "height": size[1], "dpr": 1, "preset": preset})
                result = json.loads(tools.handle_compare({"name": preset}))
                self.assertTrue(result["success"], result)
                self.assertEqual(result["meta"]["viewport"]["preset"], preset)
                result = json.loads(tools.handle_accept({"name": preset}))
                self.assertEqual(result["viewport"]["preset"], preset)
                state = json.loads((tools.resolve_data_dir() / preset / tools.STATE_FILE).read_text())
                self.assertEqual(state["viewport_preset"], preset)

    def test_preset_conflicts_and_invalid_values(self):
        for args in ({"viewport": "mobile", "width": 390}, {"viewport": "desktop", "height": 720},
                     {"viewport": None}, {"viewport": []}, {"viewport": "watch"}):
            result = json.loads(tools.handle_baseline({"url": "http://localhost", **args}))
            self.assertFalse(result["success"])
            if "width" in args or "height" in args:
                self.assertIn("never both", result["fix"])

    def test_mismatched_png_size_is_error_not_a_fake_mobile_capture(self):
        def capture(url, output, **kwargs):
            Image.new("RGB", (500, 844)).save(output)
            return True
        with patch("engine.store.detect_browser", return_value="browser.exe"), \
                patch("engine.store.capture", side_effect=capture):
            result = json.loads(tools.handle_baseline({"url": "http://localhost", "viewport": "mobile"}))
        self.assertFalse(result["success"])
        self.assertIn("requested 390x844, got 500x844", result["error"])
        self.assertIn("do not resize", result["fix"])

    def test_real_mobile_png_width_390(self):
        if detect_browser() is None:
            self.skipTest("Real mobile capture requires Edge, Chrome or Chromium")
        result = json.loads(tools.handle_baseline({"url": (FIXTURES / "move_104.html").as_uri(), "viewport": "mobile"}))
        self.assertTrue(result["success"], result)
        with Image.open(result["paths"]["baseline"]) as image:
            self.assertEqual(image.size, (390, 844))
        result = json.loads(tools.handle_compare({}))
        self.assertTrue(result["success"], result)
        with Image.open(result["paths"]["after"]) as image:
            self.assertEqual(image.size, (390, 844))
        result = json.loads(tools.handle_accept({}))
        self.assertEqual(result["viewport"]["preset"], "mobile")


class RealRequestTests(unittest.TestCase):
    def test_file_pages_move_done_wrong_target_and_flat_unknown(self):
        if detect_browser() is None:
            self.skipTest("Real Point & Tell verification requires an installed local browser")
        with tempfile.TemporaryDirectory(prefix="orphic-real-intents-") as home, \
                patch.dict(os.environ, {"HERMES_HOME": home}), \
                patch.dict(sys.modules, {"hermes_constants": None}):
            before = json.loads(tools.handle_baseline({"url": (FIXTURES / "pattern_104.html").as_uri()}))
            self.assertTrue(before["success"], before)
            request = {"id": "PT-1", "type": "move", "precision": "exact",
                       "from": {"x": 104, "y": 180, "w": 190, "h": 48},
                       "to": {"x": 74, "y": 180, "w": 190, "h": 48}}
            result = json.loads(tools.handle_compare({"url": (FIXTURES / "pattern_74.html").as_uri(), "requests": [request]}))
            self.assertTrue(result["success"], result)
            self.assertTrue(result["requests_ok"], result)
            self.assertEqual(result["request_results"][0]["moved"], {"dx": -30, "dy": 0})
            self.assertTrue((Path(result["crops_dir"]) / "req-PT-1-after.png").is_file())
            request["to"]["x"] = 40
            result = json.loads(tools.handle_compare({"url": (FIXTURES / "pattern_74.html").as_uri(), "requests": [request]}))
            self.assertEqual(result["request_results"][0]["status"], "not_done")
            self.assertEqual(result["request_results"][0]["off"], {"dx": 34, "dy": 0})
            self.assertTrue(json.loads(tools.handle_baseline({"url": (FIXTURES / "move_104.html").as_uri()}))["success"])
            result = json.loads(tools.handle_compare({"url": (FIXTURES / "move_74.html").as_uri(), "requests": [request]}))
            self.assertEqual(result["request_results"][0]["status"], "unknown")
            self.assertTrue(all("shift" not in box for box in result["boxes"]))


if __name__ == "__main__":
    unittest.main()
