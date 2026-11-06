"""Pillow-only image comparison and local screenshot comparison."""

from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

FAIL_PERCENT = 5
TILE_SIZE = 32
ZONE_NAMES = (
    ("top-left", "top-center", "top-right"),
    ("middle-left", "center", "middle-right"),
    ("bottom-left", "bottom-center", "bottom-right"),
)


def _tolerance(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise ValueError("tolerance must be an integer from 0 to 255")
    return value


def _boxes(mask, total):
    width, height = mask.size
    tiles = {}
    for y in range(0, height, TILE_SIZE):
        for x in range(0, width, TILE_SIZE):
            tile = mask.crop((x, y, min(x + TILE_SIZE, width),
                              min(y + TILE_SIZE, height)))
            bounds = tile.getbbox()
            if bounds:
                left, top, right, bottom = bounds
                tiles[(x // TILE_SIZE, y // TILE_SIZE)] = (
                    (x + left, y + top, x + right, y + bottom),
                    tile.histogram()[255],
                )
    clusters = []
    while tiles:
        seed = next(iter(tiles))
        pending = [seed]
        bounds, count = tiles.pop(seed)
        left, top, right, bottom = bounds
        while pending:
            tx, ty = pending.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (tx + dx, ty + dy)
                    entry = tiles.pop(neighbor, None)
                    if entry is not None:
                        pending.append(neighbor)
                        bounds, pixels = entry
                        left = min(left, bounds[0])
                        top = min(top, bounds[1])
                        right = max(right, bounds[2])
                        bottom = max(bottom, bounds[3])
                        count += pixels
        clusters.append((left, top, right, bottom, count))
    boxes = []
    for index, (left, top, right, bottom, count) in enumerate(
            sorted(clusters, key=lambda item: (item[1], item[0])), 1):
        column = min(2, int(((left + right) / 2) * 3 / width))
        row = min(2, int(((top + bottom) / 2) * 3 / height))
        boxes.append({
            "id": index, "x": left, "y": top,
            "w": right - left, "h": bottom - top,
            "zone": ZONE_NAMES[row][column],
            "percent": round(mask.crop((left, top, right, bottom)).histogram()[255]
                             / total * 100, 3),
            "label": "unexpected", "approved": False,
        })
    return boxes


def compare_images(before_png, after_png, diff_png, tolerance=0):
    """Write a diff and return metrics, or {status: error, error: reason}.

    The caller supplies the output location (normally inside its store).
    Size mismatches have zero counted pixels because no aligned comparison
    exists; the note and fail status identify this condition.
    """
    try:
        _tolerance(tolerance)
        diff_png = Path(diff_png)
        if diff_png.is_symlink() or (diff_png.exists() and diff_png.stat().st_nlink > 1):
            raise ValueError("diff output must not be a link")
        with Image.open(before_png) as source:
            before = source.convert("RGB")
        with Image.open(after_png) as source:
            after = source.convert("RGB")
        width, height = after.size
        dimmed = ImageEnhance.Brightness(after).enhance(0.35)
        result = {"status": "fail", "changed_px": 0,
                  "changed_percent": 0.0, "boxes": [],
                  "size": {"width": width, "height": height}}
        if before.size != after.size:
            dimmed.save(diff_png, format="PNG")
            result["note"] = "size_mismatch"
            return result
        channels = ImageChops.difference(before, after).split()
        maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]),
                                    channels[2])
        mask = maximum.point([255 if i > tolerance else 0 for i in range(256)])
        changed = mask.histogram()[255]
        total = width * height
        percent = changed / total * 100
        result.update(status=("pass" if changed == 0 else
                              "fail" if percent >= FAIL_PERCENT else "check"),
                      changed_px=changed, changed_percent=round(percent, 3),
                      boxes=_boxes(mask, total))
        Image.composite(Image.new("RGB", after.size, "red"), dimmed, mask).save(
            diff_png, format="PNG")
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def compare(name, url, store_dir, tolerance=0):
    """Capture against a baseline and persist report.json; never raise."""
    from .capture import capture, validate_url
    from .report_json import build_report, write_report
    from .store import _case_dir, _metadata, _read_metadata

    try:
        _tolerance(tolerance)
        validation = validate_url(url)
        if validation is not None:
            raise ValueError(validation)
        case = _case_dir(store_dir, name, create=False)
        old_meta = _read_metadata(case / "metadata.json")
        viewport = old_meta["viewport"]
        browser = old_meta["browser"]
        if not capture(url, case / "current.png", browser=browser,
                       width=viewport["width"], height=viewport["height"]):
            raise RuntimeError("browser capture failed")
        result = compare_images(case / "baseline.png", case / "current.png",
                                case / "diff.png", tolerance)
        if result["status"] == "error":
            return result
        metadata = _metadata(browser, viewport["width"], viewport["height"], tolerance)
        report = build_report(name, result, metadata)
        if report.get("status") == "error":
            return report
        saved = write_report(report, case / "report.json")
        if saved.get("status") == "error":
            return saved
        return report
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
