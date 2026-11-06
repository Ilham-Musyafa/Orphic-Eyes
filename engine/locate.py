"""Bounded, deterministic grayscale crop matching; no semantic recognition."""

import time

from PIL import Image, ImageChops, ImageFilter, ImageStat

from .regions import _rectangle

MATCH_MIN = 0.92  # Require a small mean absolute grayscale pixel error.
UNIQUE_GAP = 0.03  # Reject competing matches whose score is almost as good.
SEARCH_PAD = 64  # Request searches stay near the user-supplied source/target.
UNIQUE_DISTANCE = 4  # Competing top-left corners must be at least 4 Euclidean pixels apart.
COARSE_FACTOR = 4  # Reduce pixel work while retaining small UI features.
REFINE_PEAKS = 8  # Bound refinement work and keep repeated candidate locations.
COARSE_MARGIN = 0.12  # Allow downsampling/phase error before rejecting a coarse candidate.
BOUND_GRID = 4  # Disjoint block means cheaply bound full-resolution absolute error.


class SearchBudgetExceeded(RuntimeError):
    """No location or absence claim is safe when a bounded search is unfinished."""


def _check_deadline(deadline):
    if deadline is not None and time.perf_counter() >= deadline:
        raise SearchBudgetExceeded("crop search time budget exceeded")


def _score(source, needle):
    return 1.0 - ImageStat.Stat(ImageChops.difference(source, needle)).mean[0] / 255.0


def _potential(gray, target, cutoff, deadline=None):
    """Candidates whose score could reach cutoff, by a conservative MAE bound.

    Jensen's inequality bounds pixel MAE by disjoint block-mean differences.
    Subtract 1 grayscale level per block for BoxBlur's two rounding passes;
    omitted edge pixels contribute zero to the lower bound. Thus a coarse pass
    cannot silently hide a better or ambiguous high-scoring full-resolution match.
    """
    nw, nh = target.size
    cols, rows = min(BOUND_GRID, nw), min(BOUND_GRID, nh)
    bw, bh = max(1, nw // cols), max(1, nh // rows)
    bw -= 1 if bw % 2 == 0 else 0
    bh -= 1 if bh % 2 == 0 else 0
    averaged = gray.filter(ImageFilter.BoxBlur(((bw - 1) // 2, (bh - 1) // 2)))
    pw, ph = gray.width - nw + 1, gray.height - nh + 1
    lower = [0.0] * (pw * ph)
    for row in range(rows):
        y = row * (nh - bh) // max(1, rows - 1)
        for col in range(cols):
            _check_deadline(deadline)
            x = col * (nw - bw) // max(1, cols - 1)
            mean = ImageStat.Stat(target.crop((x, y, x + bw, y + bh))).mean[0]
            cx, cy = x + bw // 2, y + bh // 2
            values = averaged.crop((cx, cy, cx + pw, cy + ph)).tobytes()
            lower = [total + max(0.0, abs(value - mean) - 1.0) * bw * bh
                     for total, value in zip(lower, values)]
    maximum_error = (1.0 - cutoff) * 255 * nw * nh + 1e-7
    return ((index % pw, index // pw) for index, error in enumerate(lower) if error <= maximum_error)


def find_crop(haystack, needle, window, *, deadline=None):
    """Return (best (x,y) or None, score in [0,1], unique).

    Coordinates are absolute image pixels; window is an x/y/w/h object. The
    complete needle must fit within the clipped window. Coarse-to-fine search
    is conservative: never use a low score or a nonunique result as a location.
    Flat needles cannot establish uniqueness. No search outside window occurs.
    """
    if not isinstance(haystack, Image.Image) or not isinstance(needle, Image.Image):
        raise ValueError("haystack and needle must be Pillow images")
    _check_deadline(deadline)
    region = _rectangle(window)
    left, top = region["x"], region["y"]
    right = min(haystack.width, left + region["w"])
    bottom = min(haystack.height, top + region["h"])
    nw, nh = needle.size
    if nw <= 0 or nh <= 0 or right - left < nw or bottom - top < nh:
        return None, 0.0, False
    gray = haystack.crop((left, top, right, bottom)).convert("L")
    target = needle.convert("L")
    factor = min(COARSE_FACTOR, max(1, nw // 8), max(1, nh // 8))
    sw, sh = gray.size
    # Size ratios are preserved by exact integer-grid reduction; refine in
    # original pixels to avoid interpreting downscaled coordinates as evidence.
    coarse = gray.resize((max(1, sw // factor), max(1, sh // factor)), Image.Resampling.BOX)
    small = target.resize((max(1, nw // factor), max(1, nh // factor)), Image.Resampling.BOX)
    cw, ch = small.size
    ranked = []
    for y in range(coarse.height - ch + 1):
        _check_deadline(deadline)
        for x in range(coarse.width - cw + 1):
            score = _score(coarse.crop((x, y, x + cw, y + ch)), small)
            ranked.append((score, x, y))
    ranked.sort(key=lambda item: (-item[0], item[2], item[1]))
    if factor == 1:
        candidates = {(x, y): score for score, x, y in ranked}
    else:
        peaks = []
        for score, x, y in ranked:
            if score < MATCH_MIN - COARSE_MARGIN:
                break
            if all((x - px) ** 2 + (y - py) ** 2 >= 4 for px, py in peaks):
                peaks.append((x, y))
                if len(peaks) == REFINE_PEAKS:
                    break
        candidates = {}
        radius = factor + UNIQUE_DISTANCE
        for px, py in peaks:
            for y in range(max(0, py * factor - radius), min(sh - nh, py * factor + radius) + 1):
                _check_deadline(deadline)
                for x in range(max(0, px * factor - radius), min(sw - nw, px * factor + radius) + 1):
                    if (x, y) not in candidates:
                        candidates[x, y] = _score(gray.crop((x, y, x + nw, y + nh)), target)
    best_so_far = max(candidates.values(), default=0.0)
    # Certify high scores and uniqueness against every remaining plausible
    # position. Low-score searches certify absence at MATCH_MIN; scores below
    # that threshold are best observed scores, not a location claim.
    cutoff = max(MATCH_MIN, best_so_far - UNIQUE_GAP) if best_so_far < MATCH_MIN else best_so_far - UNIQUE_GAP
    if factor > 1:
        for x, y in _potential(gray, target, cutoff, deadline):
            _check_deadline(deadline)
            if (x, y) not in candidates:
                candidates[x, y] = _score(gray.crop((x, y, x + nw, y + nh)), target)
    if not candidates:
        return None, 0.0, False
    (x, y), best = max(candidates.items(), key=lambda item: item[1])
    second = max((score for (cx, cy), score in candidates.items()
                  if (cx - x) ** 2 + (cy - y) ** 2 >= UNIQUE_DISTANCE ** 2), default=0.0)
    flat = target.getextrema()[0] == target.getextrema()[1]
    unique = not flat and best >= MATCH_MIN and best - second >= UNIQUE_GAP - 1e-12
    return (left + x, top + y), best, unique
