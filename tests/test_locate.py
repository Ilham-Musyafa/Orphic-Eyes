"""Synthetic matcher calibration and ambiguity regressions."""

import random
import unittest

from PIL import Image

from engine.locate import find_crop


def texture(width=48, height=32, seed=9):
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height))
    image.putdata([(v, v, v) for v in (rng.randrange(256) for _ in range(width * height))])
    return image


class LocateTests(unittest.TestCase):
    def test_off_grid_exact_match_and_coordinate_space(self):
        needle = texture()
        haystack = Image.new("RGB", (400, 240), "white")
        haystack.paste(needle, (173, 93))
        pos, score, unique = find_crop(haystack, needle, {"x": 91, "y": 33, "w": 220, "h": 160})
        self.assertEqual(pos, (173, 93))
        self.assertEqual(score, 1)
        self.assertTrue(unique)

    def test_duplicate_and_flat_are_not_unique(self):
        needle = texture()
        haystack = Image.new("RGB", (280, 180), "white")
        haystack.paste(needle, (40, 50))
        haystack.paste(needle, (140, 50))
        self.assertFalse(find_crop(haystack, needle, {"x": 0, "y": 0, "w": 260, "h": 150})[2])
        needle = Image.new("RGB", (190, 48), "blue")
        haystack.paste(needle, (40, 50))
        self.assertFalse(find_crop(haystack, needle, {"x": 0, "y": 0, "w": 280, "h": 180})[2])

    def test_window_is_respected_and_absent_is_low_score(self):
        needle = texture()
        haystack = Image.new("RGB", (400, 240), "white")
        haystack.paste(needle, (300, 180))
        pos, score, unique = find_crop(haystack, needle, {"x": 0, "y": 0, "w": 160, "h": 130})
        self.assertLess(score, .92)
        self.assertFalse(unique)
        self.assertEqual(find_crop(haystack, needle, {"x": 399, "y": 239, "w": 2, "h": 2}),
                         (None, 0.0, False))

    def test_invalid_window(self):
        for window in (None, {}, {"x": True, "y": 0, "w": 1, "h": 1}):
            with self.assertRaises(ValueError):
                find_crop(texture(), texture(), window)

    def test_off_phase_duplicate_is_never_reported_unique(self):
        needle = texture(55, 35)
        haystack = Image.new("RGB", (400, 240), "white")
        haystack.paste(needle, (41, 51))
        haystack.paste(needle, (183, 94))
        position, score, unique = find_crop(haystack, needle, {"x": 0, "y": 0, "w": 330, "h": 210})
        self.assertEqual(score, 1)
        self.assertFalse(unique)

    def test_block_bound_retains_every_high_score_in_small_exhaustive_search(self):
        from engine.locate import _potential, _score
        rng = random.Random(41)
        for width, height in ((9, 9), (16, 11), (23, 17)):
            needle = texture(width, height)
            haystack = texture(width + 12, height + 10, seed=17)
            x, y = rng.randrange(10), rng.randrange(8)
            haystack.paste(needle, (x, y))
            gray, target = haystack.convert("L"), needle.convert("L")
            possible = set(_potential(gray, target, .89))
            for cy in range(haystack.height - height + 1):
                for cx in range(haystack.width - width + 1):
                    score = _score(gray.crop((cx, cy, cx + width, cy + height)), target)
                    if score >= .89:
                        self.assertIn((cx, cy), possible)
