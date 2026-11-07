"""Offline Stage 5c benchmark; run: python -m tests.benchmark_roundtrip."""

import json
import tempfile
import time
from unittest.mock import patch

from PIL import Image

from engine import baseline, compare
from tests.test_locate import texture


def main():
    before = Image.new("RGB", (1280, 720), "white")
    after = before.copy()
    requests = []
    for index in range(8):
        x, y = 64 + (index % 4) * 300, 100 + (index // 4) * 220
        needle = texture(190, 48, seed=index + 1)
        before.paste(needle, (x, y))
        after.paste(needle, (x - 30, y))
        requests.append({"id": "PT-" + str(index + 1), "type": "move", "precision": "exact",
                         "from": {"x": x, "y": y, "w": 190, "h": 48},
                         "to": {"x": x - 30, "y": y, "w": 190, "h": 48}})
    captured = before

    def capture(url, output, **kwargs):
        captured.save(output)
        return True

    measurements = []
    with tempfile.TemporaryDirectory(prefix="orphic-benchmark-") as folder, \
            patch("engine.store.detect_browser", return_value="browser.exe"), \
            patch("engine.store.capture", side_effect=capture), \
            patch("engine.capture.capture", side_effect=capture):
        result = baseline("benchmark", "http://localhost", folder, width=1280, height=720)
        assert result["status"] == "pass", result
        captured = after
        for _ in range(3):
            start = time.perf_counter()
            legacy = compare("benchmark", "http://localhost", folder)
            legacy_time = time.perf_counter() - start
            assert legacy["status"] in ("check", "fail"), legacy
            start = time.perf_counter()
            enhanced = compare("benchmark", "http://localhost", folder, requests=requests,
                               focus=True, shift_hints=True)
            enhanced_time = time.perf_counter() - start
            assert enhanced.get("requests_ok"), enhanced
            measurements.append({"legacy_s": round(legacy_time, 4), "enhanced_s": round(enhanced_time, 4),
                                 "extra_s": round(enhanced_time - legacy_time, 4)})
        print(json.dumps({"image": [1280, 720], "requests": 8, "crop": [190, 48],
                          "trials": measurements}, indent=2))


if __name__ == "__main__":
    main()
