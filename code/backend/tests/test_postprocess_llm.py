"""Test per Executive Summary e Action Plan con MistralClient mockato.

Nessuna chiamata di rete: usiamo un fake client che ritorna JSON predefinito.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import LLMConfig
from app.llm.mistral import LLMError, MistralClient
from app.postprocess.action_plan import generate_action_plan
from app.postprocess.executive_summary import generate_executive_summary
from app.schemas import ActionPlan, ExecutiveSummary


def _locate_fixture() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "fixtures" / "wuhan_report_reference.md"
        if candidate.exists():
            return candidate
    return None


FIXTURE = _locate_fixture()


class FakeClient(MistralClient):
    """Bypassa __init__ del parent: niente check API key, niente rete."""

    def __init__(self, response_json: dict, *, model: str = "fake-mistral") -> None:
        self.config = LLMConfig(
            api_key="fake",
            base_url="https://fake",
            model=model,
            timeout_s=10.0,
            max_retries=0,
        )
        self._response = response_json

    def chat_json(self, system: str, user: str, *, temperature: float = 0.2) -> dict:  # noqa: ARG002
        return self._response


class FailingClient(FakeClient):
    def chat_json(self, system: str, user: str, *, temperature: float = 0.2) -> dict:  # noqa: ARG002
        raise LLMError("network down (simulato)")


@pytest.fixture
def report_text() -> str:
    if FIXTURE is not None and FIXTURE.exists():
        return FIXTURE.read_text(encoding="utf-8")
    # Fallback: testo sintetico abbastanza lungo
    return (
        "# Report Brand X\n\n"
        "Il brand X presenta sentiment misto con il 45% di menzioni positive "
        "e il 30% negative. Il segmento Gen Z mostra preoccupazione sui prezzi. "
        "Nelle prossime 48 ore si prevede un aumento del 15% delle interazioni.\n\n"
        "## Capitolo 2\n\nUlteriori dettagli quantitativi."
    )


# ============ Executive Summary ============


def test_executive_summary_happy_path(report_text: str) -> None:
    fake = FakeClient(
        {
            "summary_it": "Il brand mostra sentiment misto con segnali di tensione sul prezzo.",
            "key_findings": [
                "Sentiment positivo al 45%",
                "Gen Z preoccupata sul prezzo",
                "Crescita interazioni +15% in 48h",
            ],
            "confidence": 0.78,
        }
    )
    out = generate_executive_summary(
        report_text, brand="TestBrand", market="IT", client=fake
    )
    assert isinstance(out, ExecutiveSummary)
    assert "sentiment" in out.summary_it.lower()
    assert len(out.key_findings) == 3
    assert out.confidence == pytest.approx(0.78)
    assert out.model == "fake-mistral"


def test_executive_summary_truncates_key_findings(report_text: str) -> None:
    fake = FakeClient(
        {
            "summary_it": "ok",
            "key_findings": [f"finding {i}" for i in range(10)],
            "confidence": 0.5,
        }
    )
    out = generate_executive_summary(report_text, client=fake)
    assert len(out.key_findings) == 5


def test_executive_summary_empty_report() -> None:
    fake = FakeClient({"summary_it": "x", "key_findings": [], "confidence": 1.0})
    out = generate_executive_summary("", client=fake)
    assert out.confidence == 0.0
    assert out.model == "fallback"


def test_executive_summary_llm_failure_fallback(report_text: str) -> None:
    failing = FailingClient({})
    out = generate_executive_summary(report_text, client=failing)
    assert out.model == "fallback"
    assert "non disponibile" in out.summary_it.lower() or out.summary_it


# ============ Action Plan ============


def test_action_plan_happy_path(report_text: str) -> None:
    fake = FakeClient(
        {
            "actions": [
                {
                    "priority": 2,
                    "action": "Pubblicare nota stampa su sostenibilità",
                    "owner": "PR",
                    "timeframe_h": 24,
                    "rationale": "Sentiment negativo su impatto ambientale.",
                    "kpi_target": "Sentiment +5pp in 7 giorni",
                },
                {
                    "priority": 1,
                    "action": "Attivare crisis room con Customer Care",
                    "owner": "Customer Care",
                    "timeframe_h": 6,
                    "rationale": "Picco lamentele Gen Z.",
                    "kpi_target": "TTR <2h",
                },
            ]
        }
    )
    plan = generate_action_plan(report_text, brand="TestBrand", client=fake)
    assert isinstance(plan, ActionPlan)
    assert plan.horizon_hours == 72
    assert len(plan.actions) == 2
    # Ordinate per priority crescente
    assert plan.actions[0].priority == 1
    assert plan.actions[0].owner == "Customer Care"
    assert plan.actions[1].owner == "PR"


def test_action_plan_invalid_owner_normalized(report_text: str) -> None:
    fake = FakeClient(
        {
            "actions": [
                {
                    "priority": 1,
                    "action": "Test",
                    "owner": "CEO",  # NON valido
                    "timeframe_h": 12,
                    "rationale": "r",
                    "kpi_target": "k",
                }
            ]
        }
    )
    plan = generate_action_plan(report_text, client=fake)
    assert plan.actions[0].owner == "Brand Manager"


def test_action_plan_max_5_actions(report_text: str) -> None:
    fake = FakeClient(
        {
            "actions": [
                {
                    "priority": 1,
                    "action": f"a{i}",
                    "owner": "Marketing",
                    "timeframe_h": 24,
                    "rationale": "r",
                    "kpi_target": "k",
                }
                for i in range(10)
            ]
        }
    )
    plan = generate_action_plan(report_text, client=fake)
    assert len(plan.actions) == 5


def test_action_plan_caps_timeframe_to_horizon(report_text: str) -> None:
    fake = FakeClient(
        {
            "actions": [
                {
                    "priority": 1,
                    "action": "x",
                    "owner": "PR",
                    "timeframe_h": 999,
                    "rationale": "r",
                    "kpi_target": "k",
                }
            ]
        }
    )
    plan = generate_action_plan(report_text, client=fake, horizon_hours=48)
    assert plan.actions[0].timeframe_h == 48


def test_action_plan_llm_failure_fallback(report_text: str) -> None:
    plan = generate_action_plan(report_text, client=FailingClient({}))
    assert plan.model == "fallback"
    assert len(plan.actions) == 1
    assert "fallback" in plan.actions[0].action.lower()


# ============ MistralClient JSON parsing ============


def test_chat_json_strips_code_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    """chat_json deve tollerare risposte avvolte in ```json ... ```."""

    class Client(MistralClient):
        def __init__(self) -> None:
            self.config = LLMConfig(
                api_key="x", base_url="x", model="x", timeout_s=1.0, max_retries=0
            )

        def chat(self, system, user, *, temperature=0.3, response_format_json=False):  # noqa: ARG002
            return '```json\n{"foo": 1}\n```'

    out = Client().chat_json("s", "u")
    assert out == {"foo": 1}


def test_chat_json_invalid_raises() -> None:
    class Client(MistralClient):
        def __init__(self) -> None:
            self.config = LLMConfig(
                api_key="x", base_url="x", model="x", timeout_s=1.0, max_retries=0
            )

        def chat(self, system, user, *, temperature=0.3, response_format_json=False):  # noqa: ARG002
            return "non è json"

    with pytest.raises(LLMError):
        Client().chat_json("s", "u")
