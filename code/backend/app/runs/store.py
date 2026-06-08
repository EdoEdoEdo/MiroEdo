"""
RunStore — persist report-pipeline runs as JSON files on disk.

Each run is stored at `{base_dir}/{run_id}.json`. The store is thread-safe
(file writes go through a single Lock) so that FastAPI BackgroundTasks can
safely update status from a worker thread while HTTP handlers read.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

RunStatus = Literal["pending", "running", "succeeded", "failed"]
SimulationStatus = Literal["idle", "pending", "running", "succeeded", "failed"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RunRecord:
    """Single pipeline execution."""

    run_id: str
    status: RunStatus
    mode: Literal["quick", "full"]
    brand: str
    source_type: Literal[
        "tabular",
        "document",
        "manual",
        "brandwatch_csv",
        "brandwatch_pdf",
    ]
    source_filename: Optional[str]
    enable_simulation: bool
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Dict[str, Any] = field(default_factory=dict)
    scenario_brief: Optional[str] = None
    simulation_status: SimulationStatus = "idle"
    simulation_error: Optional[str] = None
    simulation_progress: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RunStore:
    """Filesystem-backed store for `RunRecord` instances."""

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        self.base_dir = Path(base_dir or os.environ.get("MIROEDO_RUNS_DIR", "data/runs"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # === Lifecycle ===

    def create(
        self,
        *,
        mode: Literal["quick", "full"],
        brand: str,
        source_type: Literal[
            "tabular",
            "document",
            "manual",
            "brandwatch_csv",
            "brandwatch_pdf",
        ],
        source_filename: Optional[str] = None,
        enable_simulation: bool = False,
        scenario_brief: Optional[str] = None,
    ) -> RunRecord:
        now = _utcnow_iso()
        record = RunRecord(
            run_id=uuid.uuid4().hex,
            status="pending",
            mode=mode,
            brand=brand,
            source_type=source_type,
            source_filename=source_filename,
            enable_simulation=enable_simulation,
            created_at=now,
            updated_at=now,
            scenario_brief=(scenario_brief.strip() if scenario_brief else None) or None,
        )
        self._write(record)
        return record

    def update(self, run_id: str, **fields: Any) -> RunRecord:
        with self._lock:
            record = self._read(run_id)
            for key, value in fields.items():
                if not hasattr(record, key):
                    raise AttributeError(f"RunRecord has no field '{key}'")
                setattr(record, key, value)
            record.updated_at = _utcnow_iso()
            self._write_locked(record)
            return record

    def mark_running(self, run_id: str) -> RunRecord:
        return self.update(run_id, status="running")

    def mark_succeeded(self, run_id: str, result: Dict[str, Any]) -> RunRecord:
        return self.update(run_id, status="succeeded", result=result, error=None)

    def mark_failed(self, run_id: str, error: str) -> RunRecord:
        return self.update(run_id, status="failed", error=error)

    def set_progress(self, run_id: str, **progress: Any) -> RunRecord:
        with self._lock:
            record = self._read(run_id)
            record.progress = {**record.progress, **progress}
            record.updated_at = _utcnow_iso()
            self._write_locked(record)
            return record

    # === Simulation lifecycle (on-demand, post-pipeline) ===

    def mark_sim_running(self, run_id: str) -> RunRecord:
        return self.update(
            run_id,
            simulation_status="running",
            simulation_error=None,
            simulation_progress={"step": "starting"},
        )

    def mark_sim_succeeded(
        self, run_id: str, simulation: Dict[str, Any]
    ) -> RunRecord:
        with self._lock:
            record = self._read(run_id)
            base = dict(record.result or {})
            base["simulation"] = simulation
            record.result = base
            record.simulation_status = "succeeded"
            record.simulation_error = None
            record.simulation_progress = {"step": "done"}
            record.updated_at = _utcnow_iso()
            self._write_locked(record)
            return record

    def mark_sim_failed(self, run_id: str, error: str) -> RunRecord:
        return self.update(
            run_id,
            simulation_status="failed",
            simulation_error=error,
            simulation_progress={"step": "failed"},
        )

    def set_sim_progress(self, run_id: str, **progress: Any) -> RunRecord:
        with self._lock:
            record = self._read(run_id)
            record.simulation_progress = {**record.simulation_progress, **progress}
            record.updated_at = _utcnow_iso()
            self._write_locked(record)
            return record

    # === Read ===

    def get(self, run_id: str) -> RunRecord:
        with self._lock:
            return self._read(run_id)

    def list(self, *, limit: int = 50) -> List[RunRecord]:
        files = sorted(
            self.base_dir.glob("*.json"),
            # nanosecond precision + name tie-breaker for deterministic order
            # across filesystems with low mtime resolution (e.g. Docker overlayfs).
            key=lambda p: (p.stat().st_mtime_ns, p.name),
            reverse=True,
        )[:limit]
        out: List[RunRecord] = []
        with self._lock:
            for f in files:
                try:
                    out.append(self._read_path(f))
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Skip corrupted files rather than failing the whole listing.
                    continue
        return out

    # === Internal ===

    def _path(self, run_id: str) -> Path:
        if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
            raise ValueError(f"Invalid run_id: {run_id!r}")
        return self.base_dir / f"{run_id}.json"

    def _write(self, record: RunRecord) -> None:
        with self._lock:
            self._write_locked(record)

    def _write_locked(self, record: RunRecord) -> None:
        path = self._path(record.run_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # atomic rename

    def _read(self, run_id: str) -> RunRecord:
        path = self._path(run_id)
        if not path.exists():
            raise KeyError(f"Run not found: {run_id}")
        return self._read_path(path)

    def _read_path(self, path: Path) -> RunRecord:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Back-compat: tolerate older snapshots that pre-date the new fields.
        data.setdefault("simulation_status", "idle")
        data.setdefault("simulation_error", None)
        data.setdefault("simulation_progress", {})
        return RunRecord(**data)
