"""FastAPI entrypoint per MiroEdo backend."""

from __future__ import annotations

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.reports import router as reports_router
from app.ingestion.tabular_adapter import parse_csv
from app.postprocess.action_plan import generate_action_plan
from app.postprocess.executive_summary import generate_executive_summary
from app.postprocess.kpi_extractor import extract_kpi
from app.schemas import ActionPlan, BrandSeed, ExecutiveSummary, ReportKPI

app = FastAPI(
    title="MiroEdo Backend",
    version="0.1.0",
    description="Brandwatch ingestion + MiroFish postprocess",
)

# CORS for local Next.js frontend (override with MIROEDO_CORS_ORIGINS env, comma-separated)
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_origins = [o.strip() for o in os.environ.get("MIROEDO_CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports_router)


@app.get("/llm/models")
def list_llm_models() -> dict:
    """Return the catalog of LLM models known to the backend.

    Each entry has `available=True` only if the corresponding API key env var
    is set; the frontend should disable unavailable entries.
    """
    from app.llm import list_available_models

    return {"models": list_available_models()}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "miroedo-backend", "version": "0.1.0"}


@app.post("/ingest/brandwatch-csv", response_model=BrandSeed)
async def ingest_brandwatch_csv(
    file: UploadFile = File(..., description="Export Brandwatch (Mentions CSV)"),
    brand: str = Form(..., description="Nome del brand, es. 'Mulino Bianco'"),
    market: str = Form("IT"),
    language: str = Form("it"),
) -> BrandSeed:
    """Parse di un export CSV Brandwatch in un BrandSeed pronto per MiroFish."""
    raw = await file.read()
    try:
        return parse_csv(raw, brand=brand, market=market, language=language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class PostprocessRequest(BaseModel):
    report_markdown: str
    brand: str = "Brand"
    market: str = "IT"
    horizon_hours: int = 72


class PostprocessResponse(BaseModel):
    kpi: ReportKPI
    executive_summary: ExecutiveSummary
    action_plan: ActionPlan


@app.post("/postprocess/kpi", response_model=ReportKPI)
def postprocess_kpi(req: PostprocessRequest) -> ReportKPI:
    """Estrae KPI quantitativi (no LLM, deterministico)."""
    return extract_kpi(req.report_markdown)


@app.post("/postprocess/executive-summary", response_model=ExecutiveSummary)
def postprocess_executive_summary(req: PostprocessRequest) -> ExecutiveSummary:
    """Genera solo l'Executive Summary IT (LLM)."""
    return generate_executive_summary(
        req.report_markdown, brand=req.brand, market=req.market
    )


@app.post("/postprocess/action-plan", response_model=ActionPlan)
def postprocess_action_plan(req: PostprocessRequest) -> ActionPlan:
    """Genera solo l'Action Plan 72h (LLM)."""
    return generate_action_plan(
        req.report_markdown,
        brand=req.brand,
        market=req.market,
        horizon_hours=req.horizon_hours,
    )


@app.post("/postprocess/full", response_model=PostprocessResponse)
def postprocess_full(req: PostprocessRequest) -> PostprocessResponse:
    """Pipeline completa: KPI (deterministico) + Executive Summary + Action Plan (LLM)."""
    return PostprocessResponse(
        kpi=extract_kpi(req.report_markdown),
        executive_summary=generate_executive_summary(
            req.report_markdown, brand=req.brand, market=req.market
        ),
        action_plan=generate_action_plan(
            req.report_markdown,
            brand=req.brand,
            market=req.market,
            horizon_hours=req.horizon_hours,
        ),
    )
