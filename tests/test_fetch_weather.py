import json
from pathlib import Path

import pytest
import responses

from src import fetch_weather

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "fixtures" / "hamburg_forecast_sample.json"


def _fixture_json() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@responses.activate
def test_fetch_forecast_success_schema():
    fixture = _fixture_json()
    responses.add(
        responses.GET,
        "https://api.open-meteo.com/v1/forecast",
        json=fixture,
        status=200,
    )
    result = fetch_weather.fetch_forecast(
        base_url="https://api.open-meteo.com/v1/forecast",
        latitude=53.5511,
        longitude=9.9937,
        timezone="Europe/Berlin",
        forecast_days=7,
    )
    assert result.raw_json == fixture
    assert len(result.raw_json["daily"]["time"]) == 7
    for key in ("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"):
        assert key in result.raw_json["daily"]
        assert len(result.raw_json["daily"][key]) == 7
    assert result.sha256 == __import__("hashlib").sha256(result.raw_bytes).hexdigest()
    assert result.source_url.startswith("https://api.open-meteo.com/v1/forecast?")


@responses.activate
def test_fetch_forecast_http_error_raises():
    responses.add(
        responses.GET,
        "https://api.open-meteo.com/v1/forecast",
        json={"error": True, "reason": "bad params"},
        status=400,
    )
    with pytest.raises(fetch_weather.FetchError):
        fetch_weather.fetch_forecast(
            base_url="https://api.open-meteo.com/v1/forecast",
            latitude=53.5511,
            longitude=9.9937,
            timezone="Europe/Berlin",
            forecast_days=7,
        )


@responses.activate
def test_fetch_forecast_wrong_day_count_raises():
    fixture = _fixture_json()
    # truncate to simulate an API/schema drift
    fixture["daily"]["time"] = fixture["daily"]["time"][:3]
    responses.add(
        responses.GET,
        "https://api.open-meteo.com/v1/forecast",
        json=fixture,
        status=200,
    )
    with pytest.raises(fetch_weather.FetchError):
        fetch_weather.fetch_forecast(
            base_url="https://api.open-meteo.com/v1/forecast",
            latitude=53.5511,
            longitude=9.9937,
            timezone="Europe/Berlin",
            forecast_days=7,
        )


@responses.activate
def test_fetch_forecast_missing_variable_raises():
    fixture = _fixture_json()
    del fixture["daily"]["wind_speed_10m_max"]
    responses.add(
        responses.GET,
        "https://api.open-meteo.com/v1/forecast",
        json=fixture,
        status=200,
    )
    with pytest.raises(fetch_weather.FetchError):
        fetch_weather.fetch_forecast(
            base_url="https://api.open-meteo.com/v1/forecast",
            latitude=53.5511,
            longitude=9.9937,
            timezone="Europe/Berlin",
            forecast_days=7,
        )


def test_build_url_contains_expected_params():
    url = fetch_weather.build_url(
        "https://api.open-meteo.com/v1/forecast", 53.5511, 9.9937, "Europe/Berlin", 7
    )
    assert "latitude=53.5511" in url
    assert "longitude=9.9937" in url
    assert "forecast_days=7" in url
    assert "temperature_2m_max" in url


@pytest.mark.live
def test_fetch_forecast_live_real_api():
    """Hits the real Open-Meteo API. Excluded from default `pytest` run
    (see pytest.ini) -- run explicitly with `pytest -m live`."""
    result = fetch_weather.fetch_forecast(
        base_url="https://api.open-meteo.com/v1/forecast",
        latitude=53.5511,
        longitude=9.9937,
        timezone="Europe/Berlin",
        forecast_days=7,
    )
    assert len(result.raw_json["daily"]["time"]) == 7
