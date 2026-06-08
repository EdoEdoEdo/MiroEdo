"""
Optional Zep integration package.

`zep_cloud` is an optional dependency. Import it lazily at module level so
that the rest of MiroEdo can run without it.

Usage:
    from app.engine.zep import is_zep_available, ZepEntityReader, create_zep_client

    if is_zep_available() and config.zep_enabled:
        client = create_zep_client(config)
        reader = ZepEntityReader(client)
        result = reader.filter_defined_entities(graph_id)
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from zep_cloud.client import Zep as _Zep  # type: ignore

    _ZEP_AVAILABLE = True
    _ZEP_IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:  # ImportError or any other surprise
    _Zep = None  # type: ignore
    _ZEP_AVAILABLE = False
    _ZEP_IMPORT_ERROR = _exc


def is_zep_available() -> bool:
    """Return True if the `zep_cloud` package is importable."""
    return _ZEP_AVAILABLE


def zep_import_error() -> Optional[Exception]:
    """Return the import error encountered while loading `zep_cloud`, if any."""
    return _ZEP_IMPORT_ERROR


def create_zep_client(api_key: str) -> Any:
    """Instantiate a Zep client. Raises RuntimeError if zep is not installed."""
    if not _ZEP_AVAILABLE:
        raise RuntimeError(
            "zep_cloud is not installed; install `pip install zep-cloud` to enable "
            "Zep features, or run MiroEdo with zep_enabled=False."
        )
    if not api_key:
        raise ValueError("Zep api_key is required")
    return _Zep(api_key=api_key)  # type: ignore[misc]


# Lazy export: the entity_reader / tools modules import `zep_cloud` itself,
# so only expose them when available to avoid import-time failures.
if _ZEP_AVAILABLE:
    from app.engine.zep.entity_reader import ZepEntityReader  # noqa: F401
    from app.engine.zep.tools import ZepToolsService  # noqa: F401

__all__ = [
    "create_zep_client",
    "is_zep_available",
    "zep_import_error",
]
if _ZEP_AVAILABLE:
    __all__.extend(["ZepEntityReader", "ZepToolsService"])
