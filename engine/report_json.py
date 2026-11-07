"""The version 1 report contract. No UI-specific fields."""

import json
from pathlib import Path


def result_message(report, visual_text=None):
    """Combine independent visual and request verdicts without implying success."""
    visual = visual_text or {"pass": "No unexpected changes", "check": "Check these changes",
                             "fail": "Review these visual regressions"}[report["status"]]
    counts = report.get("request_counts", {})
    if not any(counts.values()):
        return visual
    if report["requests_ok"]:
        detail = ", ".join(f"{counts[key]} {key}" for key in
                           ("done", "not_done", "unknown", "skipped") if counts.get(key))
        return visual + " | Requests: " + detail
    detail = ", ".join(f"{counts[key]} {key}" for key in ("not_done", "unknown") if counts.get(key))
    return "Requests incomplete (" + detail + ") | " + visual


def build_report(name, comparison, metadata):
    """Return the exact report schema, or a clear error dictionary."""
    try:
        boxes = comparison["boxes"]
        report = {
            "schema_version": 1,
            "name": name,
            "status": comparison["status"],
            "summary": {
                "changed_px": comparison["changed_px"],
                "changed_percent": comparison["changed_percent"],
                "box_count": len(boxes), "unexpected_count": sum(
                    box["label"] == "unexpected" and not box["approved"] for box in boxes),
            },
            "size": comparison["size"],
            "images": {"before": "baseline.png", "after": "current.png",
                       "diff": "diff.png"},
            "boxes": boxes,
            "ignore_regions": comparison.get("ignore_regions", []),
            "meta": {key: metadata[key] for key in (
                "browser", "os", "viewport", "created_at", "tolerance")},
        }
        if "note" in comparison:
            report["note"] = comparison["note"]
        return report
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def write_report(report, out_json):
    """Write UTF-8 JSON at the supplied store path, returning report or error."""
    try:
        path = Path(out_json)
        if "message" in report:
            report["message"] = result_message(report)
        if path.is_symlink() or (path.exists() and path.stat().st_nlink > 1):
            raise ValueError("report output must not be a link")
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=True, allow_nan=False)
            handle.write("\n")
        return report
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
