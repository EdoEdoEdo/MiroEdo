"""
Mock-driven tests for ReportPipeline 'full' mode.

We don't run the real OASIS subprocess here — that lives in the E2E smoke
script. Instead we patch:
- `oasis` import: ensures the gating in `_run_simulation` passes
- `OasisProfileGenerator.generate_profiles_from_entities` → returns 3 fake
  profiles instantly (no LLM calls)
- `run_minimal_simulation` → returns a fabricated SimulationSummary so the
  test runs in milliseconds and asserts the wiring is correct.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.engine.profile.generator import OasisAgentProfile
from app.pipeline import ReportPipeline


FIXTURES = Path(__file__).parent / "fixtures"


def _mock_llm():
    client = MagicMock()
    client.config = MagicMock(model="mock-model")

    def chat_json(system: str, user: str, **_kw):
        if "Executive Summary" in system or "summary_it" in user:
            return {
                "summary_it": "Sintesi mock.",
                "key_findings": ["finding"],
                "confidence": 0.6,
            }
        return {"actions": []}

    client.chat_json.side_effect = chat_json
    return client


def _fake_profiles(n: int) -> list[OasisAgentProfile]:
    return [
        OasisAgentProfile(
            user_id=i,
            user_name=f"mock_user_{i}",
            name=f"Mock User {i}",
            bio="bio",
            persona="persona",
            source_entity_uuid=f"u-{i}",
            source_entity_type="Consumer",
        )
        for i in range(n)
    ]


def _fake_summary():
    # Mirrors the shape of SimulationSummary.to_dict()
    return {
        "profiles_count": 3,
        "initial_posts_count": 2,
        "rounds_executed": 1,
        "total_actions": 5,
        "actions_by_type": {"CREATE_POST": 2, "DO_NOTHING": 3},
        "sample_posts": [
            {"post_id": 1, "user_id": 0, "content": "Hello", "created_at": "2026-05-21"}
        ],
        "sample_comments": [],
        "sqlite_path": "/tmp/fake.db",
        "used_llm_reactions": False,
        "notes": ["mock summary"],
    }


@pytest.fixture
def fake_oasis(monkeypatch):
    """Inject a fake `oasis` module so the importability gate passes."""
    fake_mod = types.ModuleType("oasis")
    monkeypatch.setitem(sys.modules, "oasis", fake_mod)
    yield fake_mod


def test_full_mode_wires_seed_to_simulation(fake_oasis, monkeypatch):
    """End-to-end pipeline.run(mode='full') with all heavy bits mocked."""
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    captured: dict = {}

    def fake_generate(self, entities, **kwargs):
        captured["entity_count"] = len(entities)
        captured["platform"] = kwargs.get("output_platform")
        return _fake_profiles(min(len(entities), 3))

    def fake_run_sim(*, profiles, seed_posts, workspace_dir, rounds, **kw):
        captured["profiles_count"] = len(profiles)
        captured["seed_posts"] = list(seed_posts)
        captured["rounds"] = rounds
        captured["enable_llm"] = kw.get("enable_llm_reactions")
        from app.engine.simulation.oasis_runner import SimulationSummary

        return SimulationSummary(**_fake_summary())

    with patch.object(
        sys.modules["app.engine.profile.generator"].OasisProfileGenerator,
        "generate_profiles_from_entities",
        new=fake_generate,
    ), patch(
        "app.engine.simulation.oasis_runner.run_minimal_simulation",
        new=fake_run_sim,
    ):
        # Re-import so pipeline picks up the patched function (it imports lazily)
        import importlib

        import app.engine.simulation.oasis_runner as oasis_runner_mod

        importlib.reload(oasis_runner_mod)

        with patch(
            "app.engine.simulation.oasis_runner.run_minimal_simulation",
            new=fake_run_sim,
        ):
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

    assert result.mode == "full"
    assert sim is not None, warnings
    assert sim["total_actions"] == 5
    assert sim["profiles_count"] == 3
    # Wiring checks
    assert captured["platform"] == "reddit"
    assert captured["entity_count"] >= 1
    assert captured["profiles_count"] == 3
    assert captured["rounds"] == 1
    assert captured["enable_llm"] is False  # default safe
    assert all("Mulino Bianco" in p for p in captured["seed_posts"]) or captured["seed_posts"]


def test_full_mode_without_oasis_returns_warning(monkeypatch):
    """If `oasis` is not importable, we get a warning and no simulation."""
    monkeypatch.setitem(sys.modules, "oasis", None)
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
    assert sim is None
    assert any("OASIS simulation unavailable" in w for w in warnings)


def test_full_mode_without_llm_key_returns_warning(fake_oasis, monkeypatch):
    """Without LLM_API_KEY, profile generation can't run → graceful warning."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
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
    assert sim is None
    assert any("LLM_API_KEY" in w for w in warnings)


def test_llm_reactions_env_flag_propagates(fake_oasis, monkeypatch):
    """MIROEDO_OASIS_LLM_REACTIONS=true must reach run_minimal_simulation."""
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setenv("MIROEDO_OASIS_LLM_REACTIONS", "true")

    captured: dict = {}

    def fake_generate(self, entities, **kwargs):
        return _fake_profiles(3)

    def fake_run_sim(*, profiles, seed_posts, workspace_dir, rounds, **kw):
        captured["enable_llm"] = kw.get("enable_llm_reactions")
        from app.engine.simulation.oasis_runner import SimulationSummary

        return SimulationSummary(**_fake_summary())

    with patch.object(
        sys.modules["app.engine.profile.generator"].OasisProfileGenerator,
        "generate_profiles_from_entities",
        new=fake_generate,
    ), patch(
        "app.engine.simulation.oasis_runner.run_minimal_simulation",
        new=fake_run_sim,
    ):
        pipeline = ReportPipeline(llm_client=_mock_llm())
        result = pipeline.run(
            source_path=FIXTURES / "mulino_bianco_demo.csv",
            source_type="brandwatch_csv",
            brand_hint="Mulino Bianco",
            mode="full",
        )
        pipeline.simulate_only(result.brand_seed, sim_profiles=3, sim_rounds=1)

    assert captured["enable_llm"] is True


def test_llm_sampling_env_vars_propagate(fake_oasis, monkeypatch):
    """MIROEDO_OASIS_LLM_SAMPLE and _MAX_CALLS must reach the runner."""
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setenv("MIROEDO_OASIS_LLM_REACTIONS", "true")
    monkeypatch.setenv("MIROEDO_OASIS_LLM_SAMPLE", "0.5")
    monkeypatch.setenv("MIROEDO_OASIS_LLM_MAX_CALLS", "12")

    captured: dict = {}

    def fake_generate(self, entities, **kwargs):
        return _fake_profiles(3)

    def fake_run_sim(*, profiles, seed_posts, workspace_dir, rounds, **kw):
        captured.update(
            enable_llm=kw.get("enable_llm_reactions"),
            sample=kw.get("llm_sample_rate"),
            cap=kw.get("llm_max_calls"),
        )
        from app.engine.simulation.oasis_runner import SimulationSummary

        return SimulationSummary(**_fake_summary())

    with patch.object(
        sys.modules["app.engine.profile.generator"].OasisProfileGenerator,
        "generate_profiles_from_entities",
        new=fake_generate,
    ), patch(
        "app.engine.simulation.oasis_runner.run_minimal_simulation",
        new=fake_run_sim,
    ):
        pipeline = ReportPipeline(llm_client=_mock_llm())
        result = pipeline.run(
            source_path=FIXTURES / "mulino_bianco_demo.csv",
            source_type="brandwatch_csv",
            brand_hint="Mulino Bianco",
            mode="full",
        )
        pipeline.simulate_only(result.brand_seed, sim_profiles=3, sim_rounds=1)

    assert captured == {"enable_llm": True, "sample": 0.5, "cap": 12}
