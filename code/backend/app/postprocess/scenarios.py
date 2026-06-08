"""Scenario generator (Fase C — LLM via Mistral).

Produce 3 narrative scenarios (best / base / worst) based on the brand seed
and the optional business scenario brief provided by the user at upload time.
"""

from __future__ import annotations

import json
from typing import Optional

from app.llm.mistral import LLMError, MistralClient
from app.schemas import BrandSeed, Scenario, ScenarioSet

_SYSTEM_PROMPT = (
    "Sei un analista di scenario planning per brand italiani. "
    "Dato un seed quantitativo (mention, sentiment, topic, segmenti) e un "
    "eventuale scenario di business dell'utente, produci 3 scenari prospettici "
    "(best/base/worst) qualitativi ma ancorati ai dati. "
    "Rispondi ESCLUSIVAMENTE in JSON valido, niente preamboli."
)

_USER_TEMPLATE = """Brand: {brand}
Mercato: {market}
Orizzonte: {horizon_weeks} settimane
Finestra storica: {window_days} giorni
Mention totali: {total_mentions}
Sentiment medio: {sentiment:+.2f}

TOPIC TOP (mentions, sentiment):
{topics_block}

SEGMENTI:
{segments_block}

{scenario_block}

Genera JSON con questa struttura ESATTA:
{{
  "scenarios": [
    {{
      "label": "best",
      "title": "<≤80 char>",
      "narrative": "<80-200 parole in italiano, business tone>",
      "probability": <float 0.0-1.0>,
      "drivers": ["<driver 1>", "<driver 2>", "<driver 3>"],
      "early_signals": ["<segnale misurabile 1>", "<segnale 2>"]
    }},
    {{ "label": "base", ... }},
    {{ "label": "worst", ... }}
  ],
  "confidence": <float 0.0-1.0>
}}

Regole:
- ESATTAMENTE 3 scenari nell'ordine best, base, worst
- probability deve sommare a ~1.0 fra i 3
- drivers: 3-5 ciascuno, fattori concreti (non generici)
- early_signals: 2-4 ciascuno, metriche o eventi osservabili nelle prossime 2-4 settimane
- narrative deve citare evidenze dai dati (topic / segmenti / sentiment), no invenzioni
- italiano corretto, no anglismi inutili, no JSON fence"""


def generate_scenarios(
    seed: BrandSeed,
    *,
    horizon_weeks: int = 4,
    scenario_brief: Optional[str] = None,
    client: Optional[MistralClient] = None,
) -> ScenarioSet:
    """Produce 3 narrative scenarios. Returns fallback on LLM error."""
    try:
        llm = client or MistralClient()
        data = llm.chat_json(
            system=_SYSTEM_PROMPT,
            user=_USER_TEMPLATE.format(
                brand=seed.brand,
                market=seed.market,
                horizon_weeks=horizon_weeks,
                window_days=seed.monitoring_window_days,
                total_mentions=seed.total_mentions,
                sentiment=seed.overall_sentiment,
                topics_block=_format_topics(seed),
                segments_block=_format_segments(seed),
                scenario_block=_format_scenario_block(scenario_brief),
            ),
            temperature=0.4,
        )
        scenarios = _parse_scenarios(data.get("scenarios", []))
        if len(scenarios) != 3:
            return _fallback(seed, horizon_weeks, reason="LLM did not return 3 scenarios")
        return ScenarioSet(
            horizon_weeks=horizon_weeks,
            scenarios=scenarios,
            model=llm.config.model,
            confidence=float(data.get("confidence", 0.5)),
        )
    except (LLMError, ValueError, KeyError, TypeError) as exc:
        return _fallback(seed, horizon_weeks, reason=str(exc))


def _parse_scenarios(raw: list) -> list[Scenario]:
    out: list[Scenario] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).lower().strip()
        if label not in ("best", "base", "worst"):
            continue
        try:
            out.append(
                Scenario(
                    label=label,  # type: ignore[arg-type]
                    title=str(item.get("title", ""))[:80],
                    narrative=str(item.get("narrative", "")),
                    probability=float(item.get("probability", 0.33)),
                    drivers=[str(d) for d in item.get("drivers", [])][:5],
                    early_signals=[str(s) for s in item.get("early_signals", [])][:4],
                )
            )
        except Exception:
            continue
    return out


def _format_topics(seed: BrandSeed) -> str:
    rows = []
    for t in seed.topics[:8]:
        rows.append(f"- {t.name}: {t.mentions} mention, sent {t.sentiment_score:+.2f}")
    return "\n".join(rows) if rows else "(nessuno)"


def _format_segments(seed: BrandSeed) -> str:
    rows = []
    for s in seed.segments[:6]:
        rows.append(
            f"- {s.name} ({int(s.weight * 100)}%, baseline {s.sentiment_baseline})"
        )
    return "\n".join(rows) if rows else "(nessuno)"


def _format_scenario_block(brief: Optional[str]) -> str:
    if not brief or not brief.strip():
        return ""
    return (
        "SCENARIO BUSINESS (richiesta utente):\n---\n"
        f"{brief.strip()[:4000]}\n---\n"
    )


def _fallback(seed: BrandSeed, horizon_weeks: int, *, reason: str) -> ScenarioSet:
    sent = seed.overall_sentiment
    base_prob = 0.55
    return ScenarioSet(
        horizon_weeks=horizon_weeks,
        confidence=0.2,
        model="fallback",
        scenarios=[
            Scenario(
                label="best",
                title="Recupero sentiment trainato dai topic positivi",
                narrative=(
                    f"Scenario fallback (LLM non disponibile: {reason}). "
                    f"Ipotizza che i topic con sentiment > 0 amplifichino il volume "
                    f"positivo nelle prossime {horizon_weeks} settimane, riportando "
                    f"il sentiment medio sopra zero."
                ),
                probability=0.25,
                drivers=["Topic positivi crescono", "Nessuna crisi reputazionale"],
                early_signals=["sentiment medio settimanale > 0", "calo mention negative"],
            ),
            Scenario(
                label="base",
                title="Continuità dei pattern attuali",
                narrative=(
                    f"Scenario fallback. Il volume mention rimane sui livelli medi "
                    f"({seed.total_mentions} totali nella finestra) con sentiment "
                    f"intorno a {sent:+.2f}. Nessun evento esogeno significativo."
                ),
                probability=base_prob,
                drivers=["Trend storico stabile", "Mix topic invariato"],
                early_signals=["volume settimanale entro ±15% mediana", "sentiment invariato"],
            ),
            Scenario(
                label="worst",
                title="Amplificazione dei topic negativi",
                narrative=(
                    f"Scenario fallback. I topic con sentiment < -0.1 attirano "
                    f"attenzione mediatica e trascinano la conversazione verso "
                    f"sentiment più negativo."
                ),
                probability=0.20,
                drivers=["Topic negativi virali", "Mancanza di risposta tempestiva"],
                early_signals=["picco mention negative settimanale", "share-of-voice negativo > 40%"],
            ),
        ],
    )


__all__ = ["generate_scenarios"]
