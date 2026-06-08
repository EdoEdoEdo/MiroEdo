"""Deprecated alias for ``app.ingestion.tabular_adapter``.

Kept for backward compatibility with persisted runs and external callers that
still import the legacy ``brandwatch_csv_adapter`` module. New code MUST import
from :mod:`app.ingestion.tabular_adapter`.
"""

from __future__ import annotations

from app.ingestion.tabular_adapter import *  # noqa: F401,F403
from app.ingestion.tabular_adapter import (  # noqa: F401
    parse_csv,
    parse_dataframe,
)
