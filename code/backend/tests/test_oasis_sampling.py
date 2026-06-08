"""Unit tests for the LLM-reactions sampling helper (M7)."""

from __future__ import annotations

import random

import pytest

from app.engine.simulation.oasis_runner import plan_llm_reactions


def test_plan_zero_agents_returns_empty():
    plan = plan_llm_reactions(
        n_agents=0, sample_rate=0.5, budget_left=10, rng=random.Random(0)
    )
    assert plan == {"sample_size": 0, "capped": False, "picked_indices": []}


def test_plan_zero_budget_marks_capped():
    plan = plan_llm_reactions(
        n_agents=10, sample_rate=0.5, budget_left=0, rng=random.Random(0)
    )
    assert plan["sample_size"] == 0
    assert plan["capped"] is True
    assert plan["picked_indices"] == []


def test_plan_zero_sample_rate_yields_no_calls():
    plan = plan_llm_reactions(
        n_agents=10, sample_rate=0.0, budget_left=100, rng=random.Random(0)
    )
    assert plan["sample_size"] == 0
    assert plan["picked_indices"] == []
    assert plan["capped"] is False


def test_plan_default_sample_rate():
    # 10 agents × 30% = 3 picks, well within budget
    rng = random.Random(42)
    plan = plan_llm_reactions(
        n_agents=10, sample_rate=0.3, budget_left=100, rng=rng
    )
    assert plan["sample_size"] == 3
    assert plan["capped"] is False
    assert len(set(plan["picked_indices"])) == 3
    assert all(0 <= i < 10 for i in plan["picked_indices"])


def test_plan_budget_caps_sample():
    # 10 agents × 50% = 5 desired, but only 2 left in budget → capped
    rng = random.Random(0)
    plan = plan_llm_reactions(
        n_agents=10, sample_rate=0.5, budget_left=2, rng=rng
    )
    assert plan["sample_size"] == 2
    assert plan["capped"] is True
    assert len(plan["picked_indices"]) == 2


def test_plan_minimum_one_when_rate_rounds_down():
    # 3 agents × 0.1 = 0.3 → rounds to 0 but min 1 enforced
    rng = random.Random(0)
    plan = plan_llm_reactions(
        n_agents=3, sample_rate=0.1, budget_left=100, rng=rng
    )
    assert plan["sample_size"] == 1


def test_plan_is_deterministic_with_seed():
    a = plan_llm_reactions(
        n_agents=20, sample_rate=0.5, budget_left=50, rng=random.Random(7)
    )
    b = plan_llm_reactions(
        n_agents=20, sample_rate=0.5, budget_left=50, rng=random.Random(7)
    )
    assert a["picked_indices"] == b["picked_indices"]


def test_plan_clamps_sample_rate_to_one():
    rng = random.Random(0)
    plan = plan_llm_reactions(
        n_agents=5, sample_rate=2.5, budget_left=100, rng=rng
    )
    assert plan["sample_size"] == 5
