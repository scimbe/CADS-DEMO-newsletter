import json
from pathlib import Path

from src import facts as facts_mod, render_report

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "fixtures" / "hamburg_forecast_sample.json"


def _fixture_facts() -> dict:
    raw = json.loads(FIXTURE_PATH.read_text())
    result = facts_mod.compute_facts(raw, "Hamburg, DE", 53.5511, 9.9937, "https://api.open-meteo.com/v1/forecast?test=1")
    return result.to_dict()


def test_render_html_contains_every_fetched_number_verbatim():
    facts_dict = _fixture_facts()
    selected = facts_dict["highlights"][:3]
    html = render_report.render_html(
        facts=facts_dict,
        selected_highlights=selected,
        narrative="The warmest day reaches 23.7°C.",
        report_title="Hamburg Weekly Weather Briefing",
        model_name="local-devstral-small2",
        llm_fallback_used=False,
        chart_temperature_path="chart-temperature.png",
        chart_precipitation_path="chart-precipitation.png",
    )

    # every daily number from the fetched data must appear in the rendered HTML
    for day in facts_dict["days"]:
        assert str(day["tmax"]) in html
        assert str(day["tmin"]) in html
        assert str(day["precip_mm"]) in html
        assert str(day["wind_max_kmh"]) in html
        assert day["date"] in html

    assert "Hamburg Weekly Weather Briefing" in html
    assert facts_dict["source_url"] in html
    assert "The warmest day reaches 23.7°C." in html
    assert "chart-temperature.png" in html
    assert "chart-precipitation.png" in html


def test_render_html_flags_fallback_narrative():
    facts_dict = _fixture_facts()
    html = render_report.render_html(
        facts=facts_dict,
        selected_highlights=facts_dict["highlights"][:2],
        narrative="Fallback sentence.",
        report_title="Hamburg Weekly Weather Briefing",
        model_name="local-devstral-small2 (fallback template, guard failed)",
        llm_fallback_used=True,
        chart_temperature_path="chart-temperature.png",
        chart_precipitation_path="chart-precipitation.png",
    )
    assert "deterministic fallback sentence" in html


def test_find_chrome_binary_finds_real_chrome():
    # This machine has google-chrome installed (verified during build); this
    # test would fail loudly (not silently skip) if that ever stops being true.
    path = render_report.find_chrome_binary()
    assert path
    assert Path(path).exists()
