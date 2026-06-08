"""Tests for the optional Zep enrichment helper."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from app.engine.zep import enrichment
from app.schemas import BrandSeed, Segment, Topic


def _seed() -> BrandSeed:
    return BrandSeed(
        brand="Mulino Bianco",
        market="IT",
        language="it",
        monitoring_window_days=30,
        total_mentions=500,
        overall_sentiment=0.4,
        segments=[
            Segment(
                name="Famiglie",
                weight=1.0,
                description="Famiglie italiane",
                sentiment_baseline="positive",
                sample_quotes=[],
            )
        ],
        topics=[
            Topic(name="Colazione", mentions=300, sentiment_score=0.5, sample_quotes=[]),
            Topic(name="Prezzo", mentions=100, sentiment_score=-0.2, sample_quotes=[]),
        ],
        timeline=[],
        source="brandwatch_csv",
    )


def test_skipped_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ZEP_API_KEY", raising=False)
    result = enrichment.maybe_enrich_with_zep(_seed())
    assert result["status"] == "skipped"
    assert "ZEP_API_KEY" in result["reason"]
    assert result["facts_registered"] == 0


def test_unavailable_when_package_missing(monkeypatch):
    monkeypatch.setenv("ZEP_API_KEY", "fake-key")
    monkeypatch.setattr(enrichment, "maybe_enrich_with_zep", enrichment.maybe_enrich_with_zep)

    # Force is_zep_available() → False
    import app.engine.zep as zep_pkg

    monkeypatch.setattr(zep_pkg, "is_zep_available", lambda: False)
    result = enrichment.maybe_enrich_with_zep(_seed(), api_key="fake-key")
    assert result["status"] == "unavailable"
    assert "zep_cloud" in result["reason"]


def test_happy_path_registers_facts(monkeypatch):
    """When zep_cloud is available and the client works, all facts are pushed."""
    monkeypatch.setenv("ZEP_API_KEY", "fake-key")

    fake_client = MagicMock()
    fake_client.graph.create.side_effect = lambda **_: None
    fake_client.graph.add.return_value = None

    import app.engine.zep as zep_pkg

    monkeypatch.setattr(zep_pkg, "is_zep_available", lambda: True)
    monkeypatch.setattr(zep_pkg, "create_zep_client", lambda _k: fake_client)
    # Also patch on the enrichment module since it imports via the package
    monkeypatch.setattr(
        "app.engine.zep.enrichment.create_zep_client", lambda _k: fake_client, raising=False
    )

    result = enrichment.maybe_enrich_with_zep(_seed(), api_key="fake-key")

    assert result["status"] == "ok"
    assert result["graph_id"] == "miroedo_mulino_bianco"
    # 1 brand fact + 1 segment + 2 topics
    assert result["facts_registered"] == 4
    fake_client.graph.add.assert_called()


def test_error_when_client_raises(monkeypatch):
    monkeypatch.setenv("ZEP_API_KEY", "fake-key")

    import app.engine.zep as zep_pkg

    monkeypatch.setattr(zep_pkg, "is_zep_available", lambda: True)

    def boom(_key):
        raise RuntimeError("auth failed")

    monkeypatch.setattr(zep_pkg, "create_zep_client", boom)
    monkeypatch.setattr(
        "app.engine.zep.enrichment.create_zep_client", boom, raising=False
    )

    result = enrichment.maybe_enrich_with_zep(_seed(), api_key="fake-key")
    assert result["status"] == "error"
    assert "RuntimeError" in result["reason"]
    assert "auth failed" in result["reason"]


def test_partial_failure_counts_only_successes(monkeypatch):
    """If graph.add raises for some facts, count only the successful ones."""
    monkeypatch.setenv("ZEP_API_KEY", "fake-key")

    fake_client = MagicMock()
    fake_client.graph.create.return_value = None
    calls = {"n": 0}

    def add_side_effect(**_kw):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            raise RuntimeError("rate limited")

    fake_client.graph.add.side_effect = add_side_effect

    import app.engine.zep as zep_pkg

    monkeypatch.setattr(zep_pkg, "is_zep_available", lambda: True)
    monkeypatch.setattr(zep_pkg, "create_zep_client", lambda _k: fake_client)
    monkeypatch.setattr(
        "app.engine.zep.enrichment.create_zep_client", lambda _k: fake_client, raising=False
    )

    result = enrichment.maybe_enrich_with_zep(_seed(), api_key="fake-key")
    # 4 attempts total, every other fails → 2 successes
    assert result["status"] == "ok"
    assert result["facts_registered"] == 2


def test_default_graph_id_is_safe():
    assert enrichment._default_graph_id("Mulino Bianco") == "miroedo_mulino_bianco"
    assert enrichment._default_graph_id("D&G/100%") == "miroedo_d_g_100"
    assert enrichment._default_graph_id("") == "miroedo_brand"
