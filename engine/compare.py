"""Pillow-only image comparison and local screenshot comparison."""

from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

from .regions import _approvals, _bounds, _clip, _fingerprint, _key, _regions

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


def _boxes(mask, total, counts=None):
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
        if counts is not None:
            counts.append(count)
    return boxes


def _analyze(before, after, tolerance, ignored, expected, approvals, expected_labels=None):
    width, height = after.size
    ignored = _clip(ignored, after.size)
    dimmed = ImageEnhance.Brightness(after).enhance(0.35)
    result = {"status": "fail", "changed_px": 0, "changed_percent": 0.0,
              "boxes": [], "size": {"width": width, "height": height},
              "ignore_regions": ignored}
    if before.size != after.size:
        result["note"] = "size_mismatch"
        return result, dimmed
    channels = ImageChops.difference(before, after).split()
    maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    mask = maximum.point([255 if i > tolerance else 0 for i in range(256)])
    for region in ignored:
        mask.paste(0, _bounds(region))
    expected_mask = Image.new("L", after.size)
    for region in _clip(expected, after.size):
        expected_mask.paste(255, _bounds(region))
    total = width * height
    counts = []
    boxes = _boxes(mask, total, counts)
    unexpected_pixels = 0
    unexpected_count = 0
    for box, count in zip(boxes, counts):
        covered = expected_mask.crop(_bounds(box)).histogram()[255]
        is_expected = covered * 2 >= box["w"] * box["h"]
        if expected_labels is not None:
            is_expected = _key(box) in expected_labels
        box["label"] = "expected" if is_expected else "unexpected"
        box["approved"] = _fingerprint(after, box) in approvals
        if not is_expected and not box["approved"]:
            unexpected_pixels += count
            unexpected_count += 1
    changed = mask.histogram()[255]
    status = ("fail" if unexpected_pixels / total * 100 >= FAIL_PERCENT else
              "check" if unexpected_count else "pass")
    result.update(status=status, changed_px=changed,
                  changed_percent=round(changed / total * 100, 3), boxes=boxes)
    if status == "pass" and boxes:
        result["note"] = "only_expected_changes"
    diff = Image.composite(Image.new("RGB", after.size, "red"), dimmed, mask)
    return result, diff


def compare_images(before_png, after_png, diff_png, tolerance=0,
                   ignore_regions=None, expected_regions=None, approvals=None):
    """Write a diff and return metrics, or {status: error, error: reason}.

    The caller supplies the output location (normally inside its store).
    Size mismatches have zero counted pixels because no aligned comparison
    exists; the note and fail status identify this condition.
    """
    try:
        _tolerance(tolerance)
        ignored = _regions([] if ignore_regions is None else ignore_regions, named=True)
        expected = _regions(expected_regions)
        approved = _approvals([] if approvals is None else approvals)
        diff_png = Path(diff_png)
        if diff_png.is_symlink() or (diff_png.exists() and diff_png.stat().st_nlink > 1):
            raise ValueError("diff output must not be a link")
        with Image.open(before_png) as source:
            before = source.convert("RGB")
        with Image.open(after_png) as source:
            after = source.convert("RGB")
        result, diff = _analyze(before, after, tolerance, ignored, expected, approved)
        diff.save(diff_png, format="PNG")
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def compare(name, url, store_dir, tolerance=0, expected_regions=None, *, requests=None, focus=False):
    """Capture against a baseline and persist report.json; never raise."""
    from .capture import capture, validate_url
    from .report_json import build_report, write_report
    from .store import _case_dir, _metadata, _read_metadata, _read_options
    from .requests import check_bounds, expected_for_requests, validate_requests, verify_requests
    from .crops import validate_crops, write_crops

    try:
        _tolerance(tolerance)
        expected = _regions(expected_regions)
        intents = validate_requests(requests) if requests is not None else None
        if not isinstance(focus, bool):
            raise ValueError("focus must be a boolean")
        validation = validate_url(url)
        if validation is not None:
            raise ValueError(validation)
        case = _case_dir(store_dir, name, create=False)
        if focus or intents is not None:
            validate_crops(case)
        old_meta = _read_metadata(case / "metadata.json")
        if intents is not None:
            with Image.open(case / "baseline.png") as source:
                for intent in intents:
                    if intent["type"] != "comment":
                        check_bounds(intent["from"], source.size, "from")
                        check_bounds(intent.get("to", intent["from"]), source.size, "to")
                expected += expected_for_requests(intents, source.size)
        ignored, approvals = _read_options(case)
        viewport = old_meta["viewport"]
        browser = old_meta["browser"]
        if not capture(url, case / "current.png", browser=browser,
                       width=viewport["width"], height=viewport["height"]):
            raise RuntimeError("browser capture failed")
        result = compare_images(case / "baseline.png", case / "current.png",
                                case / "diff.png", tolerance, ignored, expected, approvals)
        if result["status"] == "error":
            return result
        metadata = _metadata(browser, viewport["width"], viewport["height"], tolerance)
        report = build_report(name, result, metadata)
        if report.get("status") == "error":
            return report
        if intents is not None or focus:
            with Image.open(case / "baseline.png") as before, Image.open(case / "current.png") as after:
                before, after = before.convert("RGB"), after.convert("RGB")
                if intents is not None:
                    report.update(verify_requests(before, after, intents))
                report["crops"] = write_crops(case, before, after, report)
        saved = write_report(report, case / "report.json")
        if saved.get("status") == "error":
            return saved
        return report
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
