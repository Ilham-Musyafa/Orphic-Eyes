"""Contract, pixel algorithm, CLI, and input validation tests."""

import contextlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from engine import baseline, capture, compare
from engine.capture import validate_url
from engine.cli import main
from engine.compare import compare_images
from engine.report_json import build_report, write_report

ROOT = Path(__file__).resolve().parents[1]
REPORT_KEYS = {"schema_version", "name", "status", "summary", "size", "images",
               "boxes", "ignore_regions", "meta"}
BOX_KEYS = {"id", "x", "y", "w", "h", "zone", "percent", "label", "approved"}
META_KEYS = {"browser", "os", "viewport", "created_at", "tolerance"}


class PixelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix="test_pixels_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def run_diff(self, before, after, tolerance=0):
        before.save(self.folder / "before.png")
        after.save(self.folder / "after.png")
        return compare_images(self.folder / "before.png", self.folder / "after.png",
                              self.folder / "diff.png", tolerance)

    def test_identical(self):
        image = Image.new("RGB", (100, 100), "white")
        result = self.run_diff(image, image)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["changed_px"], 0)
        self.assertEqual(result["boxes"], [])

    def test_max_channel_threshold_is_strict(self):
        before = Image.new("RGB", (100, 100))
        after = before.copy()
        after.putpixel((5, 6), (0, 0, 11))
        result = self.run_diff(before, after, 10)
        self.assertEqual(result["changed_px"], 1)
        self.assertEqual(result["boxes"][0]["percent"], 0.01)
        self.assertEqual(self.run_diff(before, after, 11)["status"], "pass")

    def test_five_percent_boundary(self):
        before = Image.new("RGB", (100, 100))
        after = before.copy()
        after.paste("white", (0, 0, 100, 5))
        self.assertEqual(self.run_diff(before, after)["status"], "fail")
        after.putpixel((0, 0), (0, 0, 0))
        self.assertEqual(self.run_diff(before, after)["status"], "check")

    def test_status_uses_unrounded_percent(self):
        before = Image.new("RGB", (1000, 1000))
        after = before.copy()
        after.paste("white", (0, 0, 1000, 50))
        after.putpixel((0, 0), (0, 0, 0))
        result = self.run_diff(before, after)
        self.assertEqual(result["changed_percent"], 5.0)
        self.assertEqual(result["status"], "check")

    def test_diagonal_tiles_merge_and_bounds_are_tight(self):
        before = Image.new("RGB", (160, 160))
        after = before.copy()
        for position in ((31, 31), (32, 32), (150, 1), (1, 150)):
            after.putpixel(position, (255, 255, 255))
        boxes = self.run_diff(before, after)["boxes"]
        self.assertEqual([(b["id"], b["x"], b["y"], b["w"], b["h"])
                          for b in boxes],
                         [(1, 150, 1, 1, 1), (2, 31, 31, 2, 2), (3, 1, 150, 1, 1)])

    def test_box_percentage_counts_all_changed_pixels_in_bounds(self):
        before = Image.new("RGB", (224, 224))
        after = before.copy()
        for n in range(0, 224, 32):
            for position in ((n, 0), (n, 192), (0, n), (192, n)):
                after.putpixel(position, (255, 255, 255))
        after.putpixel((96, 96), (255, 255, 255))
        result = self.run_diff(before, after)
        self.assertEqual(len(result["boxes"]), 2)
        self.assertEqual(result["boxes"][0]["percent"],
                         round(result["changed_px"] / (224 * 224) * 100, 3))

    def test_all_nine_zones(self):
        before = Image.new("RGB", (300, 300))
        after = before.copy()
        for y in (10, 150, 290):
            for x in (10, 150, 290):
                after.putpixel((x, y), (255, 255, 255))
        boxes = self.run_diff(before, after)["boxes"]
        self.assertEqual([box["zone"] for box in boxes], [
            "top-left", "top-center", "top-right", "middle-left", "center",
            "middle-right", "bottom-left", "bottom-center", "bottom-right"])

    def test_diff_is_red_over_dimmed_after(self):
        before = Image.new("RGB", (100, 100), (200, 200, 200))
        after = before.copy()
        after.putpixel((7, 8), (201, 200, 200))
        self.run_diff(before, after)
        with Image.open(self.folder / "diff.png") as diff:
            self.assertEqual(diff.getpixel((7, 8)), (255, 0, 0))
            self.assertEqual(diff.getpixel((0, 0)), (70, 70, 70))

    def test_size_mismatch(self):
        result = self.run_diff(Image.new("RGB", (100, 100)),
                               Image.new("RGB", (99, 100)))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["note"], "size_mismatch")
        self.assertEqual(result["boxes"], [])
        self.assertEqual(result["size"], {"width": 99, "height": 100})
        with Image.open(self.folder / "diff.png") as diff:
            self.assertEqual(diff.size, (99, 100))

    def test_bad_inputs_return_errors(self):
        for tolerance in (-1, 256, True, 1.5, "2", None):
            with self.subTest(tolerance=tolerance):
                self.assertEqual(compare_images(None, None, None, tolerance)["status"], "error")
        self.assertEqual(compare_images(None, None, None)["status"], "error")


class InputTests(unittest.TestCase):
    def test_nonlocal_urls_rejected(self):
        for url in ("https://example.com", "http://example.com", "https://localhost",
                    "http://localhost.example.com", "http://127.0.0.1.example.com",
                    "http://user@localhost", "http://localhost:bad", "http://localhost:0",
                    "file://server/share/a.html", "file:////server/share/a.html",
                    "file:///%2Fserver/share/a.html", "http://localhost\\@example.com",
                    "data:text/html,hello", "ftp://localhost", "http://[", "\nhttp://localhost",
                    None, 7):
            with self.subTest(url=url):
                self.assertIsInstance(validate_url(url), str)
                self.assertFalse(capture(url, ROOT / "must_not_exist.png"))
                self.assertEqual(baseline("case", url, ROOT)["status"], "error")
                self.assertEqual(compare("case", url, ROOT)["status"], "error")
        self.assertFalse((ROOT / "must_not_exist.png").exists())

    def test_local_urls_accepted(self):
        for url in ("http://localhost", "http://localhost:8080/a?q=b#c",
                    "http://127.0.0.1:8000/", "file:///C:/local/a%20b.html",
                    "file://localhost/C:/local/a.html"):
            self.assertIsNone(validate_url(url), url)

    def test_bad_dimensions_and_browser_return_false(self):
        for dimension in (0, -1, True, 1.5, "1280", None):
            self.assertFalse(capture("http://localhost", ROOT / "bad.png", width=dimension))
        self.assertFalse(capture("http://localhost", ROOT / "bad.png", browser=ROOT / "missing.exe"))


class CaptureProcessTests(unittest.TestCase):
    def test_reference_flags_timeout_and_store_local_profile(self):
        module = importlib.import_module("engine.capture")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="test_capture_") as folder:
            output = Path(folder) / "current.png"
            with patch.object(module, "detect_browser", return_value="browser.exe"), \
                    patch.object(module.subprocess, "Popen") as popen:
                process = popen.return_value
                process.wait.side_effect = [subprocess.TimeoutExpired("browser", 45), 0]
                process.poll.return_value = 0

                def launched(*args, **kwargs):
                    Image.new("RGB", (1280, 800)).save(output)
                    return process

                popen.side_effect = launched
                self.assertTrue(capture("http://localhost:8000", output))
                process.kill.assert_called_once()
                self.assertEqual(process.wait.call_args_list[0].kwargs, {"timeout": 45})
                command = popen.call_args.args[0]
                self.assertEqual(command[1:9], [
                    "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--force-prefers-reduced-motion",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=2000",
                    "--window-size=1280,800"])
                profile = Path(command[9].split("=", 1)[1])
                self.assertEqual(profile.parent, output.parent)
                self.assertFalse(profile.exists())
                self.assertEqual(command[10:], ["--screenshot=" + str(output), "http://localhost:8000"])
                self.assertEqual(popen.call_args.kwargs["env"]["TEMP"], str(profile))

    def test_stale_screenshot_does_not_count_as_success(self):
        module = importlib.import_module("engine.capture")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="test_stale_") as folder:
            output = Path(folder) / "current.png"
            Image.new("RGB", (10, 10)).save(output)
            with patch.object(module, "detect_browser", return_value="browser.exe"), \
                    patch.object(module.subprocess, "Popen", side_effect=OSError("cannot launch")):
                self.assertFalse(capture("http://localhost", output))
                self.assertFalse(output.exists())
                self.assertEqual(list(Path(folder).iterdir()), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix="test_store_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.current = Image.new("RGB", (1280, 800), "white")

        def fake_capture(url, output, **kwargs):
            self.current.save(output)
            return True

        self.capture_patch = patch("engine.capture.capture", side_effect=fake_capture)
        self.capture_patch.start()
        self.addCleanup(self.capture_patch.stop)
        store_capture_patch = patch("engine.store.capture", side_effect=fake_capture)
        store_capture_patch.start()
        self.addCleanup(store_capture_patch.stop)
        browser_patch = patch("engine.store.detect_browser", return_value="browser.exe")
        browser_patch.start()
        self.addCleanup(browser_patch.stop)

    def make_baseline(self):
        result = baseline("demo", "http://localhost", self.folder)
        self.assertEqual(result["status"], "pass", result)
        return self.folder / "demo"

    def test_end_to_end_schema_exact(self):
        case = self.make_baseline()
        self.current.putpixel((50, 200), (0, 0, 0))
        result = compare("demo", "http://localhost", self.folder, tolerance=1)
        self.assertEqual(result["status"], "check", result)
        report = json.loads((case / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(result, report)
        self.assertEqual(set(report), REPORT_KEYS)
        self.assertEqual(set(report["summary"]), {
            "changed_px", "changed_percent", "box_count", "unexpected_count"})
        self.assertEqual(set(report["size"]), {"width", "height"})
        self.assertEqual(set(report["images"]), {"before", "after", "diff"})
        self.assertEqual(set(report["meta"]), META_KEYS)
        self.assertEqual(set(report["meta"]["viewport"]), {"width", "height"})
        self.assertEqual(set(report["boxes"][0]), BOX_KEYS)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["ignore_regions"], [])
        self.assertEqual(report["boxes"][0]["label"], "unexpected")
        self.assertIs(report["boxes"][0]["approved"], False)
        self.assertEqual(report["meta"]["tolerance"], 1)
        metadata = json.loads((case / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(set(metadata), META_KEYS)
        from datetime import datetime
        self.assertIsNotNone(datetime.fromisoformat(metadata["created_at"]).utcoffset())
        self.assertEqual(set(p.name for p in case.iterdir()), {
            "baseline.png", "metadata.json", "current.png", "diff.png", "report.json"})

    def test_mismatch_report_optional_note(self):
        case = self.make_baseline()
        self.current = Image.new("RGB", (900, 600))
        result = compare("demo", "http://localhost", self.folder)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(set(result), REPORT_KEYS | {"note"})
        self.assertEqual(result["note"], "size_mismatch")
        self.assertEqual(result["boxes"], [])
        self.assertTrue((case / "diff.png").is_file())

    def test_invalid_names_cannot_escape_store(self):
        for name in ("../escape", "..", "a/b", "a\\b", "C:\\escape", "CON", "COM1",
                     "", None, "a:b", ".hidden", "name.", "with space"):
            with self.subTest(name=name):
                self.assertEqual(baseline(name, "http://localhost", self.folder)["status"], "error")
                self.assertEqual(compare(name, "http://localhost", self.folder)["status"], "error")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_missing_and_corrupt_baselines_return_errors(self):
        self.assertEqual(compare("missing", "http://localhost", self.folder)["status"], "error")
        case = self.make_baseline()
        (case / "metadata.json").write_text("bad JSON", encoding="ascii")
        self.assertEqual(compare("demo", "http://localhost", self.folder)["status"], "error")

    def test_hardlinked_output_cannot_modify_other_file(self):
        case = self.make_baseline()
        sentinel = self.folder / "sentinel.json"
        sentinel.write_text("keep", encoding="ascii")
        (case / "report.json").hardlink_to(sentinel)
        self.assertEqual(compare("demo", "http://localhost", self.folder)["status"], "error")
        self.assertEqual(sentinel.read_text(encoding="ascii"), "keep")

    def test_bad_tolerance_does_not_write(self):
        case = self.make_baseline()
        for value in (-1, 256, True, "0"):
            self.assertEqual(compare("demo", "http://localhost", self.folder, value)["status"], "error")
        self.assertFalse((case / "current.png").exists())

    def test_cli_all_status_exit_codes_and_one_line_errors(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(["baseline", "demo", "http://localhost", "--store", str(self.folder)]), 0)
            command = ["compare", "demo", "http://localhost", "--store", str(self.folder)]
            self.assertEqual(main(command), 0)
            self.current.putpixel((50, 200), (0, 0, 0))
            self.assertEqual(main(command), 1)
            self.current = Image.new("RGB", (1280, 800), "black")
            self.assertEqual(main(command), 2)
            self.assertEqual(main(command + ["--tolerance", "invalid"]), 3)
            self.assertEqual(len(errors.getvalue().splitlines()), 1)
        for arguments in ([], ["unknown"], ["baseline"],
                          ["baseline", "bad", "https://example.com", "--store", str(self.folder)]):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(arguments), 3)
                self.assertEqual(len(errors.getvalue().splitlines()), 1)

    def test_report_public_errors(self):
        self.assertEqual(build_report(None, None, None)["status"], "error")
        self.assertEqual(write_report({}, 1)["status"], "error")
        self.assertEqual(write_report({}, self.folder / "missing" / "report.json")["status"], "error")


if __name__ == "__main__":
    unittest.main()
