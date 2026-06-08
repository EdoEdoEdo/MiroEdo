"""Action Plan generator (Fase B — LLM via Mistral)."""

from __future__ import annotations

from typing import Optional

from app.llm.mistral import LLMError, MistralClient
from app.schemas import Action, ActionPlan, ScenarioDriversSet

_VALID_OWNERS = {
    "Brand Manager",
    "Marketing",
    "PR",
    "Customer Care",
    "Insight",
    "Legal",
}

_SYSTEM_PROMPT = (
    "Sei un consulente strategico per Brand Manager italiani. "
    "Dato un report di simulazione, generi un piano d'azione operativo a 72 ore. "
    "Le azioni devono essere concrete, eseguibili, e collegate a evidenze nel report. "
    "Rispondi ESCLUSIVAMENTE in JSON valido senza testo extra."
)

_USER_TEMPLATE = """Brand: {brand}
Mercato: {market}
Orizzonte: {horizon_hours} ore
{scenario_block}{drivers_block}
REPORT MIROFISH (markdown):
---
{report}
---

Genera un JSON con questa struttura ESATTA:
{{
  "actions": [
    {{
      "priority": <int 1-5, 1=critica>,
      "action": "<azione concreta in italiano, ≤30 parole, verbi all'imperativo>",
      "owner": "<uno tra: Brand Manager, Marketing, PR, Customer Care, Insight, Legal>",
      "timeframe_h": <int ore entro cui eseguire, 1-{horizon_hours}>,
      "rationale": "<perché in 1 frase, citando l'evidenza dal report>",
      "kpi_target": "<metrica misurabile, es. 'sentiment +5pp su segmento X entro 7gg'>",
      "targets_drivers": ["<etichetta esatta del driver indirizzato>", ...],
      "expected_impact": "<impatto atteso sui driver indirizzati, 1 frase>"
    }}
  ]
}}

Regole:
- Genera 3-5 azioni totali
- Ordina per priority crescente (1 prima)
- owner DEVE essere uno dei valori elencati
- Non duplicare azioni
- Se sono stati forniti DRIVER OSSERVATI sopra, ogni azione DEVE citare almeno
  1 driver in `targets_drivers` (etichetta esatta). Almeno il 60% delle azioni
  deve indirizzare driver con strength='high'.
- Se non sono stati forniti driver, lascia `targets_drivers: []` e `expected_impact: ""`.
- Niente preamboli, niente code fence: solo JSON puro"""


def generate_action_plan(
    report_markdown: str,
    *,
    brand: str = "Brand",
    market: str = "IT",
    horizon_hours: int = 72,
    client: Optional[MistralClient] = None,
    scenario_brief: Optional[str] = None,
    drivers: Optional[ScenarioDriversSet] = None,
) -> ActionPlan:
    """Genera ActionPlan strutturato dal report MiroFish.

    Quando ``drivers`` è fornito, il prompt vincola ogni azione a citare
    almeno un driver per nome via ``targets_drivers``, costruendo il bridge
    esplicito tra evidenze del corpus e raccomandazioni operative.
    """
    if not report_markdown.strip():
        return ActionPlan(actions=[], horizon_hours=horizon_hours, model="fallback")

    trimmed = report_markdown[:20000]
    scenario_block = _format_scenario_block(scenario_brief)
    drivers_block = _format_drivers_block(drivers)
    valid_driver_labels = {d.label for d in (drivers.drivers if drivers else [])}

    try:
        llm = client or MistralClient()
        data = llm.chat_json(
            system=_SYSTEM_PROMPT,
            user=_USER_TEMPLATE.format(
                brand=brand,
                market=market,
                report=trimmed,
                horizon_hours=horizon_hours,
                scenario_block=scenario_block,
                drivers_block=drivers_block,
            ),
            temperature=0.4,
        )
        raw_actions = data.get("actions", []) if isinstance(data, dict) else []
        actions: list[Action] = []
        for item in raw_actions[:5]:
            if not isinstance(item, dict):
                continue
            owner = str(item.get("owner", "Brand Manager"))
            if owner not in _VALID_OWNERS:
                owner = "Brand Manager"
            try:
                raw_targets = item.get("targets_drivers") or []
                if not isinstance(raw_targets, list):
                    raw_targets = []
                # Keep only drivers actually present in the input set so the
                # frontend can render badges without orphaned labels.
                targets = [
                    str(t).strip()[:80]
                    for t in raw_targets
                    if str(t).strip()
                    and (not valid_driver_labels or str(t).strip() in valid_driver_labels)
                ][:3]
                actions.append(
                    Action(
                        priority=int(item.get("priority", 3)),
                        action=str(item.get("action", "")).strip()[:300],
                        owner=owner,  # type: ignore[arg-type]
                        timeframe_h=min(
                            int(item.get("timeframe_h", horizon_hours)), horizon_hours
                        ),
                        rationale=str(item.get("rationale", "")).strip()[:400],
                        kpi_target=str(item.get("kpi_target", "")).strip()[:200],
                        targets_drivers=targets,
                        expected_impact=str(item.get("expected_impact", "")).strip()[:240],
                    )
                )
            except (ValueError, TypeError):
                continue

        actions.sort(key=lambda a: a.priority)
        return ActionPlan(
            actions=actions, horizon_hours=horizon_hours, model=llm.config.model
        )
    except LLMError as exc:
        return _fallback_plan(horizon_hours, error=str(exc))


def _format_drivers_block(drivers: Optional[ScenarioDriversSet]) -> str:
    """Render dei driver come blocco contestuale per il prompt LLM."""
    if not drivers or not drivers.drivers:
        return ""
    lines = [
        "",
        "DRIVER OSSERVATI dal corpus (ogni azione DEVE citare almeno 1 driver in `targets_drivers`):",
        "---",
    ]
    for d in drivers.drivers:
        evidence = (
            f" [topic: {d.evidence_topic} · {d.mentions} mention · sentiment {d.sentiment:+.2f}]"
            if d.evidence_topic
            else ""
        )
        lines.append(f"- [{d.strength}] \"{d.label}\"{evidence}: {d.rationale}")
    lines.append("---")
    if drivers.scenario_focus:
        lines.append(f"Focus: {drivers.scenario_focus}")
    return "\n".join(lines) + "\n"


def _format_scenario_block(scenario_brief: Optional[str]) -> str:
    """Render lo scenario utente come blocco contestuale per il prompt LLM."""
    if not scenario_brief or not scenario_brief.strip():
        return ""
    cleaned = scenario_brief.strip()[:4000]
    return (
        "\nSCENARIO BUSINESS (richiesta dell'utente che inquadra le azioni richieste):\n"
        "---\n"
        f"{cleaned}\n"
        "---\n"
        "Le azioni devono essere coerenti con questo scenario e con le evidenze del report.\n"
    )


def _fallback_plan(horizon_hours: int, *, error: str = "") -> ActionPlan:
    return ActionPlan(
        actions=[
            Action(
                priority=3,
                action=f"[Fallback] LLM non disponibile: {error[:120]}",
                owner="Brand Manager",
                timeframe_h=horizon_hours,
                rationale="Generato in fallback perché la chiamata LLM è fallita.",
                kpi_target="",
            )
        ],
        horizon_hours=horizon_hours,
        model="fallback",
    )
