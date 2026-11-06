"""Optional conservative movement hints for small unexpected diff boxes."""

from .locate import MATCH_MIN, find_crop
from .requests import padded

SHIFT_PAD = 128  # Only infer nearby movement, never search the entire page.
MAX_SHIFT_BOXES = 8  # Bound extra template searches for a noisy diff.
MAX_SHIFT_WIDTH = 400  # Larger crops are too costly and often contain multiple elements.
MAX_SHIFT_HEIGHT = 200  # Keep hints focused on compact visual regions.


def add_shift_hints(before, after, boxes):
    if before.size != after.size:
        return
    eligible = [box for box in boxes if box["label"] == "unexpected" and not box["approved"]
                and box["w"] <= MAX_SHIFT_WIDTH and box["h"] <= MAX_SHIFT_HEIGHT]
    for box in eligible[:MAX_SHIFT_BOXES]:
        x, y, w, h = (box[key] for key in ("x", "y", "w", "h"))
        needle = before.crop((x, y, x + w, y + h))
        extrema = needle.convert("L").getextrema()
        if extrema[0] == extrema[1]:
            continue  # A flat crop cannot establish uniqueness; do no search.
        position, score, unique = find_crop(after, needle, padded(box, after.size, SHIFT_PAD))
        if unique and score >= MATCH_MIN and position is not None:
            dx, dy = position[0] - x, position[1] - y
            if dx or dy:
                box["shift"] = {"dx": dx, "dy": dy}
