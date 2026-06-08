"""Test del KPIExtractor usando la fixture Wuhan."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.postprocess.kpi_extractor import extract_kpi


def _locate_fixture() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "fixtures" / "wuhan_report_reference.md"
        if candidate.exists():
            return candidate
    return None


FIXTURE = _locate_fixture()


@pytest.fixture
def wuhan_report() -> str:
    if FIXTURE is None:
        pytest.skip("wuhan_report_reference.md fixture not available in this runtime")
    return FIXTURE.read_text(encoding="utf-8")


def test_extracts_known_percentage_from_wuhan(wuhan_report: str):
    """Il report Wuhan cita '67% of video content' su Douyin."""
    kpi = extract_kpi(wuhan_report)
    values = [p["value"] for p in kpi.percentages_found]
    assert 67.0 in values


def test_finds_48h_timeframe(wuhan_report: str):
    """Il report predice un picco 'within 48 hours'."""
    kpi = extract_kpi(wuhan_report)
    timeframes = [t.timeframe for t in kpi.timeframes_found]
    assert any("48" in tf for tf in timeframes)


def test_counts_three_chapters(wuhan_report: str):
    """La fixture ha 3 capitoli (## 01, ## 02, ## 03)."""
    kpi = extract_kpi(wuhan_report)
    assert kpi.chapter_count == 3


def test_finds_segments_media_and_platforms(wuhan_report: str):
    kpi = extract_kpi(wuhan_report)
    assert "media" in kpi.segments_mentioned
    assert "platforms" in kpi.segments_mentioned or "platform" in kpi.segments_mentioned


def test_word_count_positive(wuhan_report: str):
    kpi = extract_kpi(wuhan_report)
    assert kpi.word_count > 500


def test_blockquotes_detected(wuhan_report: str):
    kpi = extract_kpi(wuhan_report)
    # la fixture ha molti blockquote con le citazioni in-character
    assert kpi.blockquote_count >= 10


def test_predictive_conclusions_counted(wuhan_report: str):
    kpi = extract_kpi(wuhan_report)
    # ci sono almeno 2 sezioni "Predictive Conclusion" con liste numerate 1-5
    assert kpi.predictive_conclusion_count >= 10
