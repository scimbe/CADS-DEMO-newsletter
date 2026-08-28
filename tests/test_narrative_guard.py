from src import narrative_guard

FACTS = {
    "days": [
        {"date": "2026-08-28", "tmax": 23.7, "tmin": 17.3, "precip_mm": 10.9, "wind_max_kmh": 19.8},
        {"date": "2026-08-29", "tmax": 21.1, "tmin": 15.5, "precip_mm": 1.5, "wind_max_kmh": 19.9},
        {"date": "2026-08-30", "tmax": 21.2, "tmin": 17.1, "precip_mm": 5.58, "wind_max_kmh": 23.1},
    ],
    "highlights": [
        {"id": "hottest_day", "label": "Warmest day", "value": 23.7, "unit": "°C", "date": "2026-08-28"},
        {"id": "total_precip", "label": "Total precipitation", "value": 30.9, "unit": "mm"},
    ],
}


def test_narrative_using_only_facts_numbers_passes():
    narrative = (
        "The warmest day reaches 23.7°C on the 28th, while total precipitation "
        "for the period is 30.9mm across the 3-day outlook."
    )
    result = narrative_guard.check_narrative(narrative, FACTS)
    assert result.ok, result.reason


def test_narrative_with_one_fabricated_number_is_rejected():
    narrative = "The warmest day reaches 23.7°C, roughly 15% above the seasonal norm."
    result = narrative_guard.check_narrative(narrative, FACTS)
    assert not result.ok
    assert 15.0 in result.violations


def test_narrative_with_completely_invented_stat_is_rejected():
    narrative = "Expect a scorching 41.2°C heatwave this week."
    result = narrative_guard.check_narrative(narrative, FACTS)
    assert not result.ok
    assert 41.2 in result.violations


def test_narrative_allows_rounding_within_tolerance():
    # 23.68 rounds to 23.7 which is a real value -- LLM rounding should not
    # be flagged as fabrication.
    narrative = "Temperatures peaked near 23.68 degrees."
    result = narrative_guard.check_narrative(narrative, FACTS)
    assert result.ok, result.reason


def test_narrative_with_no_numbers_passes_trivially():
    narrative = "A mild and unremarkable stretch of weather is expected."
    result = narrative_guard.check_narrative(narrative, FACTS)
    assert result.ok
    assert result.checked_numbers == []


def test_day_of_month_from_other_date_is_structurally_allowed():
    # "30th" matches the day-of-month of 2026-08-30, even though 30 is not
    # itself a tmax/tmin/precip/wind value.
    narrative = "Conditions shift by the 30th."
    result = narrative_guard.check_narrative(narrative, FACTS)
    assert result.ok, result.reason
