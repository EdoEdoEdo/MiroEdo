"""Pydantic models per MiroEdo: Seed, Report, KPI."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# === Seed format (input al motore MiroFish) ===
# Allineato a docs/05-seed-format.md


class Segment(BaseModel):
    """Audience segment con peso e attributi descrittivi."""

    name: str
    weight: float = Field(ge=0.0, le=1.0, description="Quota relativa, somma=1 fra tutti")
    description: str
    sentiment_baseline: Literal["positive", "neutral", "negative", "mixed"] = "mixed"
    sample_quotes: list[str] = Field(default_factory=list)


class Topic(BaseModel):
    """Tema di conversazione con volume e share-of-voice."""

    name: str
    mentions: int = Field(ge=0)
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="-1=neg, +1=pos")
    sample_quotes: list[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """Evento sulla timeline storica del topic monitorato."""

    date: str  # ISO YYYY-MM-DD
    label: str
    mentions: int = Field(ge=0)
    note: str = ""


class SentimentBreakdown(BaseModel):
    """Conteggi e share per polarità."""

    positive: int = 0
    neutral: int = 0
    negative: int = 0
    mixed: int = 0

    @property
    def total(self) -> int:
        return self.positive + self.neutral + self.negative + self.mixed


class GroupStat(BaseModel):
    """Stat aggregata per platform/country/domain."""

    name: str
    count: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0, default=0.0)
    sentiment: float = Field(ge=-1.0, le=1.0, default=0.0)


class BrandSeed(BaseModel):
    """
    Seed JSON che alimenta la pipeline.

    Generato dall'universal adapter (CSV/XLSX → tabular, PDF/MD/TXT → document).
    Etichette legacy ``brandwatch_*`` accettate per compatibilità con run salvati.
    """

    brand: str
    market: str = "IT"
    language: str = "it"
    monitoring_window_days: int = Field(ge=1, le=365)
    total_mentions: int = Field(ge=0)
    overall_sentiment: float = Field(ge=-1.0, le=1.0)
    segments: list[Segment]
    topics: list[Topic]
    timeline: list[TimelineEvent] = Field(default_factory=list)
    volume_series_weekly: list[TimelineEvent] = Field(
        default_factory=list,
        description=(
            "Serie temporale settimanale autoritativa per il forecast volumi. "
            "Quando popolata (tipicamente da tabella esplicita nel documento), "
            "viene preferita a `timeline` dal forecaster. Ogni elemento ha "
            "date=lunedì ISO della settimana e mentions=volume aggregato."
        ),
    )
    sentiment_breakdown: SentimentBreakdown = Field(default_factory=SentimentBreakdown)
    platforms: list[GroupStat] = Field(default_factory=list)
    countries: list[GroupStat] = Field(default_factory=list)
    knowledge_graph: dict = Field(
        default_factory=dict,
        description="Brand-centric graph {nodes:[], links:[], stats:{}} per visualizzazione",
    )
    source: Literal[
        "tabular",
        "document",
        "manual",
        "brandwatch_csv",
        "brandwatch_pdf",
        "brandwatch_api",
    ] = "tabular"
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# === KPI Extraction (output postprocess) ===


class SegmentKPI(BaseModel):
    name: str
    mention_count: int | None = None
    sentiment_pct_positive: float | None = None
    sentiment_pct_negative: float | None = None


class TimeframePrediction(BaseModel):
    """Predizione con orizzonte temporale esplicito."""

    timeframe: str  # es. "48h", "1-2 weeks"
    text: str


class ReportKPI(BaseModel):
    """KPI quantitativi estratti da un report MiroFish markdown."""

    # Numeri raw trovati nel testo (regex)
    percentages_found: list[dict] = Field(
        default_factory=list,
        description="Ogni dict: {value: float, context: str (frase circostante)}",
    )
    timeframes_found: list[TimeframePrediction] = Field(default_factory=list)
    segments_mentioned: list[str] = Field(default_factory=list)

    # Conteggi strutturali
    chapter_count: int = 0
    predictive_conclusion_count: int = 0
    blockquote_count: int = 0
    word_count: int = 0

    # Score sintetici (0-100) — da raffinare in Fase B con LLM
    quantitative_density_score: int = Field(
        ge=0, le=100, default=0, description="% paragrafi con numeri concreti"
    )


# === Postprocess LLM output (Fase B) ===


class ExecutiveSummary(BaseModel):
    """Riassunto esecutivo IT (≤200 parole) + key findings."""

    summary_it: str = Field(description="Riassunto in italiano, business tone, ≤200 parole")
    key_findings: list[str] = Field(
        default_factory=list, description="3-5 bullet sintetici"
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.6)
    model: str = ""


class Action(BaseModel):
    """Singola azione operativa nel piano 72h."""

    priority: int = Field(ge=1, le=5, description="1=critica, 5=opzionale")
    action: str
    owner: Literal[
        "Brand Manager", "Marketing", "PR", "Customer Care", "Insight", "Legal"
    ] = "Brand Manager"
    timeframe_h: int = Field(ge=1, le=720, default=72)
    rationale: str
    kpi_target: str = ""
    targets_drivers: list[str] = Field(
        default_factory=list,
        description="Etichette dei ScenarioDriver indirizzati da questa azione",
    )
    expected_impact: str = Field(
        default="",
        description="Impatto atteso sui driver indirizzati, in 1 frase",
    )


class ActionPlan(BaseModel):
    actions: list[Action]
    horizon_hours: int = 72
    model: str = ""


# === Scenario drivers (Fase D — bridge dati → azione) ===


class ScenarioDriver(BaseModel):
    """Driver osservato nel corpus che può spiegare lo scenario richiesto.

    Inferito dall'LLM combinando il BrandSeed (topic + sentiment + quote) con
    lo ``scenario_brief`` utente. Pensato per fare da ponte tra evidenze
    quantitative (numeri/quote) e raccomandazioni operative.
    """

    label: str = Field(description="Nome breve del driver, es. 'Rincaro tariffe percepito'")
    evidence_topic: str = Field(
        default="",
        description="Topic del BrandSeed che fa da evidenza primaria, se applicabile",
    )
    mentions: int = Field(ge=0, default=0)
    sentiment: float = Field(ge=-1.0, le=1.0, default=0.0)
    strength: Literal["high", "medium", "low"] = "medium"
    rationale: str = Field(
        default="",
        description="Perché questo driver è rilevante per lo scenario richiesto, 1-2 frasi",
    )
    sample_quotes: list[str] = Field(
        default_factory=list,
        description="1-3 quote testuali dal corpus che esemplificano il driver",
    )


class ScenarioDriversSet(BaseModel):
    """Output strutturato dell'estrazione driver scenario-driven."""

    scenario_focus: str = Field(
        default="",
        description="Sintesi 1 frase di cosa il driver-set sta indirizzando",
    )
    drivers: list[ScenarioDriver] = Field(default_factory=list)
    model: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    notes: str = ""


# === Scenarios + Forecast (Fase C) ===


class Scenario(BaseModel):
    """Singolo scenario prospettico (best / base / worst)."""

    label: Literal["best", "base", "worst"]
    title: str = Field(description="Titolo breve dello scenario (≤80 char)")
    narrative: str = Field(description="Narrativa qualitativa dello scenario, 80-200 parole")
    probability: float = Field(ge=0.0, le=1.0, description="Probabilità soggettiva LLM")
    drivers: list[str] = Field(
        default_factory=list,
        description="3-5 fattori che spingono verso questo scenario",
    )
    early_signals: list[str] = Field(
        default_factory=list,
        description="2-4 segnali misurabili da monitorare nelle prossime 2-4 settimane",
    )


class ScenarioSet(BaseModel):
    """Tre scenari prospettici prodotti dall'LLM su scenario_brief + dati reali."""

    horizon_weeks: int = Field(ge=1, le=52, default=4)
    scenarios: list[Scenario] = Field(default_factory=list)
    model: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ForecastPoint(BaseModel):
    """Punto previsto della time series volume mention."""

    date: str  # ISO YYYY-MM-DD (inizio settimana)
    yhat: float = Field(description="Volume previsto")
    yhat_lower: float = Field(description="Lower bound 95% CI")
    yhat_upper: float = Field(description="Upper bound 95% CI")


class VolumeForecast(BaseModel):
    """Forecast statistico volume mention basato su time series storica."""

    method: Literal["holt_winters", "linear_trend", "naive_mean", "insufficient_data"] = "naive_mean"
    history_weeks: int = 0
    horizon_weeks: int = 4
    historical: list[ForecastPoint] = Field(default_factory=list)
    forecast: list[ForecastPoint] = Field(default_factory=list)
    notes: str = ""
