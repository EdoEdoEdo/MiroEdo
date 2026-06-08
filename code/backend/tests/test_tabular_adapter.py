"""Test del BrandwatchCSVAdapter."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from app.ingestion.tabular_adapter import parse_csv


def _make_csv(rows: list[dict]) -> bytes:
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def test_parse_minimal_csv():
    csv = _make_csv(
        [
            {"Date": "2026-05-01", "Hit Sentence": "Adoro Mulino Bianco, sempre il top!"},
            {"Date": "2026-05-02", "Hit Sentence": "Prezzi troppo alti, deluso."},
        ]
    )
    seed = parse_csv(csv, brand="Mulino Bianco")
    assert seed.brand == "Mulino Bianco"
    assert seed.market == "IT"
    assert seed.total_mentions == 2
    assert seed.monitoring_window_days == 2
    # senza colonna sentiment → score 0
    assert seed.overall_sentiment == 0.0
    # senza segmentazione → un solo segmento generico
    assert len(seed.segments) == 1
    assert seed.segments[0].weight == 1.0


def test_parse_with_sentiment_and_country():
    csv = _make_csv(
        [
            {
                "Date": "2026-05-01",
                "Hit Sentence": "Top!",
                "Sentiment": "positive",
                "Country": "Italy",
            },
            {
                "Date": "2026-05-02",
                "Hit Sentence": "Male.",
                "Sentiment": "negative",
                "Country": "Italy",
            },
            {
                "Date": "2026-05-03",
                "Hit Sentence": "Nice.",
                "Sentiment": "positive",
                "Country": "Germany",
            },
        ]
    )
    seed = parse_csv(csv, brand="Test")
    assert seed.overall_sentiment == round((1 + (-1) + 1) / 3, 3)
    seg_names = {s.name for s in seed.segments}
    assert "Italy" in seg_names
    assert "Germany" in seg_names
    # peso Italia = 2/3
    italy = next(s for s in seed.segments if s.name == "Italy")
    assert italy.weight == round(2 / 3, 4)


def test_parse_with_topics():
    csv = _make_csv(
        [
            {"Date": "2026-05-01", "Hit Sentence": "x", "Topics": "qualità;prezzo"},
            {"Date": "2026-05-02", "Hit Sentence": "y", "Topics": "qualità"},
            {"Date": "2026-05-03", "Hit Sentence": "z", "Topics": "packaging"},
        ]
    )
    seed = parse_csv(csv, brand="T")
    topics_by_name = {t.name: t for t in seed.topics}
    assert topics_by_name["qualità"].mentions == 2
    assert topics_by_name["prezzo"].mentions == 1
    assert topics_by_name["packaging"].mentions == 1


def test_empty_csv_raises():
    buf = io.BytesIO(b"")
    with pytest.raises(Exception):
        parse_csv(buf.getvalue(), brand="X")


def test_csv_missing_text_column_raises():
    csv = _make_csv([{"Date": "2026-05-01", "Foo": "bar"}])
    with pytest.raises(ValueError, match="colonna testuale"):
        parse_csv(csv, brand="X")


def test_timeline_built_from_dates():
    # Use dates spanning different ISO weeks to verify weekly aggregation.
    csv = _make_csv(
        [
            {"Date": "2026-05-04", "Hit Sentence": "a"},  # week 19
            {"Date": "2026-05-05", "Hit Sentence": "b"},  # week 19
            {"Date": "2026-05-12", "Hit Sentence": "c"},  # week 20
        ]
    )
    seed = parse_csv(csv, brand="T")
    assert len(seed.timeline) == 2
    assert seed.timeline[0].mentions == 2
    assert seed.timeline[1].mentions == 1
