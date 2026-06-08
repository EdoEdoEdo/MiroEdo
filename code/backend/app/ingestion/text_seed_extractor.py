"""
TextSeedExtractor — turn unstructured text (PDF/MD/TXT) into a `BrandSeed`
via Mistral LLM. Used when input is NOT a Brandwatch CSV.

Strategy:
- One LLM call with strict JSON schema instructions.
- Pydantic validation on the output, raising ValueError on schema mismatch.
- Truncation guard: input text is capped to ~24k chars to stay within
  context budgets (Mistral Nemo = 128k, but we keep prompts lean).
- Postprocess fallback: if the LLM misses an explicit weekly-volume table
  in the source, a regex sweeps the raw text and populates
  `volume_series_weekly` directly (defensive, no-op when LLM did its job).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from app.llm.mistral import LLMError, MistralClient
from app.schemas import BrandSeed

_MAX_TEXT_CHARS = 24_000

_SYSTEM_PROMPT = """\
You are a senior brand-insights analyst. Given an unstructured market/brand \
research document (Italian or English), you extract a structured BrandSeed in \
JSON format.

Output MUST be a single JSON object matching this schema EXACTLY (no markdown, \
no commentary):

{
  "brand": "<brand name>",
  "market": "<ISO country, e.g. 'IT'>",
  "language": "<ISO lang, e.g. 'it'>",
  "monitoring_window_days": <int, 1-365, infer from document or default 30>,
  "total_mentions": <int >=0, infer or estimate>,
  "overall_sentiment": <float -1.0 to +1.0>,
  "segments": [
    {
      "name": "<segment name>",
      "weight": <float 0-1, sum across segments ~= 1>,
      "description": "<one sentence>",
      "sentiment_baseline": "positive|neutral|negative|mixed",
      "sample_quotes": ["<verbatim or paraphrased>"]
    }
  ],
  "topics": [
    {
      "name": "<topic>",
      "mentions": <int>,
      "sentiment_score": <float -1 to +1>,
      "sample_quotes": []
    }
  ],
  "timeline": [
    {"date": "YYYY-MM-DD", "label": "<event>", "mentions": <int>, "note": ""}
  ],
  "volume_series_weekly": [
    {"date": "YYYY-MM-DD (Monday of the ISO week)", "label": "weekly_volume", "mentions": <int>, "note": ""}
  ],
  "source": "brandwatch_pdf"
}

# SOURCE HIERARCHY — read this carefully
When extracting numeric values you MUST respect this priority:
  1. EXPLICIT TABLES with header rows (e.g. "Settimana | Mention", "Week | \
Volume"). These are the GROUND TRUTH for `volume_series_weekly` and \
`total_mentions`.
  2. Numbered lists or KPI bullets that explicitly label the metric \
(e.g. "Mention totali: 1.247").
  3. Free prose. Use only if (1) and (2) are absent — and clearly mark \
estimates.

# SEMANTIC DISAMBIGUATION — what counts as a "mention"
The document may contain MULTIPLE numeric series. Treat them as DIFFERENT \
metrics — never mix them:
  * mention / menzione / post / citazione        → counts as a MENTION
  * view / visualizzazione / impression / reach  → NOT a mention, IGNORE \
unless explicitly asked
  * like / reaction / heart / clap               → NOT a mention, IGNORE
  * comment / commento / reply                   → NOT a mention, IGNORE
  * share / repost / retweet                     → NOT a mention, IGNORE
  * follower / iscritto / subscriber             → NOT a mention, IGNORE

# NEVER EXTRACT NUMBERS FROM
  * Section numbering ("01 ·", "2.1", "Sezione 3")
  * List item counters ("1.", "2.", "3)")
  * Page numbers, footnote markers ("[1]", "(2)")
  * Dates already represented as ISO strings
  * Generic counts ("undici lotti", "tre settimane") unless a unit is attached

# RULES
- Produce 2-5 segments and 3-8 topics, even if the document is sparse \
(reasonable inference is OK).
- segments[*].weight MUST sum to ~1.0.
- `volume_series_weekly`: populate ONLY if the document has an explicit \
table or paragraph aggregating mention volume per week. If absent, return [] \
— do NOT fabricate a series.
- `timeline`: contains named DATED EVENTS (recall, press release, launch). \
The `mentions` field there is the spike count for that event, NOT the weekly \
volume. If you do not know the spike size, set mentions to 0.
- Quotes in `sample_quotes` MUST be verbatim from the document (within \
quotation marks in the source). If no verbatim quote exists for a segment, \
return an empty list — do NOT paraphrase.
- If a numeric value is unknown, infer a plausible estimate, never use null.
- Respond with the JSON object only.
"""


class TextSeedExtractor:
    """Wraps Mistral to produce a `BrandSeed` from free text."""

    def __init__(self, client: Optional[MistralClient] = None) -> None:
        self.client = client or MistralClient()

    def extract(self, text: str, *, brand_hint: Optional[str] = None) -> BrandSeed:
        if not text or not text.strip():
            raise ValueError("Input text is empty")

        trimmed = text[:_MAX_TEXT_CHARS]
        user_msg = trimmed
        if brand_hint:
            user_msg = f"Brand hint (override if document is clear): {brand_hint}\n\n---\n\n{trimmed}"

        try:
            data = self.client.chat_json(_SYSTEM_PROMPT, user_msg, temperature=0.2)
        except LLMError as exc:
            raise ValueError(f"LLM extraction failed: {exc}") from exc

        # Force source tag — LLM sometimes echoes "manual"
        data["source"] = "brandwatch_pdf"
        _coerce_seed_payload(data)
        # Defensive fallback: if the LLM missed a weekly volume table that
        # is obviously present in the raw text, recover it via regex.
        if not data.get("volume_series_weekly"):
            recovered = _recover_weekly_volume(trimmed)
            if recovered:
                data["volume_series_weekly"] = recovered
        try:
            return BrandSeed(**data)
        except Exception as exc:
            raise ValueError(f"LLM output did not match BrandSeed schema: {exc}") from exc


_SENTIMENT_BUCKETS = {
    "positive": "positive",
    "very positive": "positive",
    "pos": "positive",
    "positivo": "positive",
    "negative": "negative",
    "very negative": "negative",
    "neg": "negative",
    "negativo": "negative",
    "neutral": "neutral",
    "neutro": "neutral",
    "mixed": "mixed",
    "misto": "mixed",
}


def _coerce_seed_payload(data: dict) -> None:
    """Normalize fields the LLM tends to drift on (sentiment labels, ranges)."""
    segments = data.get("segments")
    if isinstance(segments, list):
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            raw = str(seg.get("sentiment_baseline", "mixed")).strip().lower()
            seg["sentiment_baseline"] = _SENTIMENT_BUCKETS.get(raw, "mixed")
    # clamp monitoring_window_days into the schema range
    try:
        w = int(data.get("monitoring_window_days") or 30)
        data["monitoring_window_days"] = max(1, min(w, 365))
    except (TypeError, ValueError):
        data["monitoring_window_days"] = 30
    # clamp overall_sentiment
    try:
        s = float(data.get("overall_sentiment") or 0.0)
        data["overall_sentiment"] = max(-1.0, min(s, 1.0))
    except (TypeError, ValueError):
        data["overall_sentiment"] = 0.0
    # validate volume_series_weekly: drop malformed entries, snap dates to Monday
    raw_series = data.get("volume_series_weekly")
    if isinstance(raw_series, list):
        cleaned: list[dict] = []
        for ev in raw_series:
            if not isinstance(ev, dict):
                continue
            iso = str(ev.get("date", ""))[:10]
            try:
                dt = datetime.fromisoformat(iso)
            except (ValueError, TypeError):
                continue
            monday = dt - timedelta(days=dt.weekday())
            try:
                mentions = int(ev.get("mentions") or 0)
            except (TypeError, ValueError):
                mentions = 0
            if mentions < 0:
                mentions = 0
            cleaned.append(
                {
                    "date": monday.date().isoformat(),
                    "label": str(ev.get("label", "weekly_volume"))[:80],
                    "mentions": mentions,
                    "note": str(ev.get("note", ""))[:200],
                }
            )
        data["volume_series_weekly"] = cleaned
    else:
        data["volume_series_weekly"] = []


# Inline pattern: "<date> ... <N> mention" on a single line.
# Conservative — requires the keyword to avoid catching views/likes/etc.
_WEEK_LINE_RE = re.compile(
    r"(?P<date>"
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"
    r"|\d{1,2}\s+(?:gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic|"
    r"january|february|march|april|may|june|july|august|september|"
    r"october|november|december|"
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    r"settembre|ottobre|novembre|dicembre)[a-z]*\s+\d{2,4}"
    r")"
    r"[^\n\d]{1,40}?"
    r"(?P<mentions>\d{1,3}(?:[.,]\d{3})*|\d+)"
    r"\s*"
    r"(?:menzion|mention)",
    re.IGNORECASE,
)

# Tabular pattern: PDF tables get flattened to one cell per line. After a
# header containing "Mention", we expect rows of <date>\n<int>[\n<float>].
_TABLE_HEADER_RE = re.compile(r"(?:^|\n)[^\n]*\bmention[^\n]*", re.IGNORECASE)
# Loose "line starts with date-like token" check. We capture only enough to
# decide whether the line is a date row; the full stripped line is passed to
# `_first_date_in_range`, which handles ranges like "02 mar – 08 mar 2026".
_DATE_LINE_RE = re.compile(
    r"^\s*(?:"
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
    r"|\d{1,2}\s+[a-zA-Z]{3,}"  # "02 mar" / "12 maggio" — year optional
    r")\b"
)
_INT_LINE_RE = re.compile(r"^\s*(\d{1,3}(?:[.,]\d{3})*|\d+)\s*$")

_MONTHS = {
    "gen": 1, "gennaio": 1, "jan": 1, "january": 1,
    "feb": 2, "febbraio": 2, "february": 2,
    "mar": 3, "marzo": 3, "march": 3,
    "apr": 4, "aprile": 4, "april": 4,
    "mag": 5, "maggio": 5, "may": 5,
    "giu": 6, "giugno": 6, "jun": 6, "june": 6,
    "lug": 7, "luglio": 7, "jul": 7, "july": 7,
    "ago": 8, "agosto": 8, "aug": 8, "august": 8,
    "set": 9, "settembre": 9, "sep": 9, "sept": 9, "september": 9,
    "ott": 10, "ottobre": 10, "oct": 10, "october": 10,
    "nov": 11, "novembre": 11, "november": 11,
    "dic": 12, "dicembre": 12, "dec": 12, "december": 12,
}


def _parse_loose_date(raw: str) -> Optional[datetime]:
    """Parse ISO, dd/mm/yyyy, dd-mm-yyyy, '12 maggio 2025', '02 mar 2026' — None on fail.

    Date ranges like '02 mar – 08 mar 2026' must be split BEFORE calling this:
    pass only the first half. We do try to recover the year from the second half
    if the input itself omits it: '02 mar' alone returns None.
    """
    raw = raw.strip().rstrip(".,;:")
    # ISO
    try:
        return datetime.fromisoformat(raw[:10])
    except ValueError:
        pass
    # numeric dd[/-.]mm[/-.]yyyy
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", raw)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, d)
        except ValueError:
            return None
    # "12 maggio 2025" / "12 may 2025" / "02 mar 2026"
    m = re.match(r"(\d{1,2})\s+([a-zA-Z]+)\s+(\d{2,4})$", raw)
    if m:
        d, mo_name, y = m.group(1), m.group(2).lower(), m.group(3)
        mo = _MONTHS.get(mo_name) or _MONTHS.get(mo_name[:3])
        if not mo:
            return None
        y = int(y)
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, int(d))
        except ValueError:
            return None
    return None


def _first_date_in_range(raw: str) -> Optional[datetime]:
    """Given a possibly-range string like '02 mar – 08 mar 2026', parse the
    first date, borrowing the year from the second half if needed.
    """
    # Split on en/em dash, hyphen with spaces, or 'al'/'to'
    parts = re.split(r"\s*(?:–|—|-|/|al|to)\s+", raw, maxsplit=1)
    head = parts[0].strip()
    tail = parts[1].strip() if len(parts) > 1 else ""
    # If head lacks a year (e.g. "02 mar"), borrow trailing 4-digit year from tail.
    if not re.search(r"\d{4}|\d{2}\b", head.split()[-1]):
        tail_year = re.search(r"\b(\d{4}|\d{2})\b\s*$", tail)
        if tail_year:
            head = f"{head} {tail_year.group(1)}"
    return _parse_loose_date(head)


def _recover_weekly_volume(text: str) -> list[dict]:
    """Sweep raw text for an explicit weekly mention volume series.

    Two passes (deduped, weeks snapped to Monday):
      1. Inline pattern (`<date> ... <N> mention`) for prose.
      2. Tabular pattern: a header line containing 'mention' followed by
         alternating date/integer cells (one per line, as flattened by PDF
         text extraction). Sentiment floats and other non-integer cells are
         skipped between rows.
    Returns at most 12 entries.
    """
    buckets: dict[str, int] = {}

    # Pass 1: inline
    for match in _WEEK_LINE_RE.finditer(text):
        dt = _parse_loose_date(match.group("date"))
        if not dt:
            continue
        monday = dt - timedelta(days=dt.weekday())
        key = monday.date().isoformat()
        try:
            n = int(match.group("mentions").replace(".", "").replace(",", ""))
        except ValueError:
            continue
        if n <= 0:
            continue
        buckets[key] = max(buckets.get(key, 0), n)

    # Pass 2: tabular. For each header containing 'mention', scan up to 80
    # subsequent lines for date/int pairs.
    for header_match in _TABLE_HEADER_RE.finditer(text):
        tail = text[header_match.end():header_match.end() + 4000]
        lines = tail.split("\n")
        i = 0
        rows_found = 0
        while i < len(lines) and rows_found < 20:
            line = lines[i].strip()
            i += 1
            if not line:
                continue
            date_match = _DATE_LINE_RE.match(line)
            if not date_match:
                # Stop scanning a table once we hit a long prose line, signalling
                # we've left the table region.
                if len(line) > 60 and not _INT_LINE_RE.match(line):
                    break
                continue
            dt = _first_date_in_range(line)
            if not dt:
                continue
            # Look ahead up to 4 lines for the first integer cell.
            n = None
            for j in range(i, min(i + 4, len(lines))):
                cand = lines[j].strip()
                if not cand:
                    continue
                int_match = _INT_LINE_RE.match(cand)
                if int_match:
                    try:
                        n = int(int_match.group(1).replace(".", "").replace(",", ""))
                    except ValueError:
                        n = None
                    i = j + 1
                    break
                # Skip floats (sentiment) — but if we hit another date, abort
                # this row.
                if _DATE_LINE_RE.match(cand):
                    break
            if n is not None and n > 0:
                monday = dt - timedelta(days=dt.weekday())
                key = monday.date().isoformat()
                buckets[key] = max(buckets.get(key, 0), n)
                rows_found += 1

    items = sorted(buckets.items())[:12]
    return [
        {"date": k, "label": "weekly_volume", "mentions": v, "note": "recovered_from_text"}
        for k, v in items
    ]
