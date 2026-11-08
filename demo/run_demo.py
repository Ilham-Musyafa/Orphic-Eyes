"""Run the local Lumen scenario; python -B demo/run_demo.py --repeat 2."""

import argparse
import copy
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from engine import baseline, compare
from engine.report_html import DEFAULT_TEMPLATE, PLACEHOLDER
from engine.report_json import write_report
from engine.requests import validate_requests

TAG = '<script type="application/json" id="orphic-report">'
OUTPUT = DEMO / "output"


def clean_output():
    """Remove only this demo's generated files, refusing links or unknown files."""
    if OUTPUT.is_symlink() or OUTPUT.resolve() != DEMO / "output":
        raise RuntimeError("Output must be the unredirected demo/output directory")
    if not OUTPUT.exists():
        return
    allowed = {"before.png", "after.png", "diff.png", "report.json", "report.html",
               "repeatability.json", "crops"}
    if not OUTPUT.is_dir() or any(p.name not in allowed for p in OUTPUT.iterdir()):
        raise RuntimeError("Output contains unrecognized files; refusing cleanup")
    for path in OUTPUT.rglob("*"):
        if (path.is_symlink() or not path.resolve().is_relative_to(OUTPUT.resolve())
                or (path.is_file() and path.stat().st_nlink > 1)):
            raise RuntimeError("Output contains a linked or redirected path")
    shutil.rmtree(OUTPUT)


def check_export():
    report = json.loads((OUTPUT / "report.json").read_text(encoding="utf-8"))
    page = (OUTPUT / "report.html").read_text(encoding="utf-8")
    assert page.count(PLACEHOLDER) == 0, "Unexpanded template marker"
    assert page.count(TAG) == 1, "Expected exactly one embedded report"
    embedded = json.loads(page.split(TAG, 1)[1].split("</script>", 1)[0])
    assert embedded == report, "HTML and JSON reports differ"
    assert report["schema_version"] == 1
    paths = [*report["images"].values(), report["meta"]["browser"]]
    for item in report["crops"]["items"]:
        paths.extend(item[side]["path"] for side in ("before", "after") if item[side])
    for path in paths:
        assert path and not Path(path).is_absolute() and not PureWindowsPath(path).is_absolute(), path
        assert ":" not in path and not path.startswith(("/", "\\")), path
        assert (OUTPUT / path).is_file(), path
    for filename in ("before.png", "after.png"):
        with Image.open(OUTPUT / filename) as image:
            assert image.size == (1280, 720), image.size
    return report


def run_once(requests):
    clean_output()
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=DEMO) as staging:
        store = Path(staging)
        saved = baseline("scenario", (DEMO / "pages/before.html").as_uri(), store,
                         width=1280, height=720)
        if saved["status"] != "pass":
            raise RuntimeError(f"Real browser baseline failed: {saved}")
        result = compare("scenario", (DEMO / "pages/after.html").as_uri(), store,
                         requests=requests, focus=True)
        if result["status"] == "error" or "html_error" in result:
            raise RuntimeError(f"Real engine compare/HTML failed: {result}")
        case = store / "scenario"
        report = json.loads((case / "report.json").read_text(encoding="utf-8"))
        OUTPUT.mkdir()
        for source, destination in (("baseline.png", "before.png"),
                                    ("current.png", "after.png"), ("diff.png", "diff.png")):
            shutil.copyfile(case / source, OUTPUT / destination)
        shutil.copytree(case / "crops", OUTPUT / "crops")
        # Export filenames/provenance only; keep the real pixel metrics and verdicts.
        report = copy.deepcopy(report)
        report["images"] = {"before": "before.png", "after": "after.png", "diff": "diff.png"}
        report["meta"]["browser"] = Path(os.path.relpath(report["meta"]["browser"], OUTPUT)).as_posix()
        written = write_report(report, OUTPUT / "report.json")
        if written["status"] == "error" or "html_error" in written:
            raise RuntimeError(f"Real engine HTML export failed: {written}")
    return check_export()


def signature(report):
    return {key: report[key] for key in ("schema_version", "status", "summary", "boxes",
                                        "request_results", "requests_ok", "request_counts")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1, choices=range(1, 11),
                        help="Clean and rerun; require identical metrics, boxes and verdicts")
    args = parser.parse_args()
    requests = validate_requests(json.loads((DEMO / "requests.json").read_text(encoding="utf-8")))
    template = DEFAULT_TEMPLATE.read_bytes()
    runs = []
    for index in range(args.repeat):
        report = run_once(requests)
        snapshot = signature(report)
        runs.append(snapshot)
        print(f"Run {index + 1}: " + json.dumps(snapshot, ensure_ascii=True))
        expected = ["done", "not_done", "unknown"]
        assert [row["status"] for row in report["request_results"]] == expected, "Unexpected real verdicts"
        assert all("budget" not in row["why"].lower() for row in report["request_results"]), "Timeout is not a demo verdict"
        assert report["summary"]["unexpected_count"] >= 1, "Missing unexpected area"
        assert snapshot == runs[0], "Demo results changed between runs"
    assert DEFAULT_TEMPLATE.read_bytes() == template, "Template changed during demo"
    (OUTPUT / "repeatability.json").write_text(
        json.dumps({"runs": runs, "identical": True, "html_checks": {
            "marker_count": 0, "json_script_count": 1, "embedded_equals_report": True,
            "relative_paths_verified": True}}, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(runs)} clean run(s); output: {OUTPUT}")


if __name__ == "__main__":
    main()
