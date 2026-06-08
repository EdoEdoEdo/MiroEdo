"""Tests for simulation chapter renderer."""

from __future__ import annotations

from app.postprocess.simulation_chapter import render_simulation_chapter


def _summary(**overrides):
    base = {
        "profiles_count": 5,
        "initial_posts_count": 3,
        "rounds_executed": 2,
        "total_actions": 10,
        "actions_by_type": {"CREATE_POST": 3, "DO_NOTHING": 5, "LIKE_POST": 2},
        "sample_posts": [
            {"post_id": 1, "user_id": 0, "content": "Mulino Bianco è ottimo", "created_at": "2026-05-21"},
            {"post_id": 2, "user_id": 1, "content": "Prezzi alti ultimamente", "created_at": "2026-05-21"},
        ],
        "sample_comments": [
            {"comment_id": 10, "post_id": 1, "user_id": 2, "content": "Concordo", "created_at": "2026-05-21"},
        ],
        "sqlite_path": "/tmp/x.db",
        "used_llm_reactions": False,
        "notes": [],
    }
    base.update(overrides)
    return base


def test_chapter_has_header_and_metrics():
    md = render_simulation_chapter(_summary())
    assert "## 05 Simulazione OASIS" in md
    assert "5 agenti su 2 round" in md
    assert "Totale azioni registrate: 10" in md


def test_chapter_lists_actions_sorted_by_frequency():
    md = render_simulation_chapter(_summary())
    lines = [l for l in md.splitlines() if l.startswith("- **")]
    assert lines[0].startswith("- **DO_NOTHING**: 5")
    assert lines[1].startswith("- **CREATE_POST**: 3")
    assert lines[2].startswith("- **LIKE_POST**: 2")


def test_chapter_includes_posts_and_comments_quotes():
    md = render_simulation_chapter(_summary())
    assert "> [user #0] Mulino Bianco è ottimo" in md
    assert "> [user #2 → post #1] Concordo" in md


def test_chapter_includes_numeric_prediction_for_kpi():
    md = render_simulation_chapter(_summary())
    assert "Nelle prossime 72 ore" in md
    assert "%" in md


def test_chapter_handles_empty_summary():
    md = render_simulation_chapter({})
    assert "## 05 Simulazione OASIS" in md
    assert "Nessuna simulazione" in md


def test_chapter_handles_llm_reactions_flag():
    md = render_simulation_chapter(_summary(used_llm_reactions=True))
    assert "reazioni LLM attive" in md


def test_chapter_includes_notes():
    md = render_simulation_chapter(_summary(notes=["foo bar", "baz"]))
    assert "Note di esecuzione" in md
    assert "- foo bar" in md
    assert "- baz" in md
