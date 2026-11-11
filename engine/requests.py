"""Point & Tell validation and deterministic per-request pixel verdicts."""

import re
import time

from .locate import MATCH_MIN, SEARCH_PAD, UNIQUE_GAP, SearchBudgetExceeded, find_crop
from .regions import _rectangle

EXACT_TOLERANCE = 2  # Exact intent allows a two-pixel top-left discrepancy per axis.
APPROXIMATE_TOLERANCE = 8  # Approximate intent allows a small visual placement discrepancy.
MAX_REQUESTS = 8  # Bound matching work and preserve all IDs in compact tool output.
REQUEST_BUDGET_SECONDS = 1.2  # Leave headroom within 2s for shifts, crop files and serialization.


def validate_requests(value):
    if not isinstance(value, list) or len(value) > MAX_REQUESTS:
        raise ValueError("requests must be a list of at most 8 intents")
    result, ids = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each request must be an object")
        ident = item.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"PT-[1-9][0-9]{0,2}", ident) or ident in ids:
            raise ValueError("request ids must be unique PT-1..PT-999 (no leading zero)")
        kind = item.get("type")
        if kind not in ("move", "hide", "revert", "comment"):
            raise ValueError("request type must be move, hide, revert or comment")
        allowed = {"id", "type", "precision"}
        if kind != "comment":
            allowed.add("from")
        if kind == "move":
            allowed.add("to")
        if set(item) - allowed:
            raise ValueError("request contains fields not allowed for its type")
        precision = item.get("precision", "approximate")
        if precision not in ("exact", "approximate"):
            raise ValueError("precision must be exact or approximate")
        request = {"id": ident, "type": kind, "precision": precision}
        for key in ("from", "to"):
            if key in allowed:
                region = item.get(key)
                if not isinstance(region, dict) or set(region) != {"x", "y", "w", "h"}:
                    raise ValueError("request " + key + " must contain only x,y,w,h integers")
                request[key] = _rectangle(region)
        if kind == "move" and any(request["from"][key] != request["to"][key] for key in ("w", "h")):
            raise ValueError("move from/to sizes must match; crop matching cannot verify resizing")
        ids.add(ident)
        result.append(request)
    return result


def check_bounds(region, size, label):
    if region["x"] + region["w"] > size[0] or region["y"] + region["h"] > size[1]:
        raise ValueError(label + " rectangle must fit entirely inside its image")


def padded(region, size, pad=SEARCH_PAD):
    x, y = max(0, region["x"] - pad), max(0, region["y"] - pad)
    right = min(size[0], region["x"] + region["w"] + pad)
    bottom = min(size[1], region["y"] + region["h"] + pad)
    return {"x": x, "y": y, "w": max(0, right - x), "h": max(0, bottom - y)}


def expected_for_requests(requests, size):
    return [padded(request[key], size) for request in requests if request["type"] != "comment"
            for key in (("from", "to") if request["type"] == "move" else ("from",))]


def _bounds(region):
    return (region["x"], region["y"], region["x"] + region["w"], region["y"] + region["h"])


def verify_requests(before, after, requests):
    results = []
    matches_by_regions = {}  # Same immutable images, within this call only.
    deadline = time.perf_counter() + REQUEST_BUDGET_SECONDS
    for request in requests:
        verdict = {"id": request["id"], "status": "unknown", "found": None,
                   "moved": {"dx": None, "dy": None}, "off": {"dx": None, "dy": None},
                   "match": 0.0, "why": ""}
        if request["type"] == "comment":
            verdict.update(status="skipped", why="Comment has no pixel test")
        elif before.size != after.size:
            verdict["why"] = "Viewport size changed; request cannot be verified"
        else:
            source = request["from"]
            target = request.get("to", source)
            check_bounds(source, before.size, "from")
            check_bounds(target, after.size, "to")
            needle = before.crop(_bounds(source))
            # Search only two bounded neighborhoods, never the intervening page.
            # Merge overlapping windows to avoid paying twice for nearby moves.
            windows = [padded(source, after.size)]
            other = padded(target, after.size)
            first = windows[0]
            if other != first:
                if (max(first["x"], other["x"]) < min(first["x"] + first["w"], other["x"] + other["w"])
                        and max(first["y"], other["y"]) < min(first["y"] + first["h"], other["y"] + other["h"])):
                    x, y = min(first["x"], other["x"]), min(first["y"], other["y"])
                    windows = [{"x": x, "y": y,
                                "w": max(first["x"] + first["w"], other["x"] + other["w"]) - x,
                                "h": max(first["y"] + first["h"], other["y"] + other["h"]) - y}]
                else:
                    windows.append(other)
            try:
                key = tuple(source[field] for field in ("x", "y", "w", "h")) + tuple(
                    target[field] for field in ("x", "y", "w", "h"))
                if key not in matches_by_regions:
                    matches_by_regions[key] = sorted(
                        (find_crop(after, needle, window, deadline=deadline) for window in windows),
                        key=lambda item: item[1], reverse=True)
                matches = matches_by_regions[key]
            except SearchBudgetExceeded:
                verdict["why"] = "Search time budget exceeded; no pixel verdict"
                results.append(verdict)
                continue
            position, score, unique = matches[0]
            if len(matches) > 1 and matches[1][1] > score - UNIQUE_GAP:
                unique = False
            verdict["match"] = round(score, 4)
            if score >= MATCH_MIN and unique and position is not None:
                x, y = position
                verdict["found"] = {"x": x, "y": y, "w": source["w"], "h": source["h"]}
                verdict["moved"] = {"dx": x - source["x"], "dy": y - source["y"]}
                verdict["off"] = {"dx": x - target["x"], "dy": y - target["y"]}
                tolerance = EXACT_TOLERANCE if request["precision"] == "exact" else APPROXIMATE_TOLERANCE
                done = request["type"] != "hide" and all(abs(v) <= tolerance for v in verdict["off"].values())
                verdict.update(status="done" if done else "not_done",
                               why="Within target tolerance" if done else "Found outside target tolerance")
                if request["type"] == "hide":
                    verdict["why"] = "Source crop still present in search window"
            elif request["type"] == "hide":
                verdict.update(status="done" if score < MATCH_MIN else "not_done",
                               why="Crop absent within bounded search" if score < MATCH_MIN else "Crop remains; location ambiguous")
            else:
                verdict["why"] = "Low match score" if score < MATCH_MIN else "Ambiguous crop match"
        results.append(verdict)
    counts = {key: sum(row["status"] == key for row in results)
              for key in ("done", "not_done", "unknown", "skipped")}
    return {"requests": requests, "request_results": results,
            "requests_ok": all(row["status"] in ("done", "skipped") for row in results),
            "request_counts": counts}
