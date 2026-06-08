"""Integration tests for /reports API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runs import RunStore

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate RunStore to tmp_path per test
    monkeypatch.setenv("MIROEDO_RUNS_DIR", str(tmp_path))
    # Reset module-level singleton
    from app.api import reports as reports_mod

    reports_mod._store = RunStore(base_dir=tmp_path)

    # Mock Mistral so tests don't need a real API key
    fake_payload_summary = {
        "summary_it": "Test summary",
        "key_findings": ["finding 1"],
        "confidence": 0.7,
    }
    fake_payload_action = {
        "actions": [
            {
                "priority": 1,
                "action": "Test action",
                "owner": "Marketing",
                "timeframe_h": 24,
                "rationale": "Test rationale",
                "kpi_target": "+5pp",
            }
        ]
    }

    def fake_chat_json(self, system, user, **_kw):
        if "Executive Summary" in system or "summary_it" in user:
            return fake_payload_summary
        return fake_payload_action

    with patch("app.llm.mistral.MistralClient.__init__", return_value=None), \
         patch("app.llm.mistral.MistralClient.chat_json", new=fake_chat_json), \
         patch.object(reports_mod, "_simulation_default", return_value=False):
        # Ensure config attribute exists for executive_summary's .config.model lookup
        from app.llm.mistral import MistralClient

        MistralClient.config = type("C", (), {"model": "mock"})()
        with TestClient(app) as c:
            yield c


def _post_csv(client: TestClient, brand: str = "Mulino Bianco", mode: str = "quick"):
    with open(FIXTURES / "mulino_bianco_demo.csv", "rb") as fh:
        return client.post(
            "/reports",
            files={"file": ("demo.csv", fh, "text/csv")},
            data={
                "brand": brand,
                "source_type": "brandwatch_csv",
                "mode": mode,
            },
        )


def test_health_still_works(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_post_reports_returns_202_and_run_id(client: TestClient) -> None:
    r = _post_csv(client)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] in {"pending", "succeeded", "running"}
    assert body["brand"] == "Mulino Bianco"
    assert body["mode"] == "quick"
    assert len(body["run_id"]) == 32


def test_get_report_after_completion(client: TestClient) -> None:
    run_id = _post_csv(client).json()["run_id"]
    # BackgroundTasks runs synchronously in TestClient after response → already done
    r = client.get(f"/reports/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded", body
    assert body["result"]["brand_seed"]["brand"] == "Mulino Bianco"
    assert body["result"]["executive_summary"]["summary_it"] == "Test summary"
    assert len(body["result"]["action_plan"]["actions"]) == 1


def test_get_report_not_found(client: TestClient) -> None:
    r = client.get("/reports/" + "0" * 32)
    assert r.status_code == 404


def test_get_report_invalid_id(client: TestClient) -> None:
    r = client.get("/reports/..%2Fetc%2Fpasswd")
    assert r.status_code in {400, 404}


def test_list_reports(client: TestClient) -> None:
    _post_csv(client, brand="A")
    _post_csv(client, brand="B")
    r = client.get("/reports?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    brands = {item["brand"] for item in body}
    assert brands == {"A", "B"}


def test_rejects_empty_file(client: TestClient) -> None:
    r = client.post(
        "/reports",
        files={"file": ("empty.csv", b"", "text/csv")},
        data={"brand": "X", "source_type": "brandwatch_csv", "mode": "quick"},
    )
    assert r.status_code == 400


def test_rejects_wrong_extension_for_csv(client: TestClient) -> None:
    # Universal adapter: legacy source_type=brandwatch_csv is normalized to
    # "tabular"; .pdf becomes "document" automatically. A truly unsupported
    # extension (e.g. .exe) must still be rejected.
    r = client.post(
        "/reports",
        files={"file": ("malware.exe", b"MZ\x90", "application/octet-stream")},
        data={"brand": "X", "mode": "quick"},
    )
    assert r.status_code == 400


def test_failed_pipeline_records_error(client: TestClient, monkeypatch) -> None:
    # Force pipeline to fail by uploading an unparseable CSV
    r = client.post(
        "/reports",
        files={"file": ("bad.csv", b"not,a,real,csv\nxx", "text/csv")},
        data={"brand": "X", "source_type": "brandwatch_csv", "mode": "quick"},
    )
    run_id = r.json()["run_id"]
    body = client.get(f"/reports/{run_id}").json()
    assert body["status"] == "failed"
    assert body["error"]
