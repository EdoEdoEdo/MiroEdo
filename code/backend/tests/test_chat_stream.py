"""Tests for the streaming chat path (M8)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.postprocess.chat import _JsonAnswerExtractor, chat_with_report_stream
from app.runs import RunStore


# === Pure extractor tests ===========================================


def _feed_chunks(text: str, chunk_size: int = 3):
    ex = _JsonAnswerExtractor()
    out: list[str] = []
    for i in range(0, len(text), chunk_size):
        decoded = ex.feed(text[i : i + chunk_size])
        if decoded:
            out.append(decoded)
    return "".join(out), ex


def test_extractor_accumulates_simple_answer():
    raw = '{"answer":"Hello world","citations":["S1"],"confidence":"high","out_of_scope":false}'
    answer, ex = _feed_chunks(raw, chunk_size=4)
    assert answer == "Hello world"
    assert ex.closed is True


def test_extractor_decodes_escapes():
    raw = '{"answer":"Riga 1\\nRiga 2 \\"quoted\\""}'
    answer, _ex = _feed_chunks(raw, chunk_size=5)
    assert answer == 'Riga 1\nRiga 2 "quoted"'


def test_extractor_handles_unicode_escape():
    # \u00e8 = è
    raw = '{"answer":"caff\\u00e8 \\u00e8 ok"}'
    answer, _ex = _feed_chunks(raw, chunk_size=3)
    assert answer == "caffè è ok"


def test_extractor_returns_empty_for_non_json_stream():
    raw = "Risposta in chiaro senza JSON"
    answer, ex = _feed_chunks(raw, chunk_size=4)
    assert answer == ""
    assert ex.closed is False
    assert ex.buf == raw


def test_extractor_waits_for_complete_escape_sequence():
    # Split right inside an escape '\\u00e8'
    ex = _JsonAnswerExtractor()
    parts = ['{"answer":"caff\\u', "00e8 ok\"}"]
    out = "".join(ex.feed(p) for p in parts)
    assert out == "caffè ok"


# === Streaming endpoint test ========================================


REPORT_MD = (
    "# Report\n\n## 01 KPI\nIl sentiment medio è +0.10.\n\n"
    "## 02 Topic\nIl packaging ha sentiment -1.00.\n"
)


@pytest.fixture
def stream_client(tmp_path, monkeypatch):
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

    payload = (
        '{"answer":"Il sentiment medio è +0.10.",'
        '"citations":["S1"],"confidence":"high","out_of_scope":false}'
    )
    # Emit 6-character chunks to exercise incremental parsing.
    chunks = [payload[i : i + 6] for i in range(0, len(payload), 6)]

    def fake_stream(self, messages, **_kw):
        yield from chunks

    with patch("app.llm.mistral.MistralClient.__init__", return_value=None), patch(
        "app.llm.mistral.MistralClient.chat_messages_stream", new=fake_stream
    ):
        from app.llm.mistral import MistralClient

        MistralClient.config = type("C", (), {"model": "mock"})()
        with TestClient(app) as c:
            yield c, rec.run_id


def test_stream_endpoint_emits_token_then_meta(stream_client) -> None:
    client, run_id = stream_client
    with client.stream(
        "POST",
        f"/reports/{run_id}/chat/stream",
        json={"question": "Qual è il sentiment medio?"},
    ) as resp:
        assert resp.status_code == 200
        events: list[tuple[str, dict | str]] = []
        current_event: str | None = None
        for line in resp.iter_lines():
            if not line:
                current_event = None
                continue
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: ") and current_event:
                data = line[6:]
                if current_event == "token":
                    events.append(("token", json.loads(data)))
                elif current_event == "meta":
                    events.append(("meta", json.loads(data)))
                elif current_event == "done":
                    events.append(("done", {}))
                elif current_event == "error":
                    events.append(("error", json.loads(data)))

    kinds = [k for k, _ in events]
    assert "token" in kinds
    assert "meta" in kinds
    assert kinds[-1] == "done"

    # Reassembling token payloads must reproduce the answer
    answer_text = "".join(v for k, v in events if k == "token")
    assert answer_text == "Il sentiment medio è +0.10."

    meta = next(v for k, v in events if k == "meta")
    assert meta["citations"] == ["S1"]
    assert meta["confidence"] == "high"
    assert meta["out_of_scope"] is False
    assert any(s["sid"] == "S1" for s in meta["sections"])
