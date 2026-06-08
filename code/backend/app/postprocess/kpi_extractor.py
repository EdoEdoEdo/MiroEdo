"""
KPIExtractor — estrae KPI quantitativi da un report MiroFish (markdown).

100% deterministico, no LLM. Lavora su:
- regex per percentuali, numeri assoluti, timeframe
- conteggio strutturale (capitoli, blockquote, predizioni numerate)
- parole-chiave per identificare segmenti citati

In Fase B aggiungeremo un layer LLM opzionale per rifinire gli score.
"""

from __future__ import annotations

import re

from app.schemas import ReportKPI, TimeframePrediction


_RE_PERCENT = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")
_RE_TIMEFRAME = re.compile(
    r"\b(?:within|in the next|nelle prossime|entro|nei prossimi|prossime|prossimi)\s+"
    r"(\d+(?:\s*[-–]\s*\d+)?)\s*(hours?|hour|ore|days?|day|giorni|weeks?|week|settimane|months?|mesi)\b",
    re.IGNORECASE,
)
_RE_CHAPTER = re.compile(r"^##\s+0?\d", re.MULTILINE)
_RE_PREDICTIVE = re.compile(
    r"(?:^|\n)\s*\d+\.\s+",  # liste numerate (proxy per predizioni)
)
_RE_BLOCKQUOTE = re.compile(r"^>\s+.+", re.MULTILINE)

# Segment-name dictionary (estendibile). Match case-insensitive su token-boundary.
_KNOWN_SEGMENTS = [
    # generici
    "media",
    "platform",
    "platforms",
    "parents",
    "genitori",
    "students",
    "studenti",
    "alumni",
    "commentators",
    "commentatori",
    "investigative",
    "experts",
    "esperti",
    # consumer brand (per il caso Mulino Bianco)
    "consumatori",
    "consumer",
    "consumers",
    "gen z",
    "millennial",
    "millennials",
    "famiglie",
    "families",
    "boomers",
    "influencer",
    "influencers",
    "retailer",
    "retailers",
    "competitor",
    "competitors",
]


def _extract_percentages(text: str) -> list[dict]:
    """Trova ogni % nel testo e cattura una breve frase di contesto (±80 char)."""
    results: list[dict] = []
    for m in _RE_PERCENT.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if value > 100:  # filtra falsi positivi tipo "1000%"
            continue
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        context = text[start:end].replace("\n", " ").strip()
        results.append({"value": value, "context": context})
    return results


def _extract_timeframes(text: str) -> list[TimeframePrediction]:
    results: list[TimeframePrediction] = []
    for m in _RE_TIMEFRAME.finditer(text):
        amount = re.sub(r"\s+", "", m.group(1))
        unit = m.group(2).lower()
        # normalizza
        unit_map = {
            "hour": "h",
            "hours": "h",
            "ore": "h",
            "day": "d",
            "days": "d",
            "giorni": "d",
            "week": "w",
            "weeks": "w",
            "settimane": "w",
            "month": "mo",
            "months": "mo",
            "mesi": "mo",
        }
        tf = f"{amount}{unit_map.get(unit, unit)}"
        # contesto: la frase contenente il match
        start = max(0, text.rfind(".", 0, m.start()) + 1)
        end = text.find(".", m.end())
        if end == -1:
            end = min(len(text), m.end() + 120)
        sentence = text[start:end].strip()
        results.append(TimeframePrediction(timeframe=tf, text=sentence))
    return results


def _extract_segments(text: str) -> list[str]:
    found: set[str] = set()
    lower = text.lower()
    for seg in _KNOWN_SEGMENTS:
        # match con word-boundary su stringhe multi-parola
        pattern = r"\b" + re.escape(seg) + r"\b"
        if re.search(pattern, lower):
            found.add(seg)
    return sorted(found)


def _quantitative_density(text: str) -> int:
    """% di paragrafi che contengono almeno un numero (proxy di densità quantitativa)."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return 0
    with_numbers = sum(1 for p in paragraphs if re.search(r"\d", p))
    return round(with_numbers * 100 / len(paragraphs))


def extract_kpi(report_markdown: str) -> ReportKPI:
    """
    Entrypoint principale.

    Args:
        report_markdown: il testo markdown del report MiroFish.

    Returns:
        ReportKPI con i KPI quantitativi estratti.
    """
    return ReportKPI(
        percentages_found=_extract_percentages(report_markdown),
        timeframes_found=_extract_timeframes(report_markdown),
        segments_mentioned=_extract_segments(report_markdown),
        chapter_count=len(_RE_CHAPTER.findall(report_markdown)),
        predictive_conclusion_count=len(_RE_PREDICTIVE.findall(report_markdown)),
        blockquote_count=len(_RE_BLOCKQUOTE.findall(report_markdown)),
        word_count=len(report_markdown.split()),
        quantitative_density_score=_quantitative_density(report_markdown),
    )
