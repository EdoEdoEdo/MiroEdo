"""Tests for baseline_report renderer."""

from __future__ import annotations

from app.postprocess.baseline_report import render_baseline_report
from app.schemas import BrandSeed, Segment, TimelineEvent, Topic


def _seed() -> BrandSeed:
    return BrandSeed(
        brand="Acme",
        market="IT",
        language="it",
        monitoring_window_days=14,
        total_mentions=1234,
        overall_sentiment=0.25,
        segments=[
            Segment(
                name="Famiglie",
                weight=0.7,
                description="Famiglie con bambini",
                sentiment_baseline="positive",
                sample_quotes=["I bambini adorano"],
            ),
            Segment(
                name="Critici",
                weight=0.3,
                description="Consumatori critici",
                sentiment_baseline="negative",
                sample_quotes=[],
            ),
        ],
        topics=[
            Topic(name="Qualità", mentions=800, sentiment_score=0.4, sample_quotes=["Buono"]),
            Topic(name="Prezzo", mentions=400, sentiment_score=-0.2, sample_quotes=[]),
        ],
        timeline=[TimelineEvent(date="2025-09-01", label="Lancio promo", mentions=100, note="")],
        source="brandwatch_csv",
    )


def test_render_contains_brand_and_chapters() -> None:
    md = render_baseline_report(_seed())
    assert "# Acme" in md
    assert "## 01 Segmenti audience" in md
    assert "## 02 Topic principali" in md
    assert "## 03 Timeline" in md
    assert "## 04 Predizioni baseline" in md
    assert "Famiglie" in md and "Qualità" in md


def test_render_segment_share_and_quote() -> None:
    md = render_baseline_report(_seed())
    assert "70.0%" in md  # Famiglie share
    assert "> I bambini adorano" in md


def test_render_omits_timeline_when_empty() -> None:
    seed = _seed()
    seed.timeline = []
    md = render_baseline_report(seed)
    assert "## 03 Timeline" not in md
