"""Internal rectangle validation, clipping, and RGB approval fingerprints."""

import hashlib
import re

MAX_IGNORE_REGIONS = 50


def _label(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value):
        raise ValueError("label must be 1-40 ASCII letters, digits, - or _")
    return value


def _rectangle(value):
    if isinstance(value, dict):
        if not all(key in value for key in ("x", "y", "w", "h")):
            raise ValueError("region must contain x,y,w,h integers")
        values = [value[key] for key in ("x", "y", "w", "h")]
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        values = list(value)
    else:
        raise ValueError("region must contain x,y,w,h integers")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in values):
        raise ValueError("region coordinates must be integers")
    x, y, w, h = values
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        raise ValueError("region requires x,y >= 0 and w,h > 0")
    return dict(zip(("x", "y", "w", "h"), values))


def _regions(values, named=False):
    if values is None and not named:
        return []
    if not isinstance(values, (list, tuple)):
        raise ValueError("regions must be a list")
    if named and len(values) > MAX_IGNORE_REGIONS:
        raise ValueError("at most 50 ignore regions are allowed")
    result = []
    names = set()
    for value in values:
        region = _rectangle(value)
        if named:
            name = _label(value["name"])
            if name in names:
                raise ValueError("ignore labels must be unique")
            names.add(name)
            region = {"name": name, **region}
        result.append(region)
    return result


def _clip(regions, size):
    width, height = size
    result = []
    for region in regions:
        x, y = region["x"], region["y"]
        w, h = min(region["w"], width - x), min(region["h"], height - y)
        if w > 0 and h > 0:
            result.append({**region, "w": w, "h": h})
    return result


def _bounds(box):
    return (box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"])


def _key(box):
    return tuple(box[field] for field in ("x", "y", "w", "h"))


def _fingerprint(image, box):
    return {**dict(zip(("x", "y", "w", "h"), _key(box))),
            "sha256": hashlib.sha256(image.crop(_bounds(box)).convert("RGB").tobytes()).hexdigest()}


def _approvals(values):
    if not isinstance(values, list):
        raise ValueError("approvals must be a list")
    result = []
    for value in values:
        rectangle = _rectangle(value)
        digest = value["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("approval sha256 must be 64 lowercase hexadecimal characters")
        result.append({**rectangle, "sha256": digest})
    return result
