"""Persistent region/approval commands and classification boundary tests."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from engine import accept, approve, baseline, compare, ignore_add, ignore_list, ignore_remove
from engine.cli import main
from engine.compare import compare_images
from engine.regions import _fingerprint

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"schema_version", "name", "status", "summary", "size", "images", "boxes",
        "ignore_regions", "meta"}


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix="test_stage3_")
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name)
        # Keep legacy result-schema checks independent of optional HTML output.
        template = patch("engine.report_html.DEFAULT_TEMPLATE", self.store / "missing.html")
        template.start()
        self.addCleanup(template.stop)
        self.current = Image.new("RGB", (256, 256), "white")

        def fake_capture(url, output, **kwargs):
            self.current.save(output)
            return True

        for target, kwargs in (
                ("engine.capture.capture", {"side_effect": fake_capture}),
                ("engine.store.capture", {"side_effect": fake_capture}),
                ("engine.store.detect_browser", {"return_value": "browser.exe"})):
            mock = patch(target, **kwargs)
            mock.start()
            self.addCleanup(mock.stop)
        self.assertEqual(baseline("demo", "http://localhost", self.store)["status"], "pass")
        self.case = self.store / "demo"
        self.current.paste("black", (40, 160, 120, 180))

    def compare(self, **kwargs):
        return compare("demo", "http://localhost", self.store, **kwargs)

    def snapshot(self):
        return {str(path.relative_to(self.store)): path.read_bytes()
                for path in self.store.rglob("*") if path.is_file()}

    def cli(self, arguments):
        with contextlib.redirect_stdout(io.StringIO()) as output, \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            code = main(arguments)
        return code, output.getvalue(), errors.getvalue()

    def test_ignore_covers_changes_and_report_schema(self):
        self.assertEqual(ignore_add("demo", self.store, (30, 150, 100, 40), "button")["status"], "pass")
        result = self.compare()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["summary"]["changed_px"], 0)
        self.assertEqual(result["boxes"], [])
        self.assertEqual(set(result), KEYS)
        self.assertEqual(result["ignore_regions"], [
            {"name": "button", "x": 30, "y": 150, "w": 100, "h": 40}])
        self.assertEqual(json.loads((self.case / "config.json").read_text()), result["ignore_regions"])
        with Image.open(self.case / "diff.png") as diff:
            self.assertEqual(diff.getpixel((50, 170)), (0, 0, 0))

    def test_ignore_elsewhere_remains_check(self):
        ignore_add("demo", self.store, (0, 0, 10, 10))
        result = self.compare()
        self.assertEqual(result["status"], "check")
        self.assertEqual(result["summary"]["changed_px"], 1600)

    def test_partial_ignore_masks_exact_pixels(self):
        ignore_add("demo", self.store, (40, 160, 40, 20))
        result = self.compare()
        self.assertEqual(result["summary"]["changed_px"], 800)
        self.assertEqual(result["boxes"][0]["x"], 80)
        self.assertEqual(result["boxes"][0]["w"], 40)

    def test_clipping_labels_list_and_remove(self):
        added = ignore_add("demo", self.store, (250, 250, 30, 30))
        self.assertEqual(added["ignore_regions"], [
            {"name": "region-1", "x": 250, "y": 250, "w": 6, "h": 6}])
        self.assertEqual(ignore_list("demo", self.store), added)
        self.assertEqual(ignore_remove("demo", self.store, "region-1")["ignore_regions"], [])
        self.assertEqual(ignore_remove("demo", self.store, "missing")["status"], "error")
        self.assertEqual(ignore_add("demo", self.store, (300, 300, 4, 4))["status"], "error")

    def test_expected_and_not_persisted(self):
        result = self.compare(expected_regions=[(30, 150, 100, 40)])
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["boxes"][0]["label"], "expected")
        self.assertFalse(result["boxes"][0]["approved"])
        self.assertEqual(result["note"], "only_expected_changes")
        self.assertEqual(result["summary"]["unexpected_count"], 0)
        self.assertEqual(set(result), KEYS | {"note"})
        self.assertEqual(self.compare()["status"], "check")
        self.assertFalse((self.case / "config.json").exists())

    def test_expected_elsewhere(self):
        result = self.compare(expected_regions=[{"x": 0, "y": 0, "w": 10, "h": 10}])
        self.assertEqual(result["status"], "check")
        self.assertEqual(result["boxes"][0]["label"], "unexpected")
        self.assertNotIn("note", result)

    def test_expected_union_boundary_and_no_double_counting(self):
        half = self.compare(expected_regions=[(40, 160, 20, 20), (60, 160, 20, 20)])
        self.assertEqual(half["status"], "pass")
        duplicate = self.compare(expected_regions=[(40, 160, 20, 20), (40, 160, 20, 20)])
        self.assertEqual(duplicate["status"], "check")
        under_half = self.compare(expected_regions=[(40, 160, 39, 20)])
        self.assertEqual(under_half["status"], "check")

    def test_approve_without_browser_and_persistent_match(self):
        self.assertEqual(self.compare()["status"], "check")
        with patch("engine.capture.capture", side_effect=AssertionError("browser forbidden")), \
                patch("engine.store.capture", side_effect=AssertionError("browser forbidden")):
            result = approve("demo", self.store, boxes=[1])
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["note"], "only_expected_changes")
        self.assertTrue(result["boxes"][0]["approved"])
        self.assertEqual(result["summary"]["unexpected_count"], 0)
        self.assertEqual(set(result), KEYS | {"note"})
        records = json.loads((self.case / "approvals.json").read_text())
        self.assertEqual(set(records[0]), {"x", "y", "w", "h", "sha256"})
        self.assertEqual(records, [_fingerprint(self.current, result["boxes"][0])])
        self.assertTrue(self.compare()["boxes"][0]["approved"])
        latest = self.compare()
        self.assertEqual(json.loads((self.case / "report.json").read_text()), latest)

    def test_changed_crop_same_bounds_is_not_approved(self):
        original = self.compare()
        approve("demo", self.store, [1])
        self.current.paste("red", (40, 160, 120, 180))
        result = self.compare()
        for field in ("x", "y", "w", "h"):
            self.assertEqual(original["boxes"][0][field], result["boxes"][0][field])
        self.assertFalse(result["boxes"][0]["approved"])
        self.assertEqual(result["status"], "check")

    def test_approve_preserves_expected_labels_for_that_report(self):
        self.current.putpixel((220, 220), (0, 0, 0))
        result = self.compare(expected_regions=[(40, 160, 80, 20)])
        self.assertEqual(result["status"], "check")
        approved = approve("demo", self.store, [2])
        self.assertEqual(approved["status"], "pass", approved)
        self.assertEqual(approved["boxes"][0]["label"], "expected")
        self.assertFalse(approved["boxes"][0]["approved"])
        self.assertEqual(self.compare()["status"], "check")

    def test_approve_all_deduplicates_and_invalid_ids_write_nothing(self):
        self.current.putpixel((220, 220), (0, 0, 0))
        self.compare()
        before = self.snapshot()
        for boxes in ([3], [0], [-1], [True], ["1"], None):
            self.assertEqual(approve("demo", self.store, boxes)["status"], "error")
            self.assertEqual(self.snapshot(), before)
        result = approve("demo", self.store, all_boxes=True)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(all(box["approved"] for box in result["boxes"]))
        approve("demo", self.store, [1, 1])
        self.assertEqual(len(json.loads((self.case / "approvals.json").read_text())), 2)

    def test_approve_refuses_stale_layout(self):
        self.compare()
        ignore_add("demo", self.store, (40, 160, 40, 20))
        before = self.snapshot()
        self.assertEqual(approve("demo", self.store, [1])["status"], "error")
        self.assertEqual(self.snapshot(), before)

    def test_accept_clears_approvals_preserves_config_and_updates_viewport(self):
        self.compare()
        approve("demo", self.store, all_boxes=True)
        ignore_add("demo", self.store, (0, 0, 10, 10), "clock")
        expected_bytes = (self.case / "current.png").read_bytes()
        with patch("engine.capture.capture", side_effect=AssertionError("browser forbidden")):
            result = accept("demo", self.store)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual((self.case / "baseline.png").read_bytes(), expected_bytes)
        self.assertEqual(json.loads((self.case / "approvals.json").read_text()), [])
        self.assertEqual(len(ignore_list("demo", self.store)["ignore_regions"]), 1)
        self.assertEqual(result["meta"]["viewport"], {"width": 256, "height": 256})
        self.assertEqual(self.compare()["status"], "pass")

    def test_invalid_regions_no_writes_and_one_line_cli_errors(self):
        before = self.snapshot()
        for region in ((-1, 0, 1, 1), (0, -1, 1, 1), (0, 0, 0, 1), (0, 0, 1, -1),
                       (True, 0, 1, 1), ("text", 0, 1, 1), (0.5, 0, 1, 1), {}, None):
            self.assertEqual(ignore_add("demo", self.store, region)["status"], "error")
            self.assertEqual(self.compare(expected_regions=[region])["status"], "error")
            self.assertEqual(self.snapshot(), before)
        for region in ("-1,0,1,1", "0,0,0,1", "0,0,text,1", "0,0,1", "1.5,0,1,1"):
            for arguments in (["ignore", "add", "demo", "--region=" + region],
                              ["compare", "demo", "http://localhost", "--expect=" + region]):
                code, output, error = self.cli([*arguments, "--store", str(self.store)])
                self.assertEqual(code, 3)
                self.assertEqual(output, "")
                self.assertEqual(len(error.splitlines()), 1)
                self.assertEqual(self.snapshot(), before)

    def test_maximum_50_ignore_regions_and_unique_labels(self):
        for i in range(50):
            self.assertEqual(ignore_add("demo", self.store, (0, 0, 1, 1))["status"], "pass")
        before = self.snapshot()
        code, output, error = self.cli(["ignore", "add", "demo", "--store", str(self.store),
                                       "--region", "0,0,1,1"])
        self.assertEqual(code, 3)
        self.assertIn("50", error)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(ignore_add("demo", self.store, (1, 1, 1, 1), "region-1")["status"], "error")

    def test_path_labels_and_names_cannot_escape(self):
        before = self.snapshot()
        for label in ("../outside", "a/b", "a\\b", "a:b", "", "x" * 41, "with space", "\u00e9"):
            self.assertEqual(ignore_add("demo", self.store, (0, 0, 1, 1), label)["status"], "error")
            self.assertEqual(ignore_remove("demo", self.store, label)["status"], "error")
        for name in ("../outside", "a/b", "a\\b", "CON"):
            self.assertEqual(ignore_list(name, self.store)["status"], "error")
            self.assertEqual(approve(name, self.store, all_boxes=True)["status"], "error")
            self.assertEqual(accept(name, self.store)["status"], "error")
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_config_or_approvals_fails_before_capture(self):
        for filename, value in (("config.json", [{"name": "a", "x": -1, "y": 0, "w": 1, "h": 1}]),
                                ("config.json", [{}] * 51), ("approvals.json", [{"sha256": "bad"}])):
            path = self.case / filename
            path.write_text(json.dumps(value), encoding="ascii")
            before = self.snapshot()
            with patch("engine.capture.capture") as capture:
                self.assertEqual(self.compare()["status"], "error")
                capture.assert_not_called()
            self.assertEqual(self.snapshot(), before)
            path.unlink()

    def test_config_and_approvals_links_are_rejected(self):
        for filename in ("config.json", "approvals.json"):
            sentinel = self.store / "sentinel.json"
            sentinel.write_text("[]", encoding="ascii")
            target = self.case / filename
            target.hardlink_to(sentinel)
            before = self.snapshot()
            self.assertEqual(ignore_add("demo", self.store, (0, 0, 1, 1))["status"], "error")
            self.assertEqual(self.compare()["status"], "error")
            self.assertEqual(self.snapshot(), before)
            target.unlink()

    def test_atomic_replace_failure_keeps_json_and_cleans_temp(self):
        ignore_add("demo", self.store, (0, 0, 1, 1), "first")
        before = self.snapshot()
        with patch("engine.store.os.replace", side_effect=OSError("replace blocked")):
            result = ignore_add("demo", self.store, (1, 1, 1, 1), "second")
        self.assertEqual(result["status"], "error")
        self.assertEqual(self.snapshot(), before)
        self.compare()
        before = self.snapshot()
        with patch("engine.store.os.replace", side_effect=OSError("replace blocked")):
            self.assertEqual(approve("demo", self.store, [1])["status"], "error")
        self.assertEqual(self.snapshot(), before)

    def test_new_cli_commands(self):
        base = ["demo", "--store", str(self.store)]
        self.assertEqual(self.cli(["ignore", "add", *base, "--region", "0,0,10,10", "--label", "clock"])[0], 0)
        self.assertEqual(self.cli(["ignore", "list", *base])[0], 0)
        self.assertEqual(self.cli(["ignore", "remove", *base, "--label", "clock"])[0], 0)
        self.assertEqual(self.cli(["compare", "demo", "http://localhost", "--store", str(self.store),
                                   "--expect", "40,160,40,20", "--expect", "80,160,40,20"])[0], 0)
        self.compare()
        self.assertEqual(self.cli(["approve", *base, "--box", "1"])[0], 0)
        self.assertEqual(self.cli(["approve", *base, "--all"])[0], 0)
        self.assertEqual(self.cli(["approve", *base, "--all", "--box", "1"])[0], 3)
        self.assertEqual(self.cli(["accept", *base])[0], 0)

    def test_fail_uses_only_unexpected_unapproved_cluster_pixels(self):
        before = Image.new("RGB", (256, 256))
        after = before.copy()
        after.paste("white", (0, 0, 128, 128))
        after.paste("white", (200, 200, 210, 210))
        before.save(self.case / "baseline.png")
        after.save(self.case / "current.png")
        paths = (self.case / "baseline.png", self.case / "current.png", self.case / "diff.png")
        self.assertEqual(compare_images(*paths)["status"], "fail")
        expected = compare_images(*paths, expected_regions=[(0, 0, 128, 128)])
        self.assertEqual(expected["status"], "check")
        self.assertGreater(expected["changed_percent"], 5)
        approved = compare_images(*paths, approvals=[_fingerprint(after, expected["boxes"][0])])
        self.assertEqual(approved["status"], "check")

    def test_overlap_bounds_do_not_charge_expected_cluster_pixels(self):
        before = Image.new("RGB", (256, 256))
        after = before.copy()
        # Sparse outer ring is one tile cluster; the inner block is separate.
        for n in range(0, 225, 32):
            for pos in ((n, 0), (n, 224), (0, n), (224, n)):
                after.putpixel(pos, (255, 255, 255))
        after.paste("white", (96, 96, 160, 160))
        before.save(self.case / "baseline.png")
        after.save(self.case / "current.png")
        result = compare_images(self.case / "baseline.png", self.case / "current.png",
                                self.case / "diff.png", expected_regions=[(96, 96, 64, 64)])
        self.assertEqual(result["status"], "check")
        self.assertGreater(result["changed_percent"], 5)


if __name__ == "__main__":
    unittest.main()
