"""Image-only Hermes tool adapter; no registration or I/O at import time."""

import importlib
import json
import logging
import os
from pathlib import Path
import re

logger = logging.getLogger(__name__)
MAX_RESULT_BYTES = 4000
STATE_FILE = "plugin-state.json"
VIEWPORT_PRESETS = {"desktop": (1280, 720), "mobile": (390, 844), "tablet": (768, 1024)}


def _module(name):
    # Hermes loads a package; direct repo imports and `python -m engine.cli`
    # must not require Hermes or mutate sys.path (notably its `tools` package).
    return importlib.import_module((__package__ + "." if __package__ else "") + "engine." + name)


def resolve_data_dir():
    """Resolve storage without creating it; respect Hermes' context-local home."""
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        selected = os.environ.get("HERMES_HOME")
        home = Path(selected).expanduser() if selected else Path.home() / ".hermes"
    else:
        home = Path(get_hermes_home()).expanduser()
    home = home.resolve()
    root = home / "orphic-eyes"
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("data directory must not redirect outside HERMES_HOME")
    if root.exists() and not root.is_dir():
        raise ValueError("data directory is not a directory")
    return root


def _safe_file(folder, filename):
    path = folder / filename
    if path.is_symlink() or path.resolve().parent != folder.resolve():
        raise ValueError("data file must not redirect outside its target directory")
    if path.exists() and (not path.is_file() or path.stat().st_nlink > 1):
        raise ValueError("data file must be a regular file without hard links")
    return path


def _case(root, name, create=False):
    candidate = root / name
    if candidate.is_symlink() or candidate.resolve() != root.resolve() / name:
        raise ValueError("target directory must not redirect to another location")
    case = _module("store")._case_dir(root, name, create=create)
    _safe_file(case, STATE_FILE)
    return case


def _target(args):
    name = args.get("name", "default")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", name):
        raise ValueError("name: use 1-40 ASCII letters/digits/dash/underscore, starting with a letter/digit")
    return name


def _rectangle(value):
    if not isinstance(value, dict) or set(value) != {"x", "y", "w", "h"}:
        raise ValueError("region must be an object with x,y,w,h integers, e.g. {x:0,y:0,w:100,h:40}")
    return _module("regions")._rectangle(value)


def _url(value):
    error = _module("capture").validate_url(value)
    if error:
        raise ValueError(error)
    return value


def _failure(exc):
    message = " ".join(str(exc).split())[:600] or type(exc).__name__
    lower = message.lower()
    if "viewport" in lower and "width/height" in lower:
        fix = "Pass either viewport (desktop/mobile/tablet) or width/height, never both."
    elif "capture size mismatch" in lower:
        fix = "Use a supported browser or viewport; do not resize the PNG to fake the requested viewport."
    elif "url" in lower:
        fix = "Use http://localhost:PORT/, http://127.0.0.1:PORT/ or a local absolute file:// URL."
    elif "browser" in lower:
        fix = "Install an Edge, Chrome or Chromium browser locally, then run /orphic doctor."
    elif "baseline not found" in lower:
        fix = "Call orphic_baseline with this name and a local URL first."
    elif any(word in lower for word in ("permission", "denied", "directory", "read-only")):
        fix = "Make HERMES_HOME/orphic-eyes writable and remove redirected or linked data paths."
    elif "comparison" in lower or "current.png" in lower:
        fix = "Call orphic_compare for this target before approving or accepting."
    else:
        fix = "Check the tool arguments and saved target; run /orphic help or /orphic doctor."
    while True:
        encoded = json.dumps({"success": False, "error": message, "fix": fix}, ensure_ascii=True)
        if len(encoded.encode("utf-8")) < MAX_RESULT_BYTES:
            return encoded
        message = message[:max(1, len(message) // 2)]


def _result(raw, name, root, action):
    if raw.get("status") == "error":
        raise RuntimeError(raw.get("error", "engine operation failed"))
    case = _case(root, name)
    metadata = _module("store")._read_metadata(case / "metadata.json")
    result = {key: value for key, value in raw.items() if key not in ("requests", "crops")}
    if "crops" in raw:
        result["crops_dir"] = str(_module("crops").validate_crops(case))
    if "request_results" in result:
        result["request_results"] = [dict(row) for row in result["request_results"]]
    result.setdefault("name", name)
    result.setdefault("summary", {"changed_px": 0, "changed_percent": 0, "box_count": 0,
                                  "unexpected_count": 0})
    result.setdefault("boxes", [])
    original_count = len(result["boxes"])
    result["boxes"] = [dict(box, bbox={key: box[key] for key in ("x", "y", "w", "h")},
                            kind="approved" if box["approved"] else box["label"])
                       for box in result["boxes"][:20]]
    messages = {"baseline": "Baseline saved", "accept": "Latest capture accepted as baseline",
                "ignore": "Ignore regions updated"}
    message = messages.get(action, {"pass": "No unexpected changes", "check": "Check these changes",
                                    "fail": "Review these visual regressions"}[raw["status"]])
    message = _module("report_json").result_message(raw, message)
    hints = {"baseline": "After editing UI files, call orphic_compare with this target name.",
             "accept": "Call orphic_compare after the next UI edit to check the new baseline.",
             "ignore": "Call orphic_compare again to apply the updated ignore regions."}
    result.update(success=True, target=name, message=message,
                  changed_percent=result["summary"]["changed_percent"],
                  viewport={**metadata["viewport"], "dpr": 1},
                  paths={key: str(case / filename) if (case / filename).is_file() else None
                         for key, filename in (("baseline", "baseline.png"), ("after", "current.png"),
                                               ("diff", "diff.png"), ("report", "report.json"))},
                  hint=hints.get(action, "Review the boxes; call orphic_approve if intended, otherwise fix the code and call orphic_compare again."))
    if raw.get("paths", {}).get("html"):
        result["paths"]["html"] = raw["paths"]["html"]
    if "request_results" in result:
        failing = [row["id"] for row in result["request_results"] if row["status"] in ("not_done", "unknown")]
        if failing:
            result["hint"] = "Check " + ", ".join(failing) + "; fix or clarify these intents, then call orphic_compare again."
    result["boxes_omitted"] = original_count - len(result["boxes"])
    # Byte budget, not character count: long paths and additive schema fields
    # mean fewer than 20 boxes can fit. Full data remains in report.json.
    while True:
        encoded = json.dumps(result, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) < MAX_RESULT_BYTES:
            return encoded
        if any(row.get("why") for row in result.get("request_results", [])):
            for row in result["request_results"]:
                row["why"] = ""
        elif any("found" in row for row in result.get("request_results", [])):
            for row in result["request_results"]:
                row.pop("found", None)
        elif result["boxes"]:
            result["boxes"].pop()
            result["boxes_omitted"] += 1
        elif result.get("ignore_regions"):
            result["ignore_regions"] = result["ignore_regions"][:-1]
            result["ignore_regions_omitted"] = result.get("ignore_regions_omitted", 0) + 1
        else:
            raise ValueError("result metadata exceeds 4 KB; shorten HERMES_HOME path")


def _run(args, allowed, action, operation):
    try:
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        if set(args) - set(allowed):
            raise ValueError("unsupported arguments; use only the fields in this tool's schema")
        name = _target(args)
        root = resolve_data_dir()
        raw = operation(args, name, root)
        return _result(raw, name, root, action)
    except Exception as exc:
        logger.debug("Orphic Eyes %s failed", action, exc_info=True)
        return _failure(exc)


def _baseline(args, name, root):
    url = _url(args.get("url"))
    width, height = args.get("width", 1280), args.get("height", 720)
    preset = None
    if "viewport" in args:
        preset = args["viewport"]
        if not isinstance(preset, str) or preset not in VIEWPORT_PRESETS:
            raise ValueError("viewport must be desktop, mobile or tablet")
        if "width" in args or "height" in args:
            raise ValueError("viewport cannot be combined with width/height")
        width, height = VIEWPORT_PRESETS[preset]
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in (width, height)):
        raise ValueError("width and height must be positive integers")
    case = _case(root, name, create=True)
    result = _module("store").baseline(name, url, root, width=width, height=height)
    if result["status"] != "error":
        _check_capture_size(case / "baseline.png", width, height)
        # A fresh baseline invalidates previous captures/reports/approvals.
        for filename in ("current.png", "diff.png", "report.json", "report.html", "approvals.json"):
            _safe_file(case, filename).unlink(missing_ok=True)
        state = {"url": url}
        if preset is not None:
            state["viewport_preset"] = preset
            result["meta"]["viewport"]["preset"] = preset
            _module("store")._atomic_json(_safe_file(case, "metadata.json"), result["meta"])
        _module("store")._atomic_json(_safe_file(case, STATE_FILE), state)
    return result


def handle_baseline(args: dict, **_kw) -> str:
    return _run(args, ("url", "name", "width", "height", "viewport"), "baseline", _baseline)


def _check_capture_size(path, width, height):
    from PIL import Image
    with Image.open(path) as image:
        if image.size != (width, height):
            raise ValueError(f"capture size mismatch: requested {width}x{height}, got {image.width}x{image.height}; --window-size={width},{height}, DPR=1")


def _compare(args, name, root):
    intents = None
    if "requests" in args:
        intents = _module("requests").validate_requests(args["requests"])
    case = _case(root, name)
    state_file = _safe_file(case, STATE_FILE)
    state = _module("store")._read_json(state_file, {})
    if not isinstance(state, dict):
        raise ValueError("invalid plugin URL state; recreate the baseline")
    if "url" in args:
        url = _url(args["url"])
    else:
        url = _url(state.get("url"))
    expected = args.get("expect", [])
    if not isinstance(expected, list):
        raise ValueError("expect must be a list of x,y,w,h objects")
    regions = [_rectangle(region) for region in expected]
    result = _module("compare").compare(name, url, root, expected_regions=regions,
                                        requests=intents, focus=True, shift_hints=True)
    if result["status"] != "error":
        viewport = result["meta"]["viewport"]
        _check_capture_size(case / "current.png", viewport["width"], viewport["height"])
        _module("store")._atomic_json(state_file, {**state, "latest_url": url})
    return result


def handle_compare(args: dict, **_kw) -> str:
    return _run(args, ("name", "url", "expect", "requests"), "compare", _compare)


def _approve(args, name, root):
    _case(root, name)
    return _module("store").approve(name, root, boxes=args.get("boxes"),
                                     all_boxes=args.get("all", False))


def handle_approve(args: dict, **_kw) -> str:
    return _run(args, ("name", "boxes", "all"), "approve", _approve)


def _accept(args, name, root):
    case = _case(root, name)
    state_file = _safe_file(case, STATE_FILE)
    store = _module("store")
    state = store._read_json(state_file, {})
    if not isinstance(state, dict):
        raise ValueError("invalid plugin URL state; recreate the baseline")
    if "latest_url" in state:
        _url(state["latest_url"])
    result = store.accept(name, root)
    if result["status"] != "error" and "latest_url" in state:
        store._atomic_json(state_file, {**state, "url": state["latest_url"]})
    return result


def handle_accept(args: dict, **_kw) -> str:
    return _run(args, ("name",), "accept", _accept)


def _ignore(args, name, root):
    region = _rectangle(args.get("region"))
    action = args.get("action")
    if action not in ("add", "remove"):
        raise ValueError("action must be add or remove")
    case = _case(root, name)
    store = _module("store")
    if action == "add":
        return store.ignore_add(name, root, region)
    # Engine removal is by label. Match its clipped stored rectangle exactly.
    metadata = store._read_metadata(case / "metadata.json")
    viewport = metadata["viewport"]
    clipped = _module("regions")._clip([region], (viewport["width"], viewport["height"]))
    if not clipped:
        raise ValueError("ignore region must intersect the image")
    listed = store.ignore_list(name, root)
    if listed["status"] == "error":
        return listed
    matches = [entry for entry in listed["ignore_regions"]
               if all(entry[key] == clipped[0][key] for key in ("x", "y", "w", "h"))]
    if len(matches) != 1:
        raise ValueError("region must match exactly one stored ignore rectangle")
    return store.ignore_remove(name, root, matches[0]["name"])


def handle_ignore(args: dict, **_kw) -> str:
    return _run(args, ("name", "action", "region"), "ignore", _ignore)


NAME = {"type": "string", "description": "Target name, e.g. login; 1-40 ASCII letters/digits/_/-.",
        "default": "default", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$"}
URL = {"type": "string", "description": "Local page, e.g. http://localhost:3000/ or file:///C:/app/index.html."}
REGION = {"type": "object", "additionalProperties": False,
          "properties": {key: {"type": "integer", "minimum": 0 if key in ("x", "y") else 1,
                                "description": f"Screenshot pixels: {key}, e.g. {8 if key in ('x', 'y') else 40}."}
                         for key in ("x", "y", "w", "h")}, "required": ["x", "y", "w", "h"]}
REQUEST = {"type": "object", "additionalProperties": False,
           "properties": {"id": {"type": "string", "pattern": "^PT-[1-9][0-9]{0,2}$",
                                  "description": "Unique intent ID, e.g. PT-1."},
                          "type": {"type": "string", "enum": ["move", "hide", "revert", "comment"]},
                          "from": REGION, "to": REGION,
                          "precision": {"type": "string", "enum": ["exact", "approximate"], "default": "approximate"}},
           "required": ["id", "type"]}


def _schema(name, description, properties, required=()):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "additionalProperties": False,
                           "properties": {"name": NAME, **properties}, "required": list(required)}}


LIMITS = " Only http://localhost, http://127.0.0.1 and local file:// URLs; image-only, no DOM access."
TOOL_DEFINITIONS = (
    ("orphic_baseline", _schema("orphic_baseline",
        "Call first, before editing a local web app's UI, to save a baseline screenshot. Optional viewport: desktop=1280x720, mobile=390x844, tablet=768x1024; do not combine with width/height. Verifies actual PNG dimensions, DPR=1. Returns JSON status, paths and viewport; replacing a baseline clears prior comparison/approvals." + LIMITS,
        {"url": URL, "viewport": {"type": "string", "enum": ["desktop", "mobile", "tablet"],
                                  "description": "Optional preset, e.g. mobile=390x844; do not combine with width/height."},
         "width": {"type": "integer", "minimum": 1, "default": 1280,
                               "description": "Viewport width in pixels, e.g. 1280."},
         "height": {"type": "integer", "minimum": 1, "default": 720,
                    "description": "Viewport height in pixels, e.g. 720."}}, ("url",)), handle_baseline),
    ("orphic_compare", _schema("orphic_compare",
        "Call after editing UI files of a local web app. Compares before/after screenshots by pixels (image-only, no DOM/CSS). Captures using the baseline viewport/browser; returns status pass / check / fail, percentages, numbered boxes, optional shift hints and image paths. Can produce a self-contained HTML report when the template exists; paths.html is returned only when a report page was generated. Optional requests verify up to 8 Point & Tell intents (Exact = 2 px, Approx = 8 px): read request_results and requests_ok separately from visual status; expected areas never prove completion. Omitted url reuses the baseline URL; expect classifies regions without approving them. crops_dir contains box-<id>-before/after.png (first 8 boxes) and req-PT-<n>-before/after.png (non-comment requests); full coordinates/scales and verdicts are in report.json next to the screenshots." + LIMITS,
        {"url": URL, "requests": {"type": "array", "maxItems": 8, "items": REQUEST,
                                   "description": "Point & Tell intents; from is in BASELINE pixels, to in AFTER pixels; same size; exact=2px, approximate=8px."},
         "expect": {"type": "array", "items": REGION,
                                 "description": "Expected changed areas, e.g. [{x:8,y:8,w:100,h:40}]."}}), handle_compare),
    ("orphic_approve", _schema("orphic_approve",
        "After reviewing the latest comparison, approve intended unexpected box IDs or all boxes. Returns updated metrics and classifications; approvals match image content and do not replace the baseline." + LIMITS,
        {"boxes": {"type": "array", "items": {"type": "integer", "minimum": 1},
                   "description": "Latest comparison IDs, e.g. [1,2]; use instead of all=true."},
         "all": {"type": "boolean", "default": False,
                 "description": "Approve every box, e.g. true; omit boxes."}}), handle_approve),
    ("orphic_accept", _schema("orphic_accept",
        "After reviewing the latest capture, make it the new baseline and clear approvals. Returns status and paths; requires an earlier compare. This replaces the reference image." + LIMITS, {}), handle_accept),
    ("orphic_ignore", _schema("orphic_ignore",
        "After baseline creation, add an ignore rectangle for unstable content or remove one matching the returned stored rectangle. Returns ignore_regions; call compare again to recalculate. Does not edit the website." + LIMITS,
        {"action": {"type": "string", "enum": ["add", "remove"], "description": "Operation, e.g. add."},
         "region": REGION}, ("action", "region")), handle_ignore),
)
