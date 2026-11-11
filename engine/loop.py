"""One bounded, pixel-only review round; Hermes performs any code edits.

The previous image supplies the round-to-round report. Completion always uses
immutable reference pixels/requests, so an unchanged wrong page is never done.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image, ImageChops

from .compare import compare_images
from .regions import _bounds, _clip, _regions
from .report_json import build_report, write_report
from .requests import check_bounds, expected_for_requests, validate_requests, verify_requests
from .serve import attach_report_link, default_store
from .store import _atomic_json, _case_dir, _metadata, _read_metadata, _read_options
from .url_capture import CaptureError, _options, capture, validate_url


def _file(folder, name):
    path = folder / name
    if (path.is_symlink() or path.resolve().parent != folder.resolve() or
            path.exists() and (not path.is_file() or path.stat().st_nlink != 1)):
        raise ValueError("Loop artifacts must be regular files without links")
    return path


def _directory(parent, name, create=False):
    path = parent / name
    if path.is_symlink() or path.resolve() != parent.resolve() / name or path.exists() and not path.is_dir():
        raise ValueError("Loop directories must not redirect")
    if create:
        path.mkdir(exist_ok=True)
    return path


@contextmanager
def _lock(case):
    path = _file(case, ".loop-lock")
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Loop is busy; if a process crashed, remove its stale .loop-lock only after confirming it stopped") from None
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def _load(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Loop state is too large")
    return json.loads(path.read_text(encoding="utf-8"))


def _session(case, requests, max_rounds):
    folder = _directory(case, "loop")
    if not folder.exists():
        metadata = _read_metadata(case / "metadata.json")
        reference = _file(case, "baseline.png")
        initial = _file(case, "current.png")
        if not initial.exists():
            initial = reference
        ignored, _ = _read_options(case)
        if requests:
            with Image.open(reference) as image:
                for request in requests:
                    if request["type"] != "comment":
                        check_bounds(request["from"], image.size, "from")
                        check_bounds(request.get("to", request["from"]), image.size, "to")
        with tempfile.TemporaryDirectory(prefix=".loop-init_", dir=case) as temporary:
            stage = Path(temporary)
            shutil.copyfile(reference, stage / "reference.png")
            shutil.copyfile(initial, stage / "initial.png")
            comparison = compare_images(reference, initial, stage / "initial-diff.png", ignore_regions=ignored)
            if comparison["status"] == "error":
                raise ValueError("Loop reference images could not be compared")
            config = {"version": 1, "mode": "requests" if requests else "restore", "requests": requests or [],
                      "max_rounds": max_rounds or 3, "viewport": metadata["viewport"],
                      "browser": metadata["browser"], "ignore_regions": ignored,
                      "initial_zones": comparison["boxes"], "initial_mismatch": comparison.get("note") == "size_mismatch"}
            _atomic_json(stage / "session.json", config)
            os.rename(stage, folder)
    config = _load(_file(folder, "session.json"))
    if config.get("version") != 1 or config.get("mode") not in ("requests", "restore"):
        raise ValueError("Unsupported loop session; use a fresh capture target")
    config["requests"] = validate_requests(config["requests"])
    config["ignore_regions"] = _regions(config["ignore_regions"], named=True)
    if requests is not None and requests != config["requests"]:
        raise ValueError("Loop requests are fixed for the session; use a fresh target to change goals")
    if max_rounds is not None and max_rounds != config["max_rounds"]:
        raise ValueError("max_rounds is fixed for the session")
    if isinstance(config["max_rounds"], bool) or not isinstance(config["max_rounds"], int) or config["max_rounds"] < 1:
        raise ValueError("Invalid loop round limit")
    return folder, config


def _history(folder):
    history = []
    for child in folder.iterdir():
        if child.name.startswith("round-"):
            if not re.fullmatch(r"round-[0-9]{3,}", child.name):
                raise ValueError("Invalid loop round directory")
            child = _directory(folder, child.name)
            data = _load(_file(child, "round.json"))
            if not isinstance(data.get("round"), int) or isinstance(data["round"], bool):
                raise ValueError("Invalid loop round state")
            history.append((data["round"], child, data))
    history.sort(key=lambda item: item[0])
    for number, (recorded, path, _) in enumerate(history, 1):
        if recorded != number or path.name != f"round-{number:03d}":
            raise ValueError("Loop history must be complete and consecutive")
    return history


def _goals(reference, current, config):
    mismatch = reference.size != current.size or config["initial_mismatch"]
    if config["mode"] == "requests":
        intents = config["requests"]
        for request in intents:
            if request["type"] != "comment":
                check_bounds(request["from"], reference.size, "from")
                check_bounds(request.get("to", request["from"]), reference.size, "to")
        verified = verify_requests(reference, current, intents)
        per_zone = [{**row, "bbox": request.get("from"),
                     "still_changed": False if row["status"] == "done" else True if row["status"] == "not_done" else None}
                    for request, row in zip(intents, verified["request_results"])]
        return per_zone, expected_for_requests(intents, reference.size), mismatch
    zones = config["initial_zones"]
    expected = _regions([{key: box[key] for key in ("x", "y", "w", "h")} for box in zones])
    difference = ImageChops.difference(reference, current) if not mismatch else None
    if difference is not None:
        for region in _clip(config["ignore_regions"], reference.size):
            difference.paste((0, 0, 0), _bounds(region))
    result = []
    for index, (zone, rectangle) in enumerate(zip(zones, expected), 1):
        status = "unknown" if mismatch else "not_done" if difference.crop(_bounds(rectangle)).getbbox() else "done"
        result.append({"id": "Z" + str(index), "zone": zone["zone"], "bbox": rectangle, "status": status,
                       "still_changed": None if mismatch else status == "not_done",
                       "why": "Viewport mismatch" if mismatch else "Reference pixels still differ" if status == "not_done" else "Reference pixels restored"})
    return result, expected, mismatch


def _prompt(number, stop, per_zone, unexpected, reason):
    if stop == "done":
        return "Pixel review is complete for the listed goals. No further changes are requested."
    lines = [f"Pixel-only visual review, round {number}.",
             "Use the supplied reference and current screenshots; no page code or text was read by this reviewer."]
    if stop in ("needs_human", "max_rounds"):
        lines.append("Stop automatic retries and ask a person to review: " + reason)
    else:
        lines.append("Fix only the unresolved items below. Preserve other areas and the viewport.")
    for zone in per_zone:
        if zone["status"] in ("done", "skipped"):
            continue
        region = zone.get("bbox")
        location = ", ".join(f"{key}={region[key]}" for key in ("x", "y", "w", "h")) if region else "no pixel rectangle"
        instruction = zone.get("instruction", "Restore this area to the reference screenshot pixels")
        lines.append(f"- {zone['id']} ({location}): {instruction}. {zone.get('why', '')}")
    for box in unexpected:
        location = ", ".join(f"{key}={box[key]}" for key in ("x", "y", "w", "h"))
        lines.append(f"- Unexpected {box['zone']} change ({location}): restore the reference appearance.")
    lines.append("Do not guess labels, text, DOM identity or implementation details from this pixel result. Explain your edits; have the reviewer recapture before continuing.")
    return "\n".join(lines)


def loop_step(name, after_url, store_dir=None, requests=None, *, max_rounds=None,
              allow_local=False, wait_ms=250, timeout_ms=30000, browser=None):
    """Execute one round against an existing baseline/capture-pair target.

    Effective max_rounds defaults to 3 and is fixed on the first call. Explicit
    requests use existing baseline-relative Point & Tell semantics. Without
    requests, the initial changed boxes must return to the original reference.
    No source URL is stored, and this function never edits code or sends prompts.
    """
    try:
        _options(1, 1, False, wait_ms, timeout_ms, allow_local)
        if max_rounds is not None and (isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or max_rounds < 1):
            raise ValueError("max_rounds must be a positive integer")
        intents = validate_requests(requests) if requests is not None else None
        error = validate_url(after_url, allow_local=allow_local, timeout=min(5, timeout_ms / 1000))
        if error:
            raise CaptureError(error)
        root = Path(store_dir if store_dir is not None else default_store()).resolve()
        case = _case_dir(root, name, create=False)
        if case.is_symlink() or case.resolve() != root / name:
            raise ValueError("Loop target must not redirect")
        with _lock(case):
            folder, config = _session(case, intents, max_rounds)
            history = _history(folder)
            if history and history[-1][2]["should_stop"]:
                last = history[-1]
                return attach_report_link({**last[2], "already_stopped": True}, root, last[1])
            number = len(history) + 1
            previous = _file(history[-1][1], "current.png") if history else _file(folder, "initial.png")
            reference_path = _file(folder, "reference.png")
            destination = folder / f"round-{number:03d}"
            with tempfile.TemporaryDirectory(prefix=".round_", dir=folder) as temporary:
                stage = Path(temporary)
                shutil.copyfile(previous, stage / "baseline.png")
                viewport = config["viewport"]
                capture(after_url, stage / "current.png", width=viewport["width"], height=viewport["height"],
                        allow_local=allow_local, wait_ms=wait_ms, timeout_ms=timeout_ms,
                        browser=browser or os.environ.get("ORPHIC_BROWSER") or config["browser"])
                with Image.open(reference_path) as original, Image.open(stage / "current.png") as latest:
                    reference, current = original.convert("RGB"), latest.convert("RGB")
                    per_zone, expected, mismatch = _goals(reference, current, config)
                if config["mode"] == "requests":
                    for zone, request in zip(per_zone, config["requests"]):
                        zone["instruction"] = ("Comment requires human review" if request["type"] == "comment" else
                            "Hide the reference crop within the bounded search area" if request["type"] == "hide" else
                            "Restore the reference crop at its original position" if request["type"] == "revert" else
                            "Move the reference crop to " + ", ".join(f"{key}={request['to'][key]}" for key in ("x", "y", "w", "h")))
                delta = compare_images(stage / "baseline.png", stage / "current.png", stage / "diff.png",
                                       ignore_regions=config["ignore_regions"], expected_regions=expected)
                goal = compare_images(reference_path, stage / "current.png", stage / "goal-diff.png",
                                      ignore_regions=config["ignore_regions"], expected_regions=expected)
                if delta["status"] == "error" or goal["status"] == "error":
                    raise ValueError("Loop image comparison failed")
                unexpected = [box for box in goal["boxes"] if box["label"] == "unexpected" and not box["approved"]]
                failing = sum(zone["status"] == "not_done" for zone in per_zone)
                unknown = sum(zone["status"] in ("unknown", "skipped") for zone in per_zone)
                mismatch = mismatch or delta.get("note") == "size_mismatch" or goal.get("note") == "size_mismatch"
                if mismatch or unknown:
                    stop, reason = "needs_human", "Viewport mismatch or a pixel request is ambiguous, skipped or outside the search budget."
                elif not failing and not unexpected:
                    stop, reason = "done", "All fixed pixel goals are satisfied; no unexpected zones remain."
                elif number >= config["max_rounds"]:
                    stop, reason = "max_rounds", "The configured round limit was reached with unresolved pixel differences."
                else:
                    stop, reason = "continue", "Unresolved goals or unexpected pixel zones remain."
                metadata = _metadata(config["browser"], viewport["width"], viewport["height"], 0)
                report = write_report(build_report(f"{name}-round-{number}", delta, metadata), stage / "report.json")
                if report["status"] == "error":
                    raise ValueError("Loop round report could not be written")
                _atomic_json(stage / "metadata.json", metadata)
                prompt = _prompt(number, stop, per_zone, unexpected, reason)
                (stage / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
                paths = {"report": str(destination / "report.json"), "round": str(destination / "round.json"),
                         "prompt": str(destination / "prompt.txt"), "reference": str(reference_path),
                         "previous": str(destination / "baseline.png"), "after": str(destination / "current.png"),
                         "diff": str(destination / "diff.png"), "goal_diff": str(destination / "goal-diff.png")}
                if (stage / "report.html").is_file():
                    paths["html"] = str(destination / "report.html")
                result = {"success": True, "name": name, "round": number, "max_rounds": config["max_rounds"],
                          "status": delta["status"], "stop_condition": stop, "should_stop": stop != "continue",
                          "reason": reason, "goal_mode": config["mode"], "per_zone": per_zone,
                          "zone_count": len(per_zone), "failing_count": failing, "unknown_count": unknown,
                          "unexpected_zones": unexpected, "unexpected_count": len(unexpected),
                          "round_changes": delta["boxes"], "summary": {"changed_percent": delta["changed_percent"],
                              "changed_px": delta["changed_px"], "box_count": len(delta["boxes"])},
                          "follow_up_prompt": prompt, "paths": paths}
                _atomic_json(stage / "round.json", result)
                os.rename(stage, destination)
            return attach_report_link(result, root, destination)
    except (CaptureError, ValueError) as exc:
        return {"success": False, "status": "error", "error": str(exc)}
    except Exception:
        return {"success": False, "status": "error", "error": "Loop step failed; check the target state, output access and browser availability"}


orphic_loop_step = loop_step
