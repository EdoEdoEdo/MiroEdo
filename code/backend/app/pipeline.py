"""
ReportPipeline — orchestrate seed extraction + postprocess (and, in full
mode, OASIS simulation).

Modes:
- "quick": file → BrandSeed → baseline markdown → KPI + executive summary
  + action plan. No simulation, works on Python 3.9.
- "full": same as quick, but additionally runs OASIS simulation through
  the engine modules. Requires Python 3.11 (Docker image with
  requirements-simulation.txt installed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from app.ingestion.tabular_adapter import parse_csv as parse_tabular_csv
from app.ingestion.file_parser import parse_bytes, parse_file
from app.ingestion.text_seed_extractor import TextSeedExtractor
from app.ingestion.universal_adapter import ingest as universal_ingest
from app.llm.mistral import MistralClient
from app.llm.ontology import generate_ontology, ontology_to_graph_nodes
from app.postprocess.action_plan import generate_action_plan
from app.postprocess.baseline_report import render_baseline_report
from app.postprocess.drivers import generate_scenario_drivers
from app.postprocess.executive_summary import generate_executive_summary
from app.postprocess.forecast import forecast_volume
from app.postprocess.kpi_extractor import extract_kpi
from app.postprocess.scenarios import generate_scenarios
from app.postprocess.simulation_chapter import render_simulation_chapter
from app.schemas import (
    ActionPlan,
    BrandSeed,
    ExecutiveSummary,
    ReportKPI,
    ScenarioDriversSet,
    ScenarioSet,
    VolumeForecast,
)

PipelineMode = Literal["quick", "full"]
# Neutral source types. Legacy ``brandwatch_*`` values still accepted for
# back-compat with persisted runs; new code should emit ``tabular`` / ``document``.
SourceType = Literal[
    "tabular",
    "document",
    "manual",
    "brandwatch_csv",
    "brandwatch_pdf",
]


def _render_scenario_chapter(scenario_brief: str) -> str:
    """Render lo scenario business utente come capitolo iniziale del report.

    Viene così esposto sia ai chapter postprocess (executive summary, action
    plan) che ricevono già il markdown completo, sia alla chat RAG che indicizza
    le sezioni per `sid`.
    """
    cleaned = scenario_brief.strip()
    return (
        "## Scenario di business (input utente)\n\n"
        "> Questo blocco riassume la richiesta strategica formulata dall'utente "
        "al momento dell'upload. Non è un'evidenza dal dataset social ma il "
        "frame interpretativo per leggere il resto del report.\n\n"
        f"{cleaned}\n"
    )


def _render_summary_chapter(exec_summary: ExecutiveSummary) -> str:
    parts = ["## Executive summary", "", exec_summary.summary_it.strip()]
    highlights = getattr(exec_summary, "highlights", None) or []
    if highlights:
        parts.append("")
        parts.append("**Highlights**")
        for h in highlights:
            parts.append(f"- {h}")
    return "\n".join(parts) + "\n"


def _render_action_plan_chapter(plan: ActionPlan) -> str:
    actions = getattr(plan, "actions", None) or []
    horizon = getattr(plan, "horizon_hours", 72)
    parts = [f"## Piano d'azione ({horizon}h)", ""]
    if not actions:
        parts.append("_Nessuna azione generata._")
        return "\n".join(parts) + "\n"
    for a in actions:
        prio = getattr(a, "priority", "?")
        action = getattr(a, "action", "")
        owner = getattr(a, "owner", "")
        tf = getattr(a, "timeframe_h", "")
        kpi = getattr(a, "kpi_target", "")
        rationale = getattr(a, "rationale", "")
        targets = getattr(a, "targets_drivers", None) or []
        impact = getattr(a, "expected_impact", "") or ""
        parts.append(f"### {prio}. {action}")
        parts.append(f"- **Owner**: {owner} · **Timeframe**: {tf}h")
        if targets:
            parts.append("- **Driver indirizzati**: " + ", ".join(targets))
        if impact:
            parts.append(f"- **Impatto atteso**: {impact}")
        if kpi:
            parts.append(f"- **KPI target**: {kpi}")
        if rationale:
            parts.append(f"- _Rationale_: {rationale}")
        parts.append("")
    return "\n".join(parts) + "\n"


def _render_drivers_chapter(drivers: Optional[ScenarioDriversSet]) -> str:
    """Render dei driver osservati come capitolo prima del piano d'azione."""
    if not drivers or not drivers.drivers:
        return ""
    parts = ["## Driver osservati (bridge dati → azione)", ""]
    if drivers.scenario_focus:
        parts.append(f"_{drivers.scenario_focus}_")
        parts.append("")
    strength_glyph = {"high": "🔴", "medium": "🟡", "low": "⚪"}
    for d in drivers.drivers:
        glyph = strength_glyph.get(d.strength, "⚪")
        head_bits = [f"{glyph} **{d.label}**"]
        if d.evidence_topic:
            head_bits.append(
                f"topic _{d.evidence_topic}_ · {d.mentions} mention · sentiment {d.sentiment:+.2f}"
            )
        parts.append("### " + " — ".join(head_bits))
        if d.rationale:
            parts.append(d.rationale)
        for q in d.sample_quotes:
            parts.append(f"> {q}")
        parts.append("")
    if drivers.model:
        parts.append(f"_Generato da {drivers.model} (confidence {drivers.confidence:.2f})._")
    return "\n".join(parts) + "\n"


def _render_scenarios_chapter(scen: ScenarioSet) -> str:
    if not scen or not scen.scenarios:
        return ""
    parts = [f"## Scenari prospettici ({scen.horizon_weeks} settimane)", ""]
    label_map = {"best": "🟢 Best case", "base": "🟡 Base case", "worst": "🔴 Worst case"}
    for s in scen.scenarios:
        head = label_map.get(s.label, s.label)
        prob = f"{int(round(s.probability * 100))}%"
        parts.append(f"### {head} — {s.title} ({prob})")
        parts.append("")
        parts.append(s.narrative.strip())
        if s.drivers:
            parts.append("")
            parts.append("**Driver**: " + "; ".join(s.drivers))
        if s.early_signals:
            parts.append("**Early signals**: " + "; ".join(s.early_signals))
        parts.append("")
    if scen.model:
        parts.append(f"_Generato da {scen.model} (confidence {scen.confidence:.2f})._")
    return "\n".join(parts) + "\n"


def _render_forecast_chapter(fc: VolumeForecast) -> str:
    if not fc:
        return ""
    parts = [f"## Forecast volume mention ({fc.horizon_weeks} settimane)", ""]
    parts.append(f"_Metodo: `{fc.method}` · storico: {fc.history_weeks} settimane._")
    if fc.notes:
        parts.append("")
        parts.append(fc.notes)
    parts.append("")
    if fc.forecast:
        parts.append("| Settimana | Volume previsto | Range 95% CI |")
        parts.append("|---|---|---|")
        for p in fc.forecast:
            parts.append(
                f"| {p.date} | {p.yhat:.0f} | {p.yhat_lower:.0f} – {p.yhat_upper:.0f} |"
            )
    else:
        parts.append("_Nessun forecast disponibile._")
    return "\n".join(parts) + "\n"


def _render_ontology_chapter(ontology: Optional[Dict[str, Any]]) -> str:
    """Render an ontology section (LLM stakeholder mapping) into markdown."""
    if not ontology or ontology.get("status") != "ok":
        return ""
    ents = ontology.get("entity_types") or []
    edges = ontology.get("edge_types") or []
    if not ents:
        return ""
    parts = ["## Ontologia stakeholder (AI-inferred)", ""]
    summary = ontology.get("analysis_summary")
    if summary:
        parts.append(f"_{summary}_")
        parts.append("")
    parts.append("### Entità")
    parts.append("")
    for e in ents:
        examples = ", ".join(e.get("examples", [])[:3]) or "—"
        role = e.get("role_in_simulation") or ""
        parts.append(
            f"- **{e['name']}** — {e.get('description', '')} _Esempi: {examples}._"
            + (f" Ruolo: {role}" if role else "")
        )
    if edges:
        parts.append("")
        parts.append("### Relazioni")
        parts.append("")
        for ed in edges:
            pairs = ", ".join(
                f"{p['source']} → {p['target']}" for p in ed.get("source_targets", [])
            )
            parts.append(
                f"- **{ed['name']}** — {ed.get('description', '')} ({pairs})"
            )
    model = ontology.get("model")
    if model:
        parts.append("")
        parts.append(f"_Ontologia generata da {model}._")
    return "\n".join(parts) + "\n"


@dataclass
class PipelineResult:
    """Output bundle produced by `ReportPipeline.run`."""

    mode: PipelineMode
    brand_seed: BrandSeed
    report_markdown: str
    kpi: ReportKPI
    executive_summary: ExecutiveSummary
    action_plan: ActionPlan
    scenario_drivers: Optional[ScenarioDriversSet] = None
    scenarios: Optional[ScenarioSet] = None
    volume_forecast: Optional[VolumeForecast] = None
    simulation: Optional[Dict[str, Any]] = None  # populated in full mode
    ontology: Optional[Dict[str, Any]] = None  # LLM-generated stakeholder ontology
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "brand_seed": self.brand_seed.model_dump(mode="json"),
            "report_markdown": self.report_markdown,
            "kpi": self.kpi.model_dump(mode="json"),
            "executive_summary": self.executive_summary.model_dump(mode="json"),
            "action_plan": self.action_plan.model_dump(mode="json"),
            "scenario_drivers": (
                self.scenario_drivers.model_dump(mode="json") if self.scenario_drivers else None
            ),
            "scenarios": self.scenarios.model_dump(mode="json") if self.scenarios else None,
            "volume_forecast": self.volume_forecast.model_dump(mode="json") if self.volume_forecast else None,
            "simulation": self.simulation,
            "ontology": self.ontology,
            "warnings": self.warnings,
        }


class ReportPipeline:
    """Orchestrator. Stateless; safe to call concurrently."""

    def __init__(
        self,
        *,
        llm_client: Optional[MistralClient] = None,
        text_extractor: Optional[TextSeedExtractor] = None,
        on_progress: Optional[Any] = None,
    ) -> None:
        self._llm_client = llm_client
        self._text_extractor = text_extractor
        self._on_progress = on_progress  # callable(step: str, **kw) or None

    # === Public ===

    def run(
        self,
        *,
        source_path: Optional[Path | str] = None,
        source_bytes: Optional[bytes] = None,
        source_filename: Optional[str] = None,
        source_type: SourceType,
        brand_hint: Optional[str] = None,
        mode: PipelineMode = "quick",
        enable_simulation: bool = False,
        scenario_brief: Optional[str] = None,
        sim_profiles: Optional[int] = None,
        sim_rounds: Optional[int] = None,
    ) -> PipelineResult:
        """Execute the full pipeline and return a `PipelineResult`."""
        self._progress("ingest")
        seed = self._build_seed(
            source_path=source_path,
            source_bytes=source_bytes,
            source_filename=source_filename,
            source_type=source_type,
            brand_hint=brand_hint,
        )
        # Emit rich progress so the frontend can render "live" entity cards.
        self._progress(
            "ingest_done",
            ingest_preview={
                "brand": seed.brand,
                "total_mentions": seed.total_mentions,
                "overall_sentiment": seed.overall_sentiment,
                "window_days": seed.monitoring_window_days,
                "topics": [
                    {"name": t.name, "mentions": t.mentions, "sentiment": t.sentiment_score}
                    for t in seed.topics[:8]
                ],
                "platforms": [
                    {"name": p.name, "count": p.count, "share": p.share}
                    for p in seed.platforms[:6]
                ],
                "countries": [
                    {"name": c.name, "count": c.count, "share": c.share}
                    for c in seed.countries[:6]
                ],
                "segments_count": len(seed.segments),
                "graph_nodes": len(seed.knowledge_graph.get("nodes", [])),
                "graph_links": len(seed.knowledge_graph.get("links", [])),
                "sentiment_breakdown": seed.sentiment_breakdown.model_dump(),
            },
        )

        self._progress("baseline_report")
        report_md = render_baseline_report(seed)

        if scenario_brief and scenario_brief.strip():
            report_md = _render_scenario_chapter(scenario_brief) + "\n\n" + report_md

        warnings: list[str] = []
        simulation_result: Optional[Dict[str, Any]] = None

        # === Ontology generation (LLM-driven stakeholder mapping) ===
        self._progress("ontology")
        ontology = generate_ontology(
            brand=seed.brand,
            market=seed.market,
            language=seed.language,
            scenario_brief=scenario_brief,
            topics=seed.topics,
            segments=seed.segments,
            client=self._llm_client,
        )
        # If the dataset-derived knowledge_graph is empty (non-tabular source),
        # backfill it with the LLM-inferred ontology graph so the frontend
        # always has something to draw. Nodes are flagged `inferred: true`.
        if ontology.get("status") == "ok" and not seed.knowledge_graph.get("nodes"):
            inferred_nodes, inferred_links = ontology_to_graph_nodes(ontology, seed.brand)
            if inferred_nodes:
                seed.knowledge_graph = {
                    "nodes": inferred_nodes,
                    "links": inferred_links,
                    "stats": {
                        "node_count": len(inferred_nodes),
                        "link_count": len(inferred_links),
                        "node_types": sorted({n["type"] for n in inferred_nodes}),
                        "edge_types": sorted({l["type"] for l in inferred_links}),
                        "inferred": True,
                    },
                }

        # NOTE: simulation is no longer part of the base pipeline. It runs
        # on-demand via `POST /reports/{run_id}/simulation` (see api/reports.py)
        # so the report is delivered to the user in ~30s instead of ~8min.
        # `enable_simulation`, `sim_profiles`, `sim_rounds` kept for backward
        # compatibility but are ignored here.
        _ = (enable_simulation, sim_profiles, sim_rounds)

        self._progress("kpi")
        kpi = extract_kpi(report_md)

        client = self._llm_client  # may be None → postprocess will lazy-init or fallback

        self._progress("executive_summary")
        exec_summary = generate_executive_summary(
            report_md,
            brand=seed.brand,
            market=seed.market,
            client=client,
            scenario_brief=scenario_brief,
        )

        self._progress("scenario_drivers")
        scenario_drivers = generate_scenario_drivers(
            seed,
            scenario_brief=scenario_brief,
            client=client,
        )

        self._progress("action_plan")
        action_plan = generate_action_plan(
            report_md,
            brand=seed.brand,
            market=seed.market,
            client=client,
            scenario_brief=scenario_brief,
            drivers=scenario_drivers,
        )

        self._progress("scenarios")
        scenarios = generate_scenarios(
            seed,
            horizon_weeks=4,
            scenario_brief=scenario_brief,
            client=client,
        )

        self._progress("forecast")
        volume_forecast = forecast_volume(seed, horizon_weeks=4)

        # Append executive summary + action plan as final markdown chapters so
        # the downloadable .md mirrors the structured JSON output.
        report_md = (
            report_md
            + "\n" + _render_summary_chapter(exec_summary)
            + "\n" + _render_drivers_chapter(scenario_drivers)
            + "\n" + _render_action_plan_chapter(action_plan)
            + "\n" + _render_scenarios_chapter(scenarios)
            + "\n" + _render_forecast_chapter(volume_forecast)
            + "\n" + _render_ontology_chapter(ontology)
        )

        return PipelineResult(
            mode=mode,
            brand_seed=seed,
            report_markdown=report_md,
            kpi=kpi,
            executive_summary=exec_summary,
            action_plan=action_plan,
            scenario_drivers=scenario_drivers,
            scenarios=scenarios,
            volume_forecast=volume_forecast,
            simulation=simulation_result,
            ontology=ontology if ontology.get("status") == "ok" else None,
            warnings=warnings,
        )

    # === Internals ===

    def _build_seed(
        self,
        *,
        source_path: Optional[Path | str],
        source_bytes: Optional[bytes],
        source_filename: Optional[str],
        source_type: SourceType,
        brand_hint: Optional[str],
    ) -> BrandSeed:
        # Neutral entry point: tabular = CSV/XLSX, document = PDF/MD/TXT.
        if source_type in ("tabular", "document"):
            payload = source_bytes
            if payload is None and source_path is not None:
                payload = Path(source_path).read_bytes()
            if payload is None:
                raise ValueError("source requires source_path or source_bytes")
            filename = source_filename or (
                Path(source_path).name if source_path else (
                    "upload.xlsx" if source_type == "tabular" else "upload.txt"
                )
            )
            return universal_ingest(
                payload=payload,
                filename=filename,
                brand=brand_hint or "Brand",
                llm_client=self._llm_client,
                text_extractor=self._text_extractor,
            )

        # ---- legacy branches ----
        if source_type == "brandwatch_csv":
            csv_bytes = self._read_csv_bytes(
                source_path=source_path, source_bytes=source_bytes
            )
            return parse_tabular_csv(csv_bytes, brand=brand_hint or "Brand")

        if source_type == "brandwatch_pdf":
            text = self._read_text(
                source_path=source_path,
                source_bytes=source_bytes,
                source_filename=source_filename,
            )
            extractor = self._text_extractor or TextSeedExtractor(client=self._llm_client)
            return extractor.extract(text, brand_hint=brand_hint)

        if source_type == "manual":
            raise NotImplementedError("manual source not supported in pipeline (use API directly)")

        raise ValueError(f"Unknown source_type: {source_type!r}")

    @staticmethod
    def _read_csv_bytes(
        *, source_path: Optional[Path | str], source_bytes: Optional[bytes]
    ) -> bytes:
        if source_bytes is not None:
            return source_bytes
        if source_path is not None:
            return Path(source_path).read_bytes()
        raise ValueError("CSV source requires source_path or source_bytes")

    @staticmethod
    def _read_text(
        *,
        source_path: Optional[Path | str],
        source_bytes: Optional[bytes],
        source_filename: Optional[str],
    ) -> str:
        if source_bytes is not None:
            if not source_filename:
                raise ValueError("source_filename required when passing source_bytes")
            return parse_bytes(source_bytes, source_filename)
        if source_path is not None:
            return parse_file(source_path)
        raise ValueError("text source requires source_path or source_bytes")

    def simulate_only(
        self,
        seed: BrandSeed,
        *,
        sim_profiles: Optional[int] = None,
        sim_rounds: Optional[int] = None,
        oasis_model: Optional[str] = None,
        actions_log_path: Optional[Path] = None,
        scenario_brief: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, Any]], list[str]]:
        """Public wrapper around `_run_simulation` for on-demand sim launches.

        Used by the dedicated `POST /reports/{run_id}/simulation` endpoint to
        attach an OASIS simulation to a run whose base report is already done.
        """
        self._progress("simulation")
        return self._run_simulation(
            seed,
            sim_profiles=sim_profiles,
            sim_rounds=sim_rounds,
            oasis_model=oasis_model,
            actions_log_path=actions_log_path,
            scenario_brief=scenario_brief,
        )

    def _run_simulation(
        self,
        seed: BrandSeed,
        *,
        sim_profiles: Optional[int] = None,
        sim_rounds: Optional[int] = None,
        oasis_model: Optional[str] = None,
        actions_log_path: Optional[Path] = None,
        scenario_brief: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, Any]], list[str]]:
        """Run OASIS simulation. Requires OASIS deps + Python 3.11.

        ``sim_profiles`` controls how many synthetic consumer agents (default
        8, clamped 3..120). ``sim_rounds`` controls OASIS step rounds (default
        1, clamped 1..10). Exposed as a public helper via `simulate_only`.
        """
        self._progress("simulation_validating")
        try:
            import oasis  # noqa: F401
        except ImportError as exc:
            return None, [
                f"OASIS simulation unavailable in this runtime: {exc}. "
                "Run inside the Docker image (python:3.11-slim) to enable."
            ]

        try:
            from app.engine.config import EngineConfig
            from app.engine.profile.generator import OasisProfileGenerator
            from app.engine.seeds_to_entities import seed_to_entities
            from app.engine.simulation.oasis_runner import run_minimal_simulation
        except ImportError as exc:
            return None, [f"Engine modules not importable: {exc}"]

        import os
        import tempfile

        warnings: list[str] = []
        config = EngineConfig.from_env()
        if not config.llm_api_key:
            return None, ["LLM_API_KEY missing: cannot generate OASIS profiles"]

        # Clamp user-provided knobs to safe bounds. The upper limits protect
        # against runaway LLM cost during profile generation and OASIS steps.
        consumers = sim_profiles if sim_profiles and sim_profiles > 0 else 8
        consumers = max(3, min(int(consumers), 120))
        rounds = sim_rounds if sim_rounds and sim_rounds > 0 else 1
        rounds = max(1, min(int(rounds), 10))

        # 1. BrandSeed → EntityNodes (small synthetic graph)
        self._progress(
            "simulation_entities", requested_profiles=consumers, rounds=rounds
        )
        entities = seed_to_entities(seed, total_consumers=consumers, top_topics=3)

        # 2. Entities → Reddit profiles via LLM
        self._progress("simulation_profiles", entities_count=len(entities))
        generator = OasisProfileGenerator(config=config)
        profiles_obj = generator.generate_profiles_from_entities(
            entities=entities,
            output_platform="reddit",
            parallel_count=4,
        )
        profiles = [p.to_reddit_format() for p in profiles_obj]

        # 3. Seed posts: mix di provocazioni reali (quote dal dataset) e
        #    domande sui topic principali. L'obiettivo è dare agli agenti
        #    OASIS materiale concreto su cui reagire (like/comment/repost)
        #    invece di prompt generici tipo "cosa pensate di X?".
        self._progress("simulation_seed_posts", profiles_count=len(profiles))
        seed_posts: list[str] = []

        # 3a. Topic negativi/critici → usa una sample_quote come post
        #     provocatorio (parla come un utente arrabbiato).
        for topic in sorted(seed.topics, key=lambda t: t.sentiment_score)[:4]:
            quote = next((q.strip() for q in topic.sample_quotes if q.strip()), None)
            if quote and topic.sentiment_score < 0.3:
                seed_posts.append(f"{quote} #{topic.name.split()[0].lower()}")
            else:
                seed_posts.append(
                    f"Parliamo di {topic.name} per {seed.brand}: "
                    f"voi che ne pensate davvero? ({topic.mentions} menzioni)"
                )

        # 3b. Segmenti con sentiment negativo → quote del segmento come post
        for seg in seed.segments:
            if seg.sentiment_baseline in {"negative", "mixed"}:
                quote = next((q.strip() for q in seg.sample_quotes if q.strip()), None)
                if quote:
                    seed_posts.append(quote)
            if len(seed_posts) >= 8:
                break

        # 3c. Fallback se non ci sono né topic né segmenti
        if not seed_posts:
            seed_posts = [f"Opinioni su {seed.brand}?"]

        seed_posts = seed_posts[:8]

        # 4. Run minimal simulation
        enable_llm = (
            os.environ.get("MIROEDO_OASIS_LLM_REACTIONS", "false").lower()
            in {"1", "true", "yes"}
        )
        try:
            sample_rate = float(
                os.environ.get("MIROEDO_OASIS_LLM_SAMPLE", "0.3")
            )
        except ValueError:
            sample_rate = 0.3
        try:
            max_calls = int(os.environ.get("MIROEDO_OASIS_LLM_MAX_CALLS", "100"))
        except ValueError:
            max_calls = 100
        sim_workspace = Path(tempfile.mkdtemp(prefix="miroedo_oasis_"))
        self._progress(
            "simulation_oasis",
            profiles_count=len(profiles),
            seed_posts_count=len(seed_posts),
            rounds=rounds,
            llm_reactions=enable_llm,
        )
        summary = run_minimal_simulation(
            profiles=profiles,
            seed_posts=seed_posts,
            workspace_dir=sim_workspace,
            rounds=rounds,
            enable_llm_reactions=enable_llm,
            openai_model=oasis_model
            or os.environ.get("MIROEDO_OASIS_MODEL", "gpt-4o-mini"),
            llm_sample_rate=sample_rate,
            llm_max_calls=max_calls,
            actions_log_path=actions_log_path,
        )
        warnings.extend(summary.notes)

        # 5. Optional Zep enrichment (best-effort; never blocks)
        from app.engine.zep.enrichment import maybe_enrich_with_zep
        from app.engine.zep.qa import generate_zep_qa

        self._progress("simulation_zep")
        zep_result = maybe_enrich_with_zep(seed)
        if zep_result["status"] in {"unavailable", "error"}:
            warnings.append(f"Zep enrichment {zep_result['status']}: {zep_result['reason']}")

        # 5b. Brand Q&A on Zep graph (only if enrichment succeeded)
        self._progress("simulation_zep_qa")
        qa_result = generate_zep_qa(
            seed=seed,
            zep_result=zep_result,
            scenario_brief=scenario_brief,
            client=self._llm_client,
        )
        if qa_result.get("status") == "error":
            warnings.append(f"Zep Q&A error: {qa_result.get('reason')}")

        result = summary.to_dict()
        result["zep"] = zep_result
        result["zep_qa"] = qa_result
        # Expose a compact profiles preview so the frontend can render
        # PersonaCards during the live replay. Cap at 16 to keep payload small.
        result["profiles_preview"] = [
            {
                "user_id": p.get("user_id"),
                "username": p.get("username"),
                "name": p.get("name"),
                "age": p.get("age"),
                "country": p.get("country"),
                "profession": p.get("profession"),
                "bio": (p.get("bio") or "")[:160],
                "interested_topics": (p.get("interested_topics") or [])[:5],
            }
            for p in profiles[:16]
        ]
        self._progress(
            "simulation_done",
            profiles_count=result.get("profiles_count"),
            total_actions=result.get("total_actions"),
        )
        return result, warnings

    def _progress(self, step: str, **kw: Any) -> None:
        if self._on_progress is None:
            return
        try:
            self._on_progress(step, **kw)
        except Exception:  # pragma: no cover — progress reporting must never break the pipeline
            pass
