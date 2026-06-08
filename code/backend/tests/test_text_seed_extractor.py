"""Tests for ingestion.text_seed_extractor (Mistral mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ingestion.text_seed_extractor import TextSeedExtractor
from app.schemas import BrandSeed


def _good_payload() -> dict:
    return {
        "brand": "Mulino Bianco",
        "market": "IT",
        "language": "it",
        "monitoring_window_days": 30,
        "total_mentions": 1200,
        "overall_sentiment": 0.34,
        "segments": [
            {
                "name": "Famiglie",
                "weight": 0.6,
                "description": "Famiglie con bambini",
                "sentiment_baseline": "positive",
                "sample_quotes": ["I bambini adorano i biscotti"],
            },
            {
                "name": "Giovani adulti",
                "weight": 0.4,
                "description": "Millennial salutisti",
                "sentiment_baseline": "mixed",
                "sample_quotes": [],
            },
        ],
        "topics": [
            {"name": "Colazione", "mentions": 800, "sentiment_score": 0.5, "sample_quotes": []},
            {"name": "Zuccheri", "mentions": 200, "sentiment_score": -0.3, "sample_quotes": []},
        ],
        "timeline": [],
        "source": "brandwatch_pdf",
    }


def test_extract_happy_path() -> None:
    client = MagicMock()
    client.chat_json.return_value = _good_payload()
    seed = TextSeedExtractor(client=client).extract("Report Mulino Bianco Q3")

    assert isinstance(seed, BrandSeed)
    assert seed.brand == "Mulino Bianco"
    assert seed.source == "brandwatch_pdf"
    assert len(seed.segments) == 2
    assert pytest.approx(sum(s.weight for s in seed.segments), abs=1e-3) == 1.0


def test_extract_empty_text_raises() -> None:
    client = MagicMock()
    with pytest.raises(ValueError):
        TextSeedExtractor(client=client).extract("   ")
    client.chat_json.assert_not_called()


def test_extract_invalid_schema_raises() -> None:
    client = MagicMock()
    bad = _good_payload()
    # monitoring_window_days, sentiment_baseline and overall_sentiment are now
    # auto-clamped by _coerce_seed_payload. To still trigger a schema error we
    # break a structural field the coercer doesn't touch (segments shape).
    bad["segments"] = "not-a-list"
    client.chat_json.return_value = bad

    with pytest.raises(ValueError, match="BrandSeed schema"):
        TextSeedExtractor(client=client).extract("some text")


def test_extract_coerces_invalid_sentiment_baseline() -> None:
    client = MagicMock()
    payload = _good_payload()
    payload["segments"][0]["sentiment_baseline"] = "very positive"  # not in enum
    client.chat_json.return_value = payload

    seed = TextSeedExtractor(client=client).extract("report")
    assert seed.segments[0].sentiment_baseline == "positive"


def test_extract_clamps_out_of_range_window() -> None:
    client = MagicMock()
    payload = _good_payload()
    payload["monitoring_window_days"] = 9999
    payload["overall_sentiment"] = 2.5
    client.chat_json.return_value = payload

    seed = TextSeedExtractor(client=client).extract("report")
    assert seed.monitoring_window_days == 365
    assert seed.overall_sentiment == 1.0


def test_extract_forces_source_tag() -> None:
    client = MagicMock()
    payload = _good_payload()
    payload["source"] = "manual"  # LLM hallucinates wrong tag
    client.chat_json.return_value = payload

    seed = TextSeedExtractor(client=client).extract("report")
    assert seed.source == "brandwatch_pdf"


def test_extract_truncates_long_input() -> None:
    client = MagicMock()
    client.chat_json.return_value = _good_payload()
    extractor = TextSeedExtractor(client=client)
    extractor.extract("x" * 100_000, brand_hint="Mulino Bianco")

    # The user message passed must be capped + include hint
    args, kwargs = client.chat_json.call_args
    _system, user = args[0], args[1]
    assert "Mulino Bianco" in user
    assert len(user) < 30_000
