"""Tests for ReportPipeline (quick mode, LLM mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.pipeline import PipelineResult, ReportPipeline
from app.schemas import ActionPlan, BrandSeed, ExecutiveSummary


FIXTURES = Path(__file__).parent / "fixtures"


def _mock_llm() -> MagicMock:
    client = MagicMock()
    client.config = MagicMock(model="mock-model")

    def chat_json(system: str, user: str, **_kw):
        if "Executive Summary" in system or "summary_it" in user:
            return {
                "summary_it": "Mulino Bianco mostra sentiment positivo nelle famiglie.",
                "key_findings": ["Famiglie +60%", "Topic colazione dominante"],
                "confidence": 0.7,
            }
        # action plan
        return {
            "actions": [
                {
                    "priority": 1,
                    "action": "Lanciare campagna social sul topic colazione",
                    "owner": "Marketing",
                    "timeframe_h": 48,
                    "rationale": "Topic dominante per le famiglie",
                    "kpi_target": "+5pp engagement entro 7gg",
                },
                {
                    "priority": 2,
                    "action": "Monitorare segmento giovani adulti",
                    "owner": "Insight",
                    "timeframe_h": 72,
                    "rationale": "Sentiment misto da approfondire",
                    "kpi_target": "report settimanale sentiment",
                },
            ]
        }

    client.chat_json.side_effect = chat_json
    return client


def test_pipeline_quick_with_brandwatch_csv() -> None:
    client = _mock_llm()
    pipeline = ReportPipeline(llm_client=client)

    result = pipeline.run(
        source_path=FIXTURES / "mulino_bianco_demo.csv",
        source_type="brandwatch_csv",
        brand_hint="Mulino Bianco",
        mode="quick",
    )

    assert isinstance(result, PipelineResult)
    assert result.mode == "quick"
    assert isinstance(result.brand_seed, BrandSeed)
    assert result.brand_seed.brand == "Mulino Bianco"
    assert "# Mulino Bianco" in result.report_markdown
    assert result.kpi.chapter_count >= 3
    assert isinstance(result.executive_summary, ExecutiveSummary)
    assert "Mulino Bianco" in result.executive_summary.summary_it
    assert isinstance(result.action_plan, ActionPlan)
    assert len(result.action_plan.actions) == 2
    assert result.simulation is None
    assert result.warnings == []


def test_pipeline_quick_with_pdf_bytes(tmp_path: Path) -> None:
    """Quick mode with a PDF input goes through TextSeedExtractor."""
    fitz = pytest.importorskip("fitz")
    # Build a real PDF
    pdf_path = tmp_path / "brief.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Mulino Bianco brand report Q3 - sentiment positivo nelle famiglie italiane.",
    )
    doc.save(str(pdf_path))
    doc.close()

    # Mock LLM: first call = TextSeedExtractor, then exec summary, then action plan
    client = MagicMock()
    client.config = MagicMock(model="mock-model")

    def chat_json(system: str, user: str, **_kw):
        if "BrandSeed" in system:
            return {
                "brand": "Mulino Bianco",
                "market": "IT",
                "language": "it",
                "monitoring_window_days": 30,
                "total_mentions": 500,
                "overall_sentiment": 0.4,
                "segments": [
                    {
                        "name": "Famiglie",
                        "weight": 1.0,
                        "description": "Famiglie italiane",
                        "sentiment_baseline": "positive",
                        "sample_quotes": [],
                    }
                ],
                "topics": [
                    {
                        "name": "Colazione",
                        "mentions": 500,
                        "sentiment_score": 0.4,
                        "sample_quotes": [],
                    }
                ],
                "timeline": [],
                "source": "brandwatch_pdf",
            }
        if "Executive Summary" in system or "summary_it" in user:
            return {
                "summary_it": "Mulino Bianco performa bene su famiglie.",
                "key_findings": ["Sentiment +0.4"],
                "confidence": 0.6,
            }
        return {"actions": []}

    client.chat_json.side_effect = chat_json

    pipeline = ReportPipeline(llm_client=client)
    result = pipeline.run(
        source_bytes=pdf_path.read_bytes(),
        source_filename="brief.pdf",
        source_type="brandwatch_pdf",
        mode="quick",
    )

    assert result.brand_seed.source == "brandwatch_pdf"
    assert "Mulino Bianco" in result.report_markdown


def test_pipeline_full_mode_runs_without_simulation() -> None:
    """`full` mode is identical to `quick` for the base report; simulation is
    now triggered separately via `simulate_only`."""
    pipeline = ReportPipeline(llm_client=_mock_llm())
    result = pipeline.run(
        source_path=FIXTURES / "mulino_bianco_demo.csv",
        source_type="brandwatch_csv",
        brand_hint="Mulino Bianco",
        mode="full",
    )
    assert result.mode == "full"
    assert result.simulation is None


def test_simulate_only_gracefully_falls_back() -> None:
    """On Python 3.9 local runtime, OASIS engine import fails → graceful return."""
    pipeline = ReportPipeline(llm_client=_mock_llm())
    result = pipeline.run(
        source_path=FIXTURES / "mulino_bianco_demo.csv",
        source_type="brandwatch_csv",
        brand_hint="Mulino Bianco",
        mode="full",
    )
    sim, warnings = pipeline.simulate_only(
        result.brand_seed, sim_profiles=3, sim_rounds=1
    )
    # Either OASIS not installed (warning) or stub returned (simulation dict)
    assert sim is not None or any("OASIS" in w for w in warnings)


def test_pipeline_progress_callback() -> None:
    client = _mock_llm()
    steps: list[str] = []
    pipeline = ReportPipeline(llm_client=client, on_progress=lambda step, **kw: steps.append(step))

    pipeline.run(
        source_path=FIXTURES / "mulino_bianco_demo.csv",
        source_type="brandwatch_csv",
        brand_hint="Mulino Bianco",
        mode="quick",
    )
    assert steps == [
        "ingest",
        "ingest_done",
        "baseline_report",
        "kpi",
        "executive_summary",
        "scenario_drivers",
        "action_plan",
        "scenarios",
        "forecast",
    ]


def test_pipeline_to_dict_is_json_serializable() -> None:
    import json

    pipeline = ReportPipeline(llm_client=_mock_llm())
    result = pipeline.run(
        source_path=FIXTURES / "mulino_bianco_demo.csv",
        source_type="brandwatch_csv",
        brand_hint="Mulino Bianco",
        mode="quick",
    )
    # Must round-trip via json.dumps without raising
    json.dumps(result.to_dict())
