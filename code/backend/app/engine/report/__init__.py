"""Report Agent package (requires Zep)."""

from app.engine.zep import is_zep_available

if not is_zep_available():
    # Provide a stub that raises on use; this lets `from app.engine.report import ...`
    # succeed at import time even when zep_cloud is missing.
    class _MissingZep:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "ReportAgent requires zep_cloud. Install with `pip install zep-cloud` "
                "and set ZEP_API_KEY, or use a non-Zep report path."
            )

    ReportAgent = _MissingZep  # type: ignore
    ReportManager = _MissingZep  # type: ignore
    configure = lambda *_args, **_kwargs: None  # type: ignore
else:
    from app.engine.report.agent import (
        ReportAgent,
        ReportManager,
        ReportOutline,
        ReportSection,
        ReportStatus,
        Report,
        configure,
    )

__all__ = ["ReportAgent", "ReportManager", "configure"]
