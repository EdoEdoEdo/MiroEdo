"""Tests per scenarios + forecast (Fase C)."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.postprocess.forecast import forecast_volume
from app.postprocess.scenarios import generate_scenarios
from app.schemas import BrandSeed, Segment, TimelineEvent, Topic


def _seed(timeline: list[TimelineEvent] | None = None) -> BrandSeed:
    return BrandSeed(
        brand="A2A",
        market="IT",
        monitoring_window_days=90,
        total_mentions=3000,
        overall_sentiment=-0.1,
        segments=[
            Segment(name="Italy", weight=0.6, description="IT", sentiment_baseline="negative"),
            Segment(name="Other", weight=0.4, description="other", sentiment_baseline="mixed"),
        ],
        topics=[
            Topic(name="Bolletta", mentions=320, sentiment_score=-0.18),
            Topic(name="Sostenibilità", mentions=831, sentiment_score=-0.02),
        ],
        timeline=timeline or [],
    )


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def test_scenarios_llm_happy_path():
    client = MagicMock()
    client.config.model = "mistral-test"
    client.chat_json.return_value = {
        "scenarios": [
            {"label": "best", "title": "Recupero", "narrative": "n" * 90, "probability": 0.3,
             "drivers": ["a", "b", "c"], "early_signals": ["s1", "s2"]},
            {"label": "base", "title": "Stabile", "narrative": "n" * 90, "probability": 0.5,
             "drivers": ["x", "y"], "early_signals": ["e"]},
            {"label": "worst", "title": "Crisi", "narrative": "n" * 90, "probability": 0.2,
             "drivers": ["k", "j", "h"], "early_signals": ["w1", "w2"]},
        ],
        "confidence": 0.7,
    }
    out = generate_scenarios(_seed(), horizon_weeks=4, client=client)
    assert out.model == "mistral-test"
    assert len(out.scenarios) == 3
    assert {s.label for s in out.scenarios} == {"best", "base", "worst"}
    assert out.confidence == pytest.approx(0.7)


def test_scenarios_fallback_on_llm_error():
    client = MagicMock()
    from app.llm.mistral import LLMError
    client.chat_json.side_effect = LLMError("boom")
    out = generate_scenarios(_seed(), horizon_weeks=4, client=client)
    assert out.model == "fallback"
    assert len(out.scenarios) == 3
    assert {s.label for s in out.scenarios} == {"best", "base", "worst"}


def test_scenarios_fallback_when_wrong_count():
    client = MagicMock()
    client.config.model = "m"
    client.chat_json.return_value = {"scenarios": [{"label": "best", "title": "x", "narrative": "y", "probability": 1.0}]}
    out = generate_scenarios(_seed(), client=client)
    assert out.model == "fallback"


# ---------------------------------------------------------------------------
# forecast
# ---------------------------------------------------------------------------


def _weekly_timeline(values: list[int], start: date = date(2025, 1, 6)) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            date=(start + timedelta(weeks=i)).isoformat(),
            label=f"settimana {i}",
            mentions=v,
        )
        for i, v in enumerate(values)
    ]


def test_forecast_insufficient_data():
    fc = forecast_volume(_seed(timeline=[]), horizon_weeks=4)
    assert fc.method == "insufficient_data"
    assert fc.forecast == []


def test_forecast_naive_mean_when_few_weeks():
    fc = forecast_volume(_seed(timeline=_weekly_timeline([10, 20, 30])), horizon_weeks=4)
    assert fc.method == "naive_mean"
    assert len(fc.forecast) == 4
    # mean = 20
    assert fc.forecast[0].yhat == pytest.approx(20.0)
    assert fc.forecast[0].yhat_lower < fc.forecast[0].yhat <= fc.forecast[0].yhat_upper


def test_forecast_holt_with_trend():
    values = [10, 12, 14, 16, 18, 20]  # +2/settimana
    fc = forecast_volume(_seed(timeline=_weekly_timeline(values)), horizon_weeks=4)
    assert fc.method == "holt_winters"
    assert len(fc.forecast) == 4
    # should keep trending up
    assert fc.forecast[-1].yhat > fc.forecast[0].yhat
    # widening CI
    band_first = fc.forecast[0].yhat_upper - fc.forecast[0].yhat_lower
    band_last = fc.forecast[-1].yhat_upper - fc.forecast[-1].yhat_lower
    assert band_last >= band_first


def test_forecast_no_negative_values():
    fc = forecast_volume(_seed(timeline=_weekly_timeline([100, 50, 20, 10, 5])), horizon_weeks=4)
    for p in fc.forecast:
        assert p.yhat >= 0
        assert p.yhat_lower >= 0
