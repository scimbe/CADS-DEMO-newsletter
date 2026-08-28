import json
from pathlib import Path

from src import facts as facts_mod

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "fixtures" / "hamburg_forecast_sample.json"


def _fixture_json() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def _by_id(highlights, hid):
    return next(h for h in highlights if h["id"] == hid)


def test_compute_facts_hand_verified_values():
    """Pins the exact ground-truth numbers against the frozen fixture.
    These were hand-computed from data/fixtures/hamburg_forecast_sample.json:

    tmax: 23.7 21.1 21.2 20.7 20.3 20.9 19.2   -> max=23.7 (day 0, 2026-08-28)
    tmin: 17.3 15.5 17.1 15.6 15.3 13.1 14.8   -> min=13.1 (day 5, 2026-09-02)
    precip: 10.9 1.5 5.58 8.7 3.6 0.3 0.3       -> max=10.9 (day 0); sum=30.88 -> 30.9
    wind: 19.8 19.9 23.1 16.1 13.5 12.1 21.4    -> max=23.1 (day 2, 2026-08-30)
    avg tmax = 147.1 / 7 = 21.0142857 -> 21.0
    avg tmin = 108.7 / 7 = 15.5285714 -> 15.5
    dry days (<1mm): 0.3, 0.3 -> 2
    """
    raw = _fixture_json()
    result = facts_mod.compute_facts(
        raw, location_name="Hamburg, DE", latitude=53.5511, longitude=9.9937,
        source_url="https://api.open-meteo.com/v1/forecast?test=1",
    )
    d = result.to_dict()

    assert len(d["days"]) == 7
    assert d["days"][0] == {
        "date": "2026-08-28", "tmax": 23.7, "tmin": 17.3, "precip_mm": 10.9, "wind_max_kmh": 19.8,
    }

    highlights = d["highlights"]
    assert _by_id(highlights, "hottest_day")["value"] == 23.7
    assert _by_id(highlights, "hottest_day")["date"] == "2026-08-28"
    assert _by_id(highlights, "coldest_day")["value"] == 13.1
    assert _by_id(highlights, "coldest_day")["date"] == "2026-09-02"
    assert _by_id(highlights, "wettest_day")["value"] == 10.9
    assert _by_id(highlights, "wettest_day")["date"] == "2026-08-28"
    assert _by_id(highlights, "windiest_day")["value"] == 23.1
    assert _by_id(highlights, "windiest_day")["date"] == "2026-08-30"
    assert _by_id(highlights, "week_avg_tmax")["value"] == 21.0
    assert _by_id(highlights, "week_avg_tmin")["value"] == 15.5
    assert _by_id(highlights, "total_precip")["value"] == 30.9
    assert _by_id(highlights, "dry_days")["value"] == 2.0

    assert d["location"] == "Hamburg, DE (53.56N, 10.00E)"
    assert d["source_url"] == "https://api.open-meteo.com/v1/forecast?test=1"


def test_compute_facts_is_deterministic():
    raw = _fixture_json()
    r1 = facts_mod.compute_facts(raw, "Hamburg, DE", 53.5511, 9.9937, "u")
    r2 = facts_mod.compute_facts(raw, "Hamburg, DE", 53.5511, 9.9937, "u")
    # generated_at is a timestamp, ignore it for equality
    d1, d2 = r1.to_dict(), r2.to_dict()
    d1.pop("generated_at"); d2.pop("generated_at")
    assert d1 == d2
