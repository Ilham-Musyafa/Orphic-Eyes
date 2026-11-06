"""Confined baseline storage and screenshot metadata."""

from datetime import datetime
import json
import platform
from pathlib import Path
import re

from .capture import capture, detect_browser, validate_url


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
                     "report.json"):
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


def baseline(name, url, store_dir):
    """Save a 1280x800 baseline and metadata, or return an error dictionary."""
    try:
        validation = validate_url(url)
        if validation is not None:
            raise ValueError(validation)
        browser = detect_browser()
        if browser is None:
            raise RuntimeError("no installed Edge or Chrome browser found")
        case = _case_dir(store_dir, name, create=True)
        if not capture(url, case / "baseline.png", browser=browser):
            raise RuntimeError("browser capture failed")
        metadata = _metadata(browser, 1280, 800, 0)
        with (case / "metadata.json").open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
        return {"status": "pass", "name": name, "meta": metadata}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
