"""Scenario drivers extractor (Fase D — bridge dati → azione).

Estrae i *driver osservati* nel BrandSeed che potrebbero spiegare lo
``scenario_brief`` formulato dall'utente. È il nodo che rende MiroEdo
"scenario-driven brand intelligence" anziché un report generator generico:
agganciamo le evidenze quantitative (topic + sentiment + quote) alla
domanda di business e creiamo un'ancora esplicita per l'action plan.

Output: ``ScenarioDriversSet`` con N driver, ognuno con label, topic
d'evidenza, mention count, sentiment, strength qualitativa e quote di
supporto. Pensato per essere consumato sia dal nodo ``action_plan`` (che
mapperà le azioni sui driver) sia dal frontend (sezione dedicata sopra il
piano operativo).

Quando lo ``scenario_brief`` è vuoto o l'LLM fallisce, ritorniamo un
fallback deterministico costruito dai top-3 topic del seed, così la
pipeline non si rompe mai e il frontend riceve sempre qualcosa di
visualizzabile.
"""

from __future__ import annotations

from typing import Optional

from app.llm.mistral import LLMError, MistralClient
from app.schemas import BrandSeed, ScenarioDriver, ScenarioDriversSet

_SYSTEM_PROMPT = (
    "Sei un analista senior di brand intelligence. Date evidenze quantitative "
    "estratte da un corpus social-listening (topic + sentiment + quote) e una "
    "domanda di business dell'utente, identifichi i DRIVER OSSERVATI che "
    "potrebbero spiegare lo scenario richiesto. I driver sono ipotesi "
    "interpretative ancorate a numeri o quote del dataset — non invenzioni. "
    "Rispondi ESCLUSIVAMENTE in JSON valido senza testo extra."
)

_USER_TEMPLATE = """Brand: {brand}
Mercato: {market}
Periodo monitorato: {window_days} giorni
Sentiment medio: {overall_sentiment:+.2f}
Menzioni totali: {total_mentions}

DOMANDA DI BUSINESS (scenario utente):
---
{scenario_brief}
---

EVIDENZE DAL CORPUS (top topic ordinati per volume):
{topics_block}

Genera un JSON con questa struttura ESATTA:
{{
  "scenario_focus": "<1 frase che riassume cosa stai indirizzando, in italiano>",
  "drivers": [
    {{
      "label": "<nome breve del driver, max 60 char, in italiano>",
      "evidence_topic": "<nome esatto del topic dal corpus che fa da evidenza primaria, oppure '' se trasversale>",
      "mentions": <int, totale menzioni dell'evidenza (0 se non applicabile)>,
      "sentiment": <float -1..+1, sentiment medio dell'evidenza>,
      "strength": "<high|medium|low — quanto questo driver è solido vs ipotetico>",
      "rationale": "<1-2 frasi in italiano: perché questo driver spiega lo scenario richiesto>",
      "sample_quotes": ["<quote dal corpus, max 200 char>", ...]
    }}
  ],
  "confidence": <float 0..1, quanto sei sicuro dell'intero set>
}}

Regole:
- Genera 3-6 driver, ordinati dal più rilevante al meno rilevante
- I valori di `evidence_topic`, `mentions`, `sentiment` DEVONO essere copiati
  esattamente da uno dei topic elencati sopra (se applicabile)
- Le quote vanno scelte tra quelle fornite, non inventate
- Almeno 1 driver deve avere `strength="high"` se il corpus lo permette
- Driver con strength="low" sono accettabili ma vanno marcati onestamente
- Niente preamboli, niente code fence: solo JSON puro"""


def generate_scenario_drivers(
    seed: BrandSeed,
    *,
    scenario_brief: Optional[str] = None,
    client: Optional[MistralClient] = None,
) -> ScenarioDriversSet:
    """Estrae i driver osservati dal seed rispetto allo scenario utente.

    Se ``scenario_brief`` è vuoto o l'LLM fallisce, costruiamo un fallback
    deterministico dai top topic per non lasciare la sezione vuota.
    """
    brief = (scenario_brief or "").strip()
    if not brief:
        return _fallback_from_topics(
            seed,
            scenario_focus="Driver inferiti dai topic dominanti (nessuno scenario utente fornito).",
            model="fallback-no-brief",
            confidence=0.3,
        )

    topics_block = _format_topics_block(seed)
    if not topics_block.strip():
        return _fallback_from_topics(
            seed,
            scenario_focus="Driver inferiti dai topic dominanti (corpus senza topic estraibili).",
            model="fallback-no-topics",
            confidence=0.2,
        )

    try:
        llm = client or MistralClient()
        data = llm.chat_json(
            system=_SYSTEM_PROMPT,
            user=_USER_TEMPLATE.format(
                brand=seed.brand,
                market=seed.market,
                window_days=seed.monitoring_window_days,
                overall_sentiment=seed.overall_sentiment,
                total_mentions=seed.total_mentions,
                scenario_brief=brief[:4000],
                topics_block=topics_block,
            ),
            temperature=0.3,
        )
    except LLMError as exc:
        return _fallback_from_topics(
            seed,
            scenario_focus=f"Fallback driver-set: LLM non disponibile ({str(exc)[:120]}).",
            model="fallback-llm-error",
            confidence=0.25,
            notes=str(exc)[:200],
        )

    if not isinstance(data, dict):
        return _fallback_from_topics(
            seed,
            scenario_focus="Fallback driver-set: risposta LLM non valida.",
            model="fallback-bad-response",
            confidence=0.25,
        )

    raw_drivers = data.get("drivers", [])
    drivers: list[ScenarioDriver] = []
    for item in raw_drivers[:6] if isinstance(raw_drivers, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            drivers.append(
                ScenarioDriver(
                    label=str(item.get("label", "")).strip()[:80] or "Driver",
                    evidence_topic=str(item.get("evidence_topic", "")).strip()[:80],
                    mentions=max(0, int(item.get("mentions", 0) or 0)),
                    sentiment=_clamp(float(item.get("sentiment", 0.0) or 0.0), -1.0, 1.0),
                    strength=_normalize_strength(item.get("strength")),
                    rationale=str(item.get("rationale", "")).strip()[:500],
                    sample_quotes=[
                        str(q).strip()[:240]
                        for q in (item.get("sample_quotes") or [])[:3]
                        if str(q).strip()
                    ],
                )
            )
        except (ValueError, TypeError):
            continue

    if not drivers:
        return _fallback_from_topics(
            seed,
            scenario_focus="Fallback driver-set: nessun driver valido in risposta LLM.",
            model="fallback-empty",
            confidence=0.25,
        )

    confidence = _clamp(float(data.get("confidence", 0.6) or 0.6), 0.0, 1.0)
    return ScenarioDriversSet(
        scenario_focus=str(data.get("scenario_focus", "")).strip()[:280]
        or f"Driver osservati per: «{brief[:120]}»",
        drivers=drivers,
        model=llm.config.model,
        confidence=confidence,
    )


def _format_topics_block(seed: BrandSeed) -> str:
    """Render dei top topic in modo che il prompt possa citarli verbatim."""
    lines: list[str] = []
    for t in seed.topics[:8]:
        quotes = [q for q in (t.sample_quotes or [])[:3] if q]
        quote_str = "; ".join(f"«{q[:160]}»" for q in quotes) if quotes else "(nessuna quote)"
        lines.append(
            f"- name: \"{t.name}\" | mentions: {t.mentions} | sentiment: {t.sentiment_score:+.2f}\n"
            f"  quotes: {quote_str}"
        )
    return "\n".join(lines)


def _normalize_strength(raw) -> str:
    val = str(raw or "").strip().lower()
    if val not in {"high", "medium", "low"}:
        return "medium"
    return val


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _fallback_from_topics(
    seed: BrandSeed,
    *,
    scenario_focus: str,
    model: str,
    confidence: float,
    notes: str = "",
) -> ScenarioDriversSet:
    """Costruisce un driver-set deterministico dai top topic.

    Usato quando manca lo scenario brief o l'LLM è indisponibile: meglio una
    sezione popolata in modo trasparente che una vuota.
    """
    drivers: list[ScenarioDriver] = []
    for t in seed.topics[:3]:
        strength = (
            "high"
            if abs(t.sentiment_score) > 0.1 and t.mentions >= 200
            else "medium"
            if t.mentions >= 50
            else "low"
        )
        drivers.append(
            ScenarioDriver(
                label=f"Topic dominante: {t.name}"[:80],
                evidence_topic=t.name,
                mentions=t.mentions,
                sentiment=t.sentiment_score,
                strength=strength,  # type: ignore[arg-type]
                rationale=(
                    f"Topic con {t.mentions} menzioni e sentiment {t.sentiment_score:+.2f}: "
                    "rilevanza inferita dal volume relativo nel corpus."
                ),
                sample_quotes=[q[:240] for q in (t.sample_quotes or [])[:2] if q],
            )
        )
    return ScenarioDriversSet(
        scenario_focus=scenario_focus[:280],
        drivers=drivers,
        model=model,
        confidence=confidence,
        notes=notes[:240],
    )
