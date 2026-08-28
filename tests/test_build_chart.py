import json
from pathlib import Path

from PIL import Image

from src import build_chart, facts as facts_mod

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "fixtures" / "hamburg_forecast_sample.json"


def _fixture_days() -> list[dict]:
    raw = json.loads(FIXTURE_PATH.read_text())
    result = facts_mod.compute_facts(raw, "Hamburg, DE", 53.5511, 9.9937, "u")
    return result.to_dict()["days"]


def _pixel_variance(path: Path) -> float:
    img = Image.open(path).convert("L")
    pixels = list(img.getdata())
    mean = sum(pixels) / len(pixels)
    return sum((p - mean) ** 2 for p in pixels) / len(pixels)


def test_render_temperature_chart_produces_real_png(tmp_path):
    days = _fixture_days()
    out_path = tmp_path / "temp.png"
    result = build_chart.render_temperature_chart(days, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 5_000  # a blank/trivial PNG would be far smaller
    assert _pixel_variance(out_path) > 100  # a solid/blank canvas has ~zero variance

    assert result.plotted_data["tmax"] == [d["tmax"] for d in days]
    assert result.plotted_data["tmin"] == [d["tmin"] for d in days]


def test_render_precipitation_chart_produces_real_png(tmp_path):
    days = _fixture_days()
    out_path = tmp_path / "precip.png"
    result = build_chart.render_precipitation_chart(days, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 5_000
    assert _pixel_variance(out_path) > 100

    assert result.plotted_data["precip_mm"] == [d["precip_mm"] for d in days]


def test_charts_use_real_fetched_numbers_not_placeholders(tmp_path):
    days = _fixture_days()
    out_path = tmp_path / "temp.png"
    result = build_chart.render_temperature_chart(days, out_path)
    # the known hottest-day value from the frozen fixture must appear
    # verbatim in the plotted array
    assert 23.7 in result.plotted_data["tmax"]
