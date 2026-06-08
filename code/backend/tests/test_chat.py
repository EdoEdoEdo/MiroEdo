"""Tests for /reports/{id}/chat endpoint and indexing/parsing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.postprocess.chat import ChatAnswer, _parse_answer, index_report
from app.runs import RunStore

FIXTURES = Path(__file__).parent / "fixtures"

REPORT_MD = (
    "# Report Mulino Bianco\n\n"
    "## 01 KPI\n"
    "Il sentiment medio è +0.10.\n\n"
    "### Trend\n"
    "Stabile nelle ultime 2 settimane.\n\n"
    "## 02 Topic critici\n"
    "Il packaging ha sentiment -1.00.\n"
)


def _make_fake_chat(response_payload: dict | str):
    """Build a chat_messages stub that returns `response_payload` (dict→JSON)."""
    captured: dict = {}

    def fake_chat_messages(self, messages, **kw):
        captured["messages"] = messages
        captured["kwargs"] = kw
        if isinstance(response_payload, dict):
            return json.dumps(response_payload)
        return response_payload

    return fake_chat_messages, captured


@pytest.fixture
def client_with_run(tmp_path, monkeypatch):
    """Seed a RunStore with one succeeded run + a stubbed LLM chat."""
    monkeypatch.setenv("MIROEDO_RUNS_DIR", str(tmp_path))
    from app.api import reports as reports_mod

    store = RunStore(base_dir=tmp_path)
    reports_mod._store = store

    rec = store.create(
        mode="quick",
        brand="Mulino Bianco",
        source_type="brandwatch_csv",
        source_filename="demo.csv",
        enable_simulation=False,
    )
    store.mark_succeeded(
        rec.run_id,
        result={
            "mode": "quick",
            "brand_seed": {"brand": "Mulino Bianco"},
            "report_markdown": REPORT_MD,
            "kpi": {},
            "executive_summary": {"summary_it": "ok"},
            "action_plan": {"actions": []},
            "simulation": None,
            "warnings": [],
        },
    )

    fake, captured = _make_fake_chat(
        {
            "answer": "Il sentiment medio è +0.10.",
            "citations": ["S1"],
            "confidence": "high",
            "out_of_scope": False,
        }
    )

    with patch("app.llm.mistral.MistralClient.__init__", return_value=None), patch(
        "app.llm.mistral.MistralClient.chat_messages", new=fake
    ):
        from app.llm.mistral import MistralClient

        MistralClient.config = type("C", (), {"model": "mock"})()
        with TestClient(app) as c:
            yield c, rec.run_id, captured


def test_chat_returns_structured_answer(client_with_run) -> None:
    client, run_id, captured = client_with_run
    r = client.post(
        f"/reports/{run_id}/chat",
        json={"question": "Qual è il sentiment medio?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == run_id
    assert body["answer"] == "Il sentiment medio è +0.10."
    assert body["citations"] == ["S1"]
    assert body["confidence"] == "high"
    assert body["out_of_scope"] is False
    # sections include indexed headings
    sids = [s["sid"] for s in body["sections"]]
    assert "S1" in sids and "S1.1" in sids and "S2" in sids
    # JSON mode requested
    assert captured["kwargs"].get("response_format_json") is True
    # System prompt embeds indexed report
    sys_msg = captured["messages"][0]
    assert "[S1] 01 KPI" in sys_msg["content"]
    assert "[S2] 02 Topic critici" in sys_msg["content"]
    assert "SEZIONI DISPONIBILI" in sys_msg["content"]


def test_chat_history_is_forwarded(client_with_run) -> None:
    client, run_id, captured = client_with_run
    r = client.post(
        f"/reports/{run_id}/chat",
        json={
            "question": "E nei prossimi giorni?",
            "history": [
                {"role": "user", "content": "Qual è il sentiment?"},
                {"role": "assistant", "content": "È +0.10"},
            ],
        },
    )
    assert r.status_code == 200
    msgs = captured["messages"]
    assert len(msgs) == 4
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "Qual è il sentiment?"
    assert msgs[2]["role"] == "assistant"
    assert msgs[3]["content"] == "E nei prossimi giorni?"


def test_chat_rejects_empty_question(client_with_run) -> None:
    client, run_id, _ = client_with_run
    r = client.post(f"/reports/{run_id}/chat", json={"question": "   "})
    assert r.status_code == 503
    assert "empty" in r.json()["detail"].lower()


def test_chat_404_for_unknown_run(client_with_run) -> None:
    client, _, _ = client_with_run
    r = client.post("/reports/does-not-exist/chat", json={"question": "ciao"})
    assert r.status_code in (400, 404)


def test_chat_409_when_run_not_succeeded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MIROEDO_RUNS_DIR", str(tmp_path))
    from app.api import reports as reports_mod

    store = RunStore(base_dir=tmp_path)
    reports_mod._store = store
    rec = store.create(
        mode="quick",
        brand="X",
        source_type="brandwatch_csv",
        source_filename="x.csv",
        enable_simulation=False,
    )
    with TestClient(app) as c:
        r = c.post(f"/reports/{rec.run_id}/chat", json={"question": "ciao"})
        assert r.status_code == 409


# === Indexer / parser unit tests ================================


def test_index_report_assigns_stable_ids() -> None:
    indexed, sections = index_report(REPORT_MD)
    sids = [(s.sid, s.level) for s in sections]
    assert sids == [("S1", 2), ("S1.1", 3), ("S2", 2)]
    assert "## [S1] 01 KPI" in indexed
    assert "### [S1.1] Trend" in indexed
    assert "## [S2] 02 Topic critici" in indexed


def test_parse_answer_drops_unknown_citation_ids() -> None:
    raw = json.dumps(
        {
            "answer": "ok",
            "citations": ["S1", "S99", "garbage"],
            "confidence": "medium",
            "out_of_scope": False,
        }
    )
    out = _parse_answer(raw, valid_ids={"S1", "S2"})
    assert out.citations == ["S1"]


def test_parse_answer_out_of_scope_forces_empty_citations() -> None:
    raw = json.dumps(
        {
            "answer": "Il dato non è nel report.",
            "citations": ["S1"],
            "confidence": "low",
            "out_of_scope": True,
        }
    )
    out = _parse_answer(raw, valid_ids={"S1"})
    assert out.out_of_scope is True
    assert out.citations == []


def test_parse_answer_plain_text_fallback() -> None:
    out = _parse_answer("Risposta non JSON", valid_ids={"S1"})
    assert isinstance(out, ChatAnswer)
    assert out.answer == "Risposta non JSON"
    assert out.confidence == "low"
    assert out.citations == []
    assert out.out_of_scope is False


def test_parse_answer_strips_json_code_fence() -> None:
    raw = '```json\n{"answer":"x","citations":["S1"],"confidence":"high","out_of_scope":false}\n```'
    out = _parse_answer(raw, valid_ids={"S1"})
    assert out.answer == "x"
    assert out.citations == ["S1"]
    assert out.confidence == "high"
