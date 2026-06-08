"""Executive Summary generator (Fase B — LLM via Mistral)."""

from __future__ import annotations

from typing import Optional

from app.llm.mistral import LLMError, MistralClient
from app.schemas import ExecutiveSummary

_SYSTEM_PROMPT = (
    "Sei un analista senior di brand insight per il mercato italiano. "
    "Riceverai un report di simulazione multi-agente su un brand. "
    "Devi produrre un Executive Summary in ITALIANO, business tone, conciso e azionabile, "
    "destinato a un Brand Manager che ha 5 minuti per decidere. "
    "Rispondi ESCLUSIVAMENTE in JSON valido senza testo extra."
)

_USER_TEMPLATE = """Brand: {brand}
Mercato: {market}
{scenario_block}
REPORT MIROFISH (markdown):
---
{report}
---

Genera un JSON con questa struttura ESATTA:
{{
  "summary_it": "<riassunto in italiano, MAX 200 parole, focalizzato su: contesto, sentiment dominante, segmenti critici, rischi/opportunità principali>",
  "key_findings": ["<bullet 1>", "<bullet 2>", "<bullet 3>", "<bullet 4 opzionale>", "<bullet 5 opzionale>"],
  "confidence": <float 0.0-1.0 sulla qualità delle informazioni nel report>
}}

Regole:
- summary_it MUST essere in italiano corretto, no anglismi inutili
- key_findings: 3-5 elementi, ognuno ≤25 parole, con dati quantitativi se presenti nel report
- Non inventare numeri non presenti nel report
- Niente preamboli, niente markdown code fence: solo JSON puro"""


def generate_executive_summary(
    report_markdown: str,
    *,
    brand: str = "Brand",
    market: str = "IT",
    client: Optional[MistralClient] = None,
    target_words: int = 200,
    scenario_brief: Optional[str] = None,
) -> ExecutiveSummary:
    """
    Genera Executive Summary IT da un report MiroFish.

    Returns:
        ExecutiveSummary popolato. In caso di errore LLM ritorna fallback
        deterministico (non solleva eccezioni).
    """
    if not report_markdown.strip():
        return ExecutiveSummary(
            summary_it="Report vuoto, nessun summary generabile.",
            key_findings=[],
            confidence=0.0,
            model="fallback",
        )

    trimmed = report_markdown[:20000]
    scenario_block = _format_scenario_block(scenario_brief)

    try:
        llm = client or MistralClient()
        data = llm.chat_json(
            system=_SYSTEM_PROMPT,
            user=_USER_TEMPLATE.format(
                brand=brand,
                market=market,
                report=trimmed,
                scenario_block=scenario_block,
            ),
            temperature=0.3,
        )
        return ExecutiveSummary(
            summary_it=str(data.get("summary_it", "")).strip()[: target_words * 8],
            key_findings=[
                str(x).strip() for x in data.get("key_findings", []) if str(x).strip()
            ][:5],
            confidence=float(data.get("confidence", 0.6)),
            model=llm.config.model,
        )
    except LLMError as exc:
        return _fallback_summary(report_markdown, error=str(exc))


def _format_scenario_block(scenario_brief: Optional[str]) -> str:
    """Render lo scenario utente come blocco contestuale per il prompt LLM."""
    if not scenario_brief or not scenario_brief.strip():
        return ""
    cleaned = scenario_brief.strip()[:4000]
    return (
        "\nSCENARIO BUSINESS (richiesta dell'utente che inquadra la lettura del report):\n"
        "---\n"
        f"{cleaned}\n"
        "---\n"
        "Tieni conto di questo scenario per orientare il summary e i key_findings, "
        "ma usa SOLO numeri/evidenze presenti nel report.\n"
    )


def _fallback_summary(report_markdown: str, *, error: str = "") -> ExecutiveSummary:
    """Fallback deterministico se l'LLM non è raggiungibile."""
    paragraphs = [p.strip() for p in report_markdown.split("\n\n") if p.strip()]
    thesis = next(
        (p for p in paragraphs if not p.startswith("#") and len(p) > 100),
        "Executive Summary non disponibile (fallback).",
    )
    note = f" [LLM non disponibile: {error}]" if error else ""
    return ExecutiveSummary(
        summary_it=(thesis[:1200] + note).strip(),
        key_findings=[],
        confidence=0.2,
        model="fallback",
    )
