"""Run real local-browser captures and verify the supplied report template."""

import json
from pathlib import Path, PureWindowsPath
import tempfile

from engine import baseline, compare
from engine.report_html import DEFAULT_TEMPLATE, PLACEHOLDER, write_report_html


TAG = '<script type="application/json" id="orphic-report">'


def embedded(path):
    page = path.read_text(encoding="utf-8")
    assert PLACEHOLDER not in page
    assert page.count(TAG) == 1
    raw = page.split(TAG, 1)[1].split("</script>", 1)[0]
    data = json.loads(raw)
    assert data["schema_version"] == 1
    return raw, data


def main():
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "tests" / "fixtures"
    source = DEFAULT_TEMPLATE.read_text(encoding="utf-8")
    assert source.count(PLACEHOLDER) == 1 and TAG not in source
    folder = Path(tempfile.mkdtemp(prefix="orphic-html-integration-"))
    before, after = fixtures / "pattern_104.html", fixtures / "pattern_74.html"
    saved = baseline("real", before.as_uri(), folder)
    assert saved["status"] == "pass", saved
    request = {"id": "PT-1", "type": "move", "precision": "exact",
               "from": {"x": 104, "y": 180, "w": 190, "h": 48},
               "to": {"x": 74, "y": 180, "w": 190, "h": 48}}
    result = compare("real", after.as_uri(), folder, requests=[request], focus=True)
    assert result["status"] == "pass" and result["requests_ok"], result
    assert "html_error" not in result, result
    case = folder / "real"
    raw, report = embedded(case / "report.html")
    assert report == json.loads((case / "report.json").read_text(encoding="utf-8"))
    paths = list(report["images"].values())
    for item in report["crops"]["items"]:
        for side in ("before", "after"):
            if item[side]:
                assert set(item[side]) == {"path", "bbox", "scale", "size"}
                paths.append(item[side]["path"])
    for path in paths:
        assert path and not Path(path).is_absolute() and not PureWindowsPath(path).is_absolute()
        assert ":" not in path and not path.startswith(("/", "\\"))
        assert (case / path).is_file(), path
    hostile = '</script><script>alert("test")</script><!--'
    safety = folder / "safety"
    safety.mkdir()
    safety_report = {**report, "note": hostile}
    (safety / "report.json").write_text(json.dumps(safety_report), encoding="utf-8")
    safety_raw, parsed = embedded(write_report_html(safety))
    assert "</" not in safety_raw and "<!--" not in safety_raw
    assert parsed == safety_report
    assert DEFAULT_TEMPLATE.read_text(encoding="utf-8") == source
    print("Real capture inputs:", before, "->", after)
    print("Compare: pass; requests: 1 done; HTML:", case / "report.html")
    print("a: marker count=0; b: JSON script count=1; c: JSON parses, schema_version=1, equals report.json")
    print("d: hostile </script> and <!-- escaped, JSON round-trip exact")
    print("e:", len(paths), "image/crop paths relative and present")
    print("Crop sides: path,bbox,scale,size; report size: width,height; box coordinates: x,y,w,h")


if __name__ == "__main__":
    main()
