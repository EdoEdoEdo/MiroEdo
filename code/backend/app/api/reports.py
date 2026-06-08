"""
Reports API — orchestrates pipeline runs as background jobs persisted via RunStore.

Endpoints:
- POST /reports         create a new run (multipart upload + form fields)
- GET  /reports/{id}    retrieve a single run
- GET  /reports         list recent runs
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ingestion.file_parser import SUPPORTED_EXTENSIONS
from app.ingestion.universal_adapter import (
    DOCUMENT_EXTS,
    TABULAR_EXTS,
    detect_kind,
)
from app.pipeline import PipelineMode, ReportPipeline, SourceType
from app.postprocess.chat import (
    ChatError,
    ChatMessage,
    chat_with_report,
    chat_with_report_stream,
    index_report,
)
from app.postprocess.chat_agent import chat_agent_with_report
from app.runs import RunRecord, RunStore

router = APIRouter(prefix="/reports", tags=["reports"])

# Module-level singleton; FastAPI handlers reuse it across requests.
_store: Optional[RunStore] = None


def get_store() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore()
    return _store


def _simulation_default() -> bool:
    return os.environ.get("MIROEDO_ENABLE_SIMULATION", "true").lower() in {"1", "true", "yes"}


class RunCreatedResponse(BaseModel):
    run_id: str
    status: str
    mode: str
    brand: str


class RunResponse(BaseModel):
    run_id: str
    status: str
    mode: str
    brand: str
    source_type: str
    source_filename: Optional[str]
    enable_simulation: bool
    created_at: str
    updated_at: str
    progress: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    scenario_brief: Optional[str] = None
    simulation_status: str = "idle"
    simulation_error: Optional[str] = None
    simulation_progress: Dict[str, Any] = {}

    @classmethod
    def from_record(cls, rec: RunRecord) -> "RunResponse":
        return cls(**rec.to_dict())


# === Endpoints ===


@router.post("", response_model=RunCreatedResponse, status_code=202)
async def create_report(
    background: BackgroundTasks,
    file: UploadFile = File(
        ...,
        description="Any social-listening export (CSV/XLSX) or brief (PDF/MD/TXT)",
    ),
    brand: str = Form(..., description="Brand name, e.g. 'Mulino Bianco'"),
    source_type: Optional[SourceType] = Form(
        None,
        description="Optional; auto-detected from file extension if omitted",
    ),
    mode: PipelineMode = Form("quick"),
    enable_simulation: Optional[bool] = Form(
        None,
        description="DEPRECATED. Simulation is now triggered on-demand via "
        "POST /reports/{run_id}/simulation. Ignored.",
    ),
    scenario_brief: Optional[str] = Form(
        None,
        description="Optional business scenario / prediction question (free text)",
    ),
    sim_profiles: Optional[int] = Form(
        None,
        description="DEPRECATED. Use POST /reports/{run_id}/simulation. Ignored.",
    ),
    sim_rounds: Optional[int] = Form(
        None,
        description="DEPRECATED. Use POST /reports/{run_id}/simulation. Ignored.",
    ),
    llm_model: Optional[str] = Form(
        None,
        description="Catalog id of the LLM model to use (e.g. 'groq/llama-3.3-70b'). If omitted, server default is used.",
    ),
) -> RunCreatedResponse:
    """Kick off a new report run. Returns immediately with run_id."""
    filename = file.filename or "upload.bin"
    ext = Path(filename).suffix.lower()

    # Auto-detect when not provided; normalize legacy aliases to neutral kinds.
    if source_type is None:
        source_type = detect_kind(filename)
    elif source_type == "brandwatch_csv":
        source_type = "tabular"
    elif source_type == "brandwatch_pdf":
        source_type = "document"

    accepted = TABULAR_EXTS | DOCUMENT_EXTS
    if ext and ext not in accepted:
        raise HTTPException(
            400,
            f"Unsupported file extension '{ext}'. Accepted: {sorted(accepted)}",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(400, "Uploaded file is empty")

    sim_flag = _simulation_default() if enable_simulation is None else enable_simulation
    scenario = (scenario_brief or "").strip() or None
    if scenario and len(scenario) > 4000:
        scenario = scenario[:4000]

    # `sim_profiles`/`sim_rounds`/`enable_simulation` are intentionally ignored
    # at upload time. Simulation now runs on demand via the dedicated endpoint.
    _ = (sim_profiles, sim_rounds)

    store = get_store()
    record = store.create(
        mode=mode,
        brand=brand,
        source_type=source_type,
        source_filename=filename,
        enable_simulation=sim_flag,
        scenario_brief=scenario,
    )

    background.add_task(
        _run_pipeline_job,
        run_id=record.run_id,
        payload=payload,
        filename=filename,
        brand=brand,
        source_type=source_type,
        mode=mode,
        scenario_brief=scenario,
        llm_model=llm_model,
    )

    return RunCreatedResponse(
        run_id=record.run_id, status=record.status, mode=record.mode, brand=record.brand
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_report(run_id: str) -> RunResponse:
    try:
        return RunResponse.from_record(get_store().get(run_id))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("", response_model=List[RunResponse])
def list_reports(limit: int = 50) -> List[RunResponse]:
    limit = max(1, min(limit, 200))
    return [RunResponse.from_record(r) for r in get_store().list(limit=limit)]


# === Simulation (on-demand OASIS run) ===


class SimulationRequest(BaseModel):
    profiles: int = 120
    rounds: int = 10
    model: Optional[str] = None


def _run_simulation_job(
    *, run_id: str, profiles: int, rounds: int, model: Optional[str]
) -> None:
    """Background worker: runs OASIS simulation on top of an already completed report."""
    from app.schemas import BrandSeed

    store = get_store()
    try:
        rec = store.get(run_id)
        seed_dict = (rec.result or {}).get("brand_seed") or {}
        if not seed_dict:
            store.mark_sim_failed(run_id, "Run result missing brand_seed; cannot simulate.")
            return
        seed = BrandSeed.model_validate(seed_dict)

        def on_progress(step: str, **kw: Any) -> None:
            try:
                store.set_sim_progress(run_id, step=step, **kw)
            except Exception:  # noqa: BLE001
                pass

        pipeline = ReportPipeline(on_progress=on_progress)
        actions_log = store.base_dir / f"{run_id}.actions.jsonl"
        sim, warnings = pipeline.simulate_only(
            seed,
            sim_profiles=profiles,
            sim_rounds=rounds,
            oasis_model=model,
            actions_log_path=actions_log,
            scenario_brief=rec.scenario_brief,
        )
        if sim is None:
            store.mark_sim_failed(
                run_id,
                "; ".join(warnings) or "Simulation produced no output.",
            )
        else:
            store.mark_sim_succeeded(run_id, simulation=sim)
    except Exception as exc:  # noqa: BLE001
        store.mark_sim_failed(run_id, error=f"{type(exc).__name__}: {exc}")


@router.post(
    "/{run_id}/simulation",
    response_model=RunResponse,
    status_code=202,
)
def start_simulation(
    run_id: str,
    body: SimulationRequest,
    background: BackgroundTasks,
) -> RunResponse:
    """Trigger on-demand OASIS simulation for an already-succeeded report."""
    store = get_store()
    try:
        rec = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc

    if rec.status != "succeeded" or not rec.result:
        raise HTTPException(409, "Report not ready: base pipeline must succeed first.")
    if rec.simulation_status == "running":
        raise HTTPException(409, "Simulation already running for this run.")

    profiles = max(3, min(int(body.profiles), 120))
    rounds = max(1, min(int(body.rounds), 10))
    model = (body.model or "").strip() or None

    store.mark_sim_running(run_id)
    background.add_task(
        _run_simulation_job,
        run_id=run_id,
        profiles=profiles,
        rounds=rounds,
        model=model,
    )
    return RunResponse.from_record(store.get(run_id))


# === Actions stream (per-action JSONL tail, MiroFish-style) ===


class ActionsResponse(BaseModel):
    run_id: str
    cursor: int
    rows: List[Dict[str, Any]]
    done: bool


@router.get("/{run_id}/actions", response_model=ActionsResponse)
def get_actions_stream(
    run_id: str, cursor: int = 0, limit: int = 500
) -> ActionsResponse:
    """Tail the per-action JSONL written by the OASIS runner during the sim.

    The frontend polls this endpoint with the last cursor value it received and
    appends new rows to the terminal stream until ``done`` is true.
    """
    import json as _json

    store = get_store()
    try:
        rec = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc

    log_path = store.base_dir / f"{run_id}.actions.jsonl"
    rows: List[Dict[str, Any]] = []
    new_cursor = max(0, int(cursor))
    limit = max(1, min(int(limit), 2000))
    if log_path.exists():
        with log_path.open("r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh):
                if idx < new_cursor:
                    continue
                if len(rows) >= limit:
                    break
                line = line.strip()
                if not line:
                    new_cursor = idx + 1
                    continue
                try:
                    rows.append(_json.loads(line))
                except _json.JSONDecodeError:
                    pass
                new_cursor = idx + 1

    done = rec.simulation_status in {"succeeded", "failed"}
    return ActionsResponse(
        run_id=run_id, cursor=new_cursor, rows=rows, done=done
    )


# === Chat (interaction) ===


class ChatMessageIn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessageIn] = []


class ChatResponse(BaseModel):
    run_id: str
    answer: str
    citations: List[str] = []
    confidence: str = "medium"
    out_of_scope: bool = False
    sections: List[Dict[str, Any]] = []


@router.post("/{run_id}/chat", response_model=ChatResponse)
def chat_report(run_id: str, body: ChatRequest) -> ChatResponse:
    """Grounded chat over the generated report markdown."""
    try:
        rec = get_store().get(run_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if rec.status != "succeeded" or not rec.result:
        raise HTTPException(409, f"Run not ready (status={rec.status})")

    report_md = (rec.result.get("report_markdown") or "").strip()
    if not report_md:
        raise HTTPException(409, "Report markdown unavailable for this run")

    history = [
        ChatMessage(role=("user" if m.role == "user" else "assistant"), content=m.content)
        for m in body.history
        if m.role in {"user", "assistant"} and (m.content or "").strip()
    ]
    try:
        answer = chat_with_report(
            report_markdown=report_md,
            brand=rec.brand,
            mode=rec.mode,
            question=body.question,
            history=history,
        )
    except ChatError as exc:
        raise HTTPException(503, f"chat failed: {exc}") from exc

    _, sections = index_report(report_md)
    return ChatResponse(
        run_id=run_id,
        answer=answer.answer,
        citations=answer.citations,
        confidence=answer.confidence,
        out_of_scope=answer.out_of_scope,
        sections=[
            {"sid": s.sid, "title": s.title, "level": s.level} for s in sections
        ],
    )


@router.post("/{run_id}/chat/stream")
def chat_report_stream(run_id: str, body: ChatRequest) -> StreamingResponse:
    """Server-Sent Events variant of /chat. Streams answer tokens then a
    final ``meta`` event with citations/confidence/out_of_scope/sections.
    """
    import json as _json

    try:
        rec = get_store().get(run_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if rec.status != "succeeded" or not rec.result:
        raise HTTPException(409, f"Run not ready (status={rec.status})")

    report_md = (rec.result.get("report_markdown") or "").strip()
    if not report_md:
        raise HTTPException(409, "Report markdown unavailable for this run")

    history = [
        ChatMessage(role=("user" if m.role == "user" else "assistant"), content=m.content)
        for m in body.history
        if m.role in {"user", "assistant"} and (m.content or "").strip()
    ]

    _, sections = index_report(report_md)
    sections_payload = [
        {"sid": s.sid, "title": s.title, "level": s.level} for s in sections
    ]

    def event_stream():
        try:
            for kind, value in chat_with_report_stream(
                report_markdown=report_md,
                brand=rec.brand,
                mode=rec.mode,
                question=body.question,
                history=history,
            ):
                if kind == "token":
                    yield f"event: token\ndata: {_json.dumps(value)}\n\n"
                elif kind == "meta":
                    payload = {
                        "answer": value.answer,
                        "citations": value.citations,
                        "confidence": value.confidence,
                        "out_of_scope": value.out_of_scope,
                        "sections": sections_payload,
                    }
                    yield f"event: meta\ndata: {_json.dumps(payload)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except ChatError as exc:
            yield f"event: error\ndata: {_json.dumps({'detail': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# === ReAct chat agent (tool-using) ===


class ChatAgentToolCall(BaseModel):
    name: str
    parameters: Dict[str, Any] = {}
    result_excerpt: str = ""
    error: Optional[str] = None


class ChatAgentResponse(BaseModel):
    run_id: str
    answer: str
    tool_calls: List[ChatAgentToolCall] = []
    sections: List[Dict[str, Any]] = []


@router.post("/{run_id}/chat/agent", response_model=ChatAgentResponse)
def chat_report_agent(run_id: str, body: ChatRequest) -> ChatAgentResponse:
    """ReAct chat with 6 tools (local + Zep + OASIS interview).

    Tools that depend on Zep credit / live OASIS env return a graceful
    "service unavailable" message; the agent will fall back to local tools.
    """
    store = get_store()
    try:
        rec = store.get(run_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if rec.status != "succeeded" or not rec.result:
        raise HTTPException(409, f"Run not ready (status={rec.status})")

    report_md = (rec.result.get("report_markdown") or "").strip()
    if not report_md:
        raise HTTPException(409, "Report markdown unavailable for this run")

    history = [
        ChatMessage(role=("user" if m.role == "user" else "assistant"), content=m.content)
        for m in body.history
        if m.role in {"user", "assistant"} and (m.content or "").strip()
    ]

    actions_log = store.base_dir / f"{run_id}.actions.jsonl"
    sim_block = (rec.result.get("simulation") or {})
    zep_block = sim_block.get("zep") or {}
    graph_id = zep_block.get("graph_id") if zep_block.get("status") == "ok" else None
    simulation_id = sim_block.get("simulation_id")
    scenario_brief = (rec.result.get("brand_seed") or {}).get(
        "scenario_brief"
    ) or ""

    try:
        answer = chat_agent_with_report(
            report_markdown=report_md,
            brand=rec.brand,
            mode=rec.mode,
            question=body.question,
            history=history,
            actions_log_path=actions_log if actions_log.exists() else None,
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=scenario_brief,
        )
    except ChatError as exc:
        raise HTTPException(503, f"chat agent failed: {exc}") from exc

    return ChatAgentResponse(
        run_id=run_id,
        answer=answer.answer,
        tool_calls=[ChatAgentToolCall(**tc.to_dict()) for tc in answer.tool_calls],
        sections=answer.sections,
    )


# === Background worker ===


def _run_pipeline_job(
    *,
    run_id: str,
    payload: bytes,
    filename: str,
    brand: str,
    source_type: SourceType,
    mode: PipelineMode,
    scenario_brief: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> None:
    """Runs inside FastAPI BackgroundTasks worker thread."""
    store = get_store()
    try:
        store.mark_running(run_id)

        def on_progress(step: str, **kw: Any) -> None:
            try:
                store.set_progress(run_id, step=step, **kw)
            except Exception:  # noqa: BLE001
                pass

        # Build LLM client honoring the user-selected model (if any). Falls
        # back to env default when llm_model is None or invalid.
        llm_client = None
        if llm_model:
            try:
                from app.llm import make_llm_client

                llm_client = make_llm_client(llm_model)
            except Exception as exc:  # noqa: BLE001
                # Don't fail the whole run on bad selection; log and continue.
                on_progress("llm_fallback", requested=llm_model, error=str(exc))

        pipeline = ReportPipeline(on_progress=on_progress, llm_client=llm_client)
        result = pipeline.run(
            source_bytes=payload,
            source_filename=filename,
            source_type=source_type,
            brand_hint=brand,
            mode=mode,
            enable_simulation=False,
            scenario_brief=scenario_brief,
        )
        store.mark_succeeded(run_id, result=result.to_dict())
    except Exception as exc:  # noqa: BLE001 — top-level safety net
        store.mark_failed(run_id, error=f"{type(exc).__name__}: {exc}")
