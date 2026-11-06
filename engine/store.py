"""Confined baseline storage and screenshot metadata."""

from datetime import datetime
import json
import os
import platform
from pathlib import Path
import re
import tempfile

from PIL import Image

from .capture import capture, detect_browser, validate_url
from .regions import _approvals, _clip, _fingerprint, _key, _label, _rectangle, _regions


def _case_dir(store_dir, name, create):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("name must contain only ASCII letters, digits, _ or -")
    if name.upper() in {"CON", "PRN", "AUX", "NUL", *(
            prefix + str(i) for prefix in ("COM", "LPT") for i in range(1, 10))}:
        raise ValueError("name is reserved on Windows")
    root = Path(store_dir).resolve()
    case = root / name
    if case.resolve().parent != root:
        raise ValueError("case directory must stay inside the store")
    for filename in ("baseline.png", "metadata.json", "current.png", "diff.png",
                     "report.json", "config.json", "approvals.json"):
        target = case / filename
        if target.is_symlink() or (target.exists() and (
                target.resolve().parent != case.resolve() or target.stat().st_nlink > 1)):
            raise ValueError("store files must not link outside the case directory")
        if target.exists() and not target.is_file():
            raise ValueError("store output path is not a file: " + filename)
    if create:
        case.mkdir(parents=True, exist_ok=True)
    elif not case.is_dir():
        raise ValueError("baseline not found for " + name)
    return case


def _read_json(path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_options(case):
    return (_regions(_read_json(case / "config.json", []), named=True),
            _approvals(_read_json(case / "approvals.json", [])))


def _atomic_json(path, value):
    # Serialize before creating a file, so invalid data cannot leave partial JSON.
    content = json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=".sightdiff_", suffix=".tmp",
                                         dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def ignore_add(name, store_dir, region, label=None):
    """Add a persistent clipped ignore rectangle, or return an error."""
    try:
        rectangle = _rectangle(region)
        if label is not None:
            _label(label)
        case = _case_dir(store_dir, name, create=False)
        ignored, unused = _read_options(case)
        if label is None:
            used = {entry["name"] for entry in ignored}
            label = next("region-" + str(i) for i in range(1, 52)
                         if "region-" + str(i) not in used)
        proposed = _regions([*ignored, {"name": label, **rectangle}], named=True)
        with Image.open(case / "baseline.png") as image:
            clipped = _clip([proposed[-1]], image.size)
        if not clipped:
            raise ValueError("ignore region must intersect the image")
        proposed[-1] = clipped[0]
        _atomic_json(case / "config.json", proposed)
        return {"status": "pass", "ignore_regions": proposed}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def ignore_list(name, store_dir):
    """List saved ignore rectangles without creating files."""
    try:
        case = _case_dir(store_dir, name, create=False)
        ignored, unused = _read_options(case)
        return {"status": "pass", "ignore_regions": ignored}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def ignore_remove(name, store_dir, label):
    """Remove one ignore region by its unique label."""
    try:
        _label(label)
        case = _case_dir(store_dir, name, create=False)
        ignored, unused = _read_options(case)
        remaining = [region for region in ignored if region["name"] != label]
        if len(remaining) == len(ignored):
            raise ValueError("ignore label not found: " + label)
        _atomic_json(case / "config.json", remaining)
        return {"status": "pass", "ignore_regions": remaining}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def approve(name, store_dir, boxes=None, all_boxes=False):
    """Approve existing image crops and rebuild the report without a browser."""
    from .compare import _analyze, _tolerance
    from .report_json import build_report, write_report

    try:
        if not isinstance(all_boxes, bool):
            raise ValueError("all_boxes must be a boolean")
        if boxes is None:
            boxes = []
        if not isinstance(boxes, (list, tuple)) or any(
                isinstance(box, bool) or not isinstance(box, int) or box <= 0 for box in boxes):
            raise ValueError("box IDs must be positive integers")
        if (all_boxes and boxes) or (not all_boxes and not boxes):
            raise ValueError("select box IDs or all_boxes=True")
        case = _case_dir(store_dir, name, create=False)
        metadata = _read_metadata(case / "metadata.json")
        ignored, approvals = _read_options(case)
        previous = _read_json(case / "report.json", None)
        if not isinstance(previous, dict):
            raise ValueError("approve requires an existing comparison report")
        tolerance = _tolerance(previous["meta"]["tolerance"])
        expected_labels = {_key(box) for box in previous["boxes"] if box["label"] == "expected"}
        with Image.open(case / "baseline.png") as source:
            before = source.convert("RGB")
        with Image.open(case / "current.png") as source:
            after = source.convert("RGB")
        result, diff = _analyze(before, after, tolerance, ignored, [], approvals, expected_labels)
        # IDs refer to the report the caller reviewed, not a new tile layout.
        if [_key(box) for box in result["boxes"]] != [_key(box) for box in previous["boxes"]]:
            raise ValueError("comparison boxes changed; run compare before approving")
        available = {box["id"]: box for box in result["boxes"]}
        if any(box not in available for box in boxes):
            raise ValueError("box ID not found in current comparison")
        selected = list(available) if all_boxes else boxes
        proposed = list(approvals)
        for box_id in selected:
            record = _fingerprint(after, available[box_id])
            if record not in proposed:
                proposed.append(record)
        result, diff = _analyze(before, after, tolerance, ignored, [], proposed, expected_labels)
        meta = _metadata(metadata["browser"], metadata["viewport"]["width"],
                         metadata["viewport"]["height"], tolerance)
        report = build_report(name, result, meta)
        if report["status"] == "error":
            return report
        for key in ("requests", "request_results", "requests_ok", "request_counts"):
            if key in previous:
                report[key] = previous[key]
        _atomic_json(case / "approvals.json", proposed)
        diff.save(case / "diff.png", format="PNG")
        return write_report(report, case / "report.json")
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def accept(name, store_dir):
    """Replace the baseline with current.png and clear saved approvals."""
    temporary = None
    try:
        case = _case_dir(store_dir, name, create=False)
        metadata = _read_metadata(case / "metadata.json")
        with Image.open(case / "current.png") as image:
            if image.format != "PNG":
                raise ValueError("current.png must be a PNG")
            image.load()
            width, height = image.size
        # Preserve the exact captured PNG rather than recompressing its pixels.
        with tempfile.NamedTemporaryFile(prefix=".sightdiff_", suffix=".tmp",
                                         dir=case, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write((case / "current.png").read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, case / "baseline.png")
        _atomic_json(case / "approvals.json", [])
        metadata = _metadata(metadata["browser"], width, height, metadata["tolerance"])
        _atomic_json(case / "metadata.json", metadata)
        return {"status": "pass", "name": name, "meta": metadata}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _metadata(browser, width, height, tolerance):
    return {"browser": browser, "os": platform.system(),
            "viewport": {"width": width, "height": height},
            "created_at": datetime.now().astimezone().isoformat(),
            "tolerance": tolerance}


def _read_metadata(path):
    with path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    viewport = metadata["viewport"]
    for value in (viewport["width"], viewport["height"]):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("invalid baseline viewport")
    if not isinstance(metadata["browser"], str) or not metadata["browser"]:
        raise ValueError("invalid baseline browser")
    return metadata


def baseline(name, url, store_dir, *, width=1280, height=800):
    """Save a baseline and metadata (1280x800 by default), or return an error."""
    try:
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
               for v in (width, height)):
            raise ValueError("viewport dimensions must be positive integers")
        validation = validate_url(url)
        if validation is not None:
            raise ValueError(validation)
        browser = detect_browser()
        if browser is None:
            raise RuntimeError("no installed Edge or Chrome browser found")
        case = _case_dir(store_dir, name, create=True)
        if not capture(url, case / "baseline.png", browser=browser, width=width, height=height):
            raise RuntimeError("browser capture failed")
        metadata = _metadata(browser, width, height, 0)
        with (case / "metadata.json").open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
        return {"status": "pass", "name": name, "meta": metadata}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
