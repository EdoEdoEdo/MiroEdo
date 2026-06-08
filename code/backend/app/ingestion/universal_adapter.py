"""
Universal ingest adapter.

One entry point for any input the user can drop on the wizard:
- .csv / .tsv  -> pandas, deterministic column mapping (Brandwatch, Talkwalker,
  Meltwater, Sprinklr, Brand24, IT-localized exports)
- .xlsx / .xls -> pandas + openpyxl, with **auto header detection** (so massive
  Brandwatch-style exports with 5-6 metadata rows on top still work)
- .pdf / .md / .markdown / .txt -> text extraction + Mistral LLM seed
  extractor (`TextSeedExtractor`)

No vendor lock-in: the adapter routes purely on file extension and tabular
heuristics, never on filename, "Brandwatch" string, or required column names.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from app.ingestion.tabular_adapter import (
    _COLUMN_ALIASES,
    _canonicalize,
    parse_dataframe,
)
from app.ingestion.file_parser import parse_bytes as parse_text_bytes
from app.ingestion.text_seed_extractor import TextSeedExtractor
from app.llm.mistral import MistralClient
from app.schemas import BrandSeed

TABULAR_EXTS = {".csv", ".tsv", ".xlsx", ".xls"}
DOCUMENT_EXTS = {".pdf", ".md", ".markdown", ".txt"}

# Resolved bucket the dispatcher targets.
ResolvedKind = Literal["tabular", "document"]


class IngestError(ValueError):
    """Raised when no adapter can produce a usable seed from the file."""


def detect_kind(filename: str) -> ResolvedKind:
    """Map a filename to the high-level ingest path.

    Unknown extensions default to ``document`` so the LLM extractor gets a
    chance (it is robust to free text).
    """
    ext = Path(filename).suffix.lower()
    if ext in TABULAR_EXTS:
        return "tabular"
    return "document"


def ingest(
    *,
    payload: bytes,
    filename: str,
    brand: str,
    market: str = "IT",
    language: str = "it",
    llm_client: Optional[MistralClient] = None,
    text_extractor: Optional[TextSeedExtractor] = None,
) -> BrandSeed:
    """Universal entry point: bytes + filename -> BrandSeed.

    Args:
        payload: raw file bytes (from HTTP upload).
        filename: original filename, used ONLY to pick the parser via extension.
        brand: brand name (used as fallback if no auto-detection from data).
        market, language: ISO codes passed through to the BrandSeed.
        llm_client / text_extractor: dependency injection (testing).

    Raises:
        IngestError: when the file cannot be loaded or yields no usable rows.
    """
    if not payload:
        raise IngestError("Empty file")

    kind = detect_kind(filename)
    if kind == "tabular":
        df = _load_tabular(payload, filename)
        return parse_dataframe(
            df,
            brand=brand,
            market=market,
            language=language,
            source_tag="tabular",
        )

    # document path: PDF / MD / TXT -> text -> LLM seed extractor
    try:
        text = parse_text_bytes(payload, filename)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"Failed to extract text from {filename}: {exc}") from exc

    extractor = text_extractor or TextSeedExtractor(client=llm_client)
    seed = extractor.extract(text, brand_hint=brand)
    # Normalize source tag so downstream code can rely on neutral labels.
    seed.source = "document"
    return seed


# ============= Tabular loading =============


def _load_tabular(payload: bytes, filename: str) -> pd.DataFrame:
    """Load CSV/TSV/XLSX/XLS into a canonicalized DataFrame.

    For Excel files we auto-detect the header row by picking the first row
    whose values match enough of our canonical aliases. This handles vendor
    exports that prepend 5-6 metadata rows before the actual table.
    """
    ext = Path(filename).suffix.lower()
    if ext in {".csv", ".tsv"}:
        sep = "\t" if ext == ".tsv" else _sniff_csv_sep(payload)
        try:
            return pd.read_csv(io.BytesIO(payload), sep=sep)
        except Exception as exc:  # noqa: BLE001
            raise IngestError(f"Could not parse CSV: {exc}") from exc

    if ext in {".xlsx", ".xls"}:
        return _load_excel_with_header_detection(payload)

    raise IngestError(f"Unsupported tabular extension '{ext}'")


def _sniff_csv_sep(payload: bytes) -> str:
    """Return ',' or ';' based on which appears more on the first ~2KB."""
    head = payload[:2048].decode("utf-8", errors="ignore")
    return ";" if head.count(";") > head.count(",") else ","


def _load_excel_with_header_detection(payload: bytes) -> pd.DataFrame:
    """Try headers 0..10 and pick the one that yields the most canonical fields.

    Falls back to ``header=0`` if every attempt is unrecognizable.
    """
    try:
        import openpyxl  # noqa: F401 — required by pandas engine
    except ImportError as exc:
        raise IngestError(
            "openpyxl not installed; cannot read .xlsx files. "
            "Add 'openpyxl>=3.1.0' to requirements."
        ) from exc

    buf = io.BytesIO(payload)
    # Quickly read once with no header to know how many rows we have.
    try:
        probe = pd.read_excel(buf, sheet_name=0, header=None, nrows=15, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"Could not open Excel file: {exc}") from exc

    candidates: list[tuple[int, int]] = []  # (header_row, match_score)
    for h in range(min(11, len(probe))):
        try:
            buf.seek(0)
            df = pd.read_excel(buf, sheet_name=0, header=h, nrows=2, engine="openpyxl")
        except Exception:
            continue
        score = _alias_match_score(df.columns)
        if score > 0:
            candidates.append((h, score))

    if not candidates:
        # Try header=0 once and let parse_dataframe raise a friendlier error.
        buf.seek(0)
        return pd.read_excel(buf, sheet_name=0, header=0, engine="openpyxl")

    best_header = max(candidates, key=lambda x: x[1])[0]
    buf.seek(0)
    df = pd.read_excel(buf, sheet_name=0, header=best_header, engine="openpyxl")
    # Drop "Unnamed:" columns that pandas creates from blank header cells.
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    return df


def _alias_match_score(columns) -> int:
    """Count how many canonical fields are present in the column list."""
    lower = {str(c).strip().lower() for c in columns}
    score = 0
    for aliases in _COLUMN_ALIASES.values():
        if any(a in lower for a in aliases):
            score += 1
    return score


__all__ = ["ingest", "detect_kind", "IngestError", "TABULAR_EXTS", "DOCUMENT_EXTS"]
