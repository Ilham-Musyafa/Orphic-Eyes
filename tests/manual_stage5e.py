"""Orphic Eyes: python -m tests.manual_stage5e; real captures, no Hermes install."""

import json
from pathlib import Path
import tempfile

from engine import accept, baseline, compare
from engine.capture import detect_browser


def main():
    root = Path(__file__).resolve().parents[1]
    browser = detect_browser()
    assert browser and Path(browser).name.lower() == "msedge.exe", browser
    print("Browser:", browser)
    with tempfile.TemporaryDirectory(dir=root / ".stage5", prefix="manual-5e-") as folder:
        fixtures = root / "tests" / "fixtures"
        saved = baseline("manual", (fixtures / "pattern_104.html").as_uri(), folder)
        assert saved["status"] == "pass", saved
        request = {"id": "PT-1", "type": "move", "precision": "exact",
                   "from": {"x": 104, "y": 180, "w": 190, "h": 48},
                   "to": {"x": 74, "y": 180, "w": 190, "h": 48}}
        compared = compare("manual", (fixtures / "pattern_74.html").as_uri(), folder,
                           requests=[request], focus=True)
        assert compared["status"] == "pass" and compared["requests_ok"], compared
        print("baseline: pass; compare: pass; requests: 1 done")
        accepted = accept("manual", folder)
        assert accepted["status"] == "pass", accepted
        print("accept: pass")
        case = Path(folder) / "manual"
        report = json.loads((case / "report.json").read_text(encoding="utf-8"))
        assert report["note"] == "baseline_accepted" and not report["boxes"]
        assert all(value == 0 for value in report["summary"].values())
        assert report["images"] == {"before": "baseline.png", "after": "baseline.png", "diff": None}
        assert not (case / "diff.png").exists() and not list((case / "crops").iterdir())
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
