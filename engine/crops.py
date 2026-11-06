"""Confined focus-image files and their full-report coordinate metadata."""

from PIL import Image

from .requests import padded

CROP_PAD = 16  # Include enough surrounding pixels to identify nearby UI context.
CROP_MAX_SIDE = 640  # Keep model-facing images small without embedding image data.
MAX_BOX_CROPS = 8  # Bound output count even for noisy screenshots.


def _safe_file(folder, filename):
    path = folder / filename
    if path.is_symlink() or path.resolve().parent != folder.resolve():
        raise ValueError("crop file must not redirect outside the crops directory")
    if path.exists() and (not path.is_file() or path.stat().st_nlink > 1):
        raise ValueError("crop file must be regular and must not be a hard link")
    return path


def validate_crops(case):
    folder = case / "crops"
    if folder.is_symlink() or folder.resolve() != case.resolve() / "crops":
        raise ValueError("crops directory must not redirect outside the target")
    if folder.exists() and not folder.is_dir():
        raise ValueError("crops path must be a directory")
    if folder.exists():
        for child in folder.iterdir():
            _safe_file(folder, child.name)
    return folder


def _save(folder, filename, image, region):
    rectangle = padded(region, image.size, CROP_PAD)
    if rectangle["w"] <= 0 or rectangle["h"] <= 0:
        return None
    x, y, w, h = (rectangle[key] for key in ("x", "y", "w", "h"))
    crop = image.crop((x, y, x + w, y + h))
    scale = min(1.0, CROP_MAX_SIDE / max(crop.size))
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    if crop.size != size:
        crop = crop.resize(size, Image.Resampling.LANCZOS)
    crop.save(_safe_file(folder, filename), format="PNG")
    return {"path": "crops/" + filename, "bbox": rectangle, "scale": scale,
            "size": {"width": size[0], "height": size[1]}}


def write_crops(case, before, after, report):
    folder = validate_crops(case)
    folder.mkdir(exist_ok=True)
    # Validate the entire set before deleting any stale file; never recurse.
    stale = [_safe_file(folder, child.name) for child in folder.iterdir()]
    for path in stale:
        path.unlink()
    items = []
    for box in report["boxes"][:MAX_BOX_CROPS]:
        ident = "box-" + str(box["id"])
        items.append({"id": ident, "before": _save(folder, ident + "-before.png", before, box),
                      "after": _save(folder, ident + "-after.png", after, box)})
    verdicts = {row["id"]: row for row in report.get("request_results", [])}
    for request in report.get("requests", []):
        if request["type"] == "comment":
            continue  # Comments have no image rectangle by contract.
        ident = "req-" + request["id"]
        destination = verdicts[request["id"]]["found"] or request.get("to", request["from"])
        items.append({"id": ident, "before": _save(folder, ident + "-before.png", before, request["from"]),
                      "after": _save(folder, ident + "-after.png", after, destination)})
    return {"pad": CROP_PAD, "max_side": CROP_MAX_SIDE, "items": items}


def clear_crops(case):
    """An unenhanced legacy compare also invalidates any prior focus images."""
    folder = validate_crops(case)
    if folder.exists():
        stale = [_safe_file(folder, child.name) for child in folder.iterdir()]
        for path in stale:
            path.unlink()
