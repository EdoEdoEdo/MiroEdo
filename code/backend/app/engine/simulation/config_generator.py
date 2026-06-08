"""
Simulation Configuration Generator.

Adapted from MiroFish `app/services/simulation_config_generator.py`. Generates
time/event/agent/platform configs for an OASIS simulation, in steps to keep
LLM responses small.

Changes vs original:
- Takes `EngineConfig` instead of global `Config`
- Default timezone profile is generic (configurable) instead of China-only
- All prompts translated to English; `get_language_instruction()` injected
- `EntityNode` imported from `app.engine.types`
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from app.engine.config import EngineConfig
from app.engine.types import EntityNode
from app.engine.utils.locale import get_language_instruction
from app.engine.utils.logger import get_logger

logger = get_logger("miroedo.engine.simulation_config")


# ============================================================
# Data classes
# ============================================================


@dataclass
class AgentActivityConfig:
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str

    activity_level: float = 0.5
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    response_delay_min: int = 5
    response_delay_max: int = 60
    sentiment_bias: float = 0.0
    stance: str = "neutral"  # supportive | opposing | neutral | observer
    influence_weight: float = 1.0


@dataclass
class TimeSimulationConfig:
    total_simulation_hours: int = 72
    minutes_per_round: int = 60
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20

    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5

    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05

    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4

    work_hours: List[int] = field(default_factory=lambda: list(range(9, 19)))
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    hot_topics: List[str] = field(default_factory=list)
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    platform: str  # twitter | reddit
    recency_weight: float = 0.4
    popularity_weight: float = 0.3
    relevance_weight: float = 0.3
    viral_threshold: int = 10
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str

    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    event_config: EventConfig = field(default_factory=EventConfig)

    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None

    llm_model: str = ""
    llm_base_url: str = ""

    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": asdict(self.time_config),
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================
# Generator
# ============================================================


class SimulationConfigGenerator:
    """Multi-step LLM-driven config generator for OASIS simulations.

    Steps:
        1. time config
        2. event config (hot topics, initial posts, narrative)
        3. agent configs in batches (default 15)
        4. platform configs (twitter/reddit)
    """

    MAX_CONTEXT_LENGTH = 50_000
    AGENTS_PER_BATCH = 15

    TIME_CONFIG_CONTEXT_LENGTH = 10_000
    EVENT_CONFIG_CONTEXT_LENGTH = 8_000
    ENTITY_SUMMARY_LENGTH = 300
    AGENT_SUMMARY_LENGTH = 300
    ENTITIES_PER_TYPE_DISPLAY = 20

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        if not config.llm_api_key:
            raise ValueError("EngineConfig.llm_api_key is required")
        self.client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
        self.model_name = config.llm_model
        self.base_url = config.llm_base_url

    # ----- public API ---------------------------------------------------

    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        logger.info(
            f"Generating simulation config: id={simulation_id}, entities={len(entities)}"
        )

        num_batches = max(1, math.ceil(len(entities) / self.AGENTS_PER_BATCH))
        total_steps = 3 + num_batches

        def report(step: int, msg: str) -> None:
            if progress_callback:
                progress_callback(step, total_steps, msg)
            logger.info(f"[{step}/{total_steps}] {msg}")

        context = self._build_context(simulation_requirement, document_text, entities)
        reasoning_parts: List[str] = []

        # Step 1 — time
        report(1, "Generating time config")
        time_result = self._generate_time_config(context, len(entities))
        time_config = self._parse_time_config(time_result, len(entities))
        reasoning_parts.append(f"time: {time_result.get('reasoning', 'ok')}")

        # Step 2 — event
        report(2, "Generating event config")
        event_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_result)
        reasoning_parts.append(f"event: {event_result.get('reasoning', 'ok')}")

        # Steps 3..N — agents (batched)
        all_agent_configs: List[AgentActivityConfig] = []
        for batch_idx in range(num_batches):
            start = batch_idx * self.AGENTS_PER_BATCH
            end = min(start + self.AGENTS_PER_BATCH, len(entities))
            report(3 + batch_idx, f"Generating agents {start + 1}-{end} / {len(entities)}")
            batch = self._generate_agent_configs_batch(
                context, entities[start:end], start, simulation_requirement
            )
            all_agent_configs.extend(batch)
        reasoning_parts.append(f"agents: {len(all_agent_configs)} generated")

        # Assign initial post authors
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"posts: {assigned} assigned")

        # Final step — platforms
        report(total_steps, "Generating platform configs")
        twitter_cfg = PlatformConfig(platform="twitter") if enable_twitter else None
        reddit_cfg = (
            PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6,
            )
            if enable_reddit
            else None
        )

        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_cfg,
            reddit_config=reddit_cfg,
            llm_model=self.model_name,
            llm_base_url=self.base_url or "",
            generation_reasoning=" | ".join(reasoning_parts),
        )
        logger.info(f"Simulation config done: {len(params.agent_configs)} agents")
        return params

    # ----- context ------------------------------------------------------

    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
    ) -> str:
        entity_summary = self._summarize_entities(entities)
        parts = [
            f"## Simulation requirement\n{simulation_requirement}",
            f"\n## Entities ({len(entities)})\n{entity_summary}",
        ]
        used = sum(len(p) for p in parts)
        remaining = self.MAX_CONTEXT_LENGTH - used - 500
        if remaining > 0 and document_text:
            doc = document_text[:remaining]
            if len(document_text) > remaining:
                doc += "\n...(document truncated)"
            parts.append(f"\n## Source document\n{doc}")
        return "\n".join(parts)

    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            by_type.setdefault(t, []).append(e)

        lines: List[str] = []
        for entity_type, items in by_type.items():
            lines.append(f"\n### {entity_type} ({len(items)})")
            for e in items[: self.ENTITIES_PER_TYPE_DISPLAY]:
                summary = (
                    (e.summary[: self.ENTITY_SUMMARY_LENGTH] + "...")
                    if len(e.summary) > self.ENTITY_SUMMARY_LENGTH
                    else e.summary
                )
                lines.append(f"- {e.name}: {summary}")
            if len(items) > self.ENTITIES_PER_TYPE_DISPLAY:
                lines.append(f"  ... {len(items) - self.ENTITIES_PER_TYPE_DISPLAY} more")
        return "\n".join(lines)

    # ----- LLM call helpers --------------------------------------------

    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),
                )
                content = resp.choices[0].message.content or ""
                if resp.choices[0].finish_reason == "length":
                    logger.warning(f"LLM truncated (attempt {attempt + 1})")
                    content = self._fix_truncated_json(content)
                try:
                    return json.loads(content)
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON parse failed (attempt {attempt + 1}): {str(je)[:80]}")
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    last_error = je
            except Exception as exc:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {str(exc)[:80]}")
                last_error = exc
                time.sleep(2 * (attempt + 1))
        raise last_error or RuntimeError("LLM call failed")

    @staticmethod
    def _fix_truncated_json(content: str) -> str:
        content = content.strip()
        open_braces = content.count("{") - content.count("}")
        open_brackets = content.count("[") - content.count("]")
        if content and content[-1] not in '",}]':
            content += '"'
        return content + ("]" * open_brackets) + ("}" * open_braces)

    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        content = self._fix_truncated_json(content)
        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            return None
        json_str = m.group()
        json_str = re.sub(
            r'"[^"\\]*(?:\\.[^"\\]*)*"',
            lambda mm: re.sub(r"\s+", " ", mm.group(0).replace("\n", " ").replace("\r", " ")),
            json_str,
        )
        try:
            return json.loads(json_str)
        except Exception:
            try:
                json_str = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", json_str)
                json_str = re.sub(r"\s+", " ", json_str)
                return json.loads(json_str)
            except Exception:
                return None

    # ----- time ---------------------------------------------------------

    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        ctx = context[: self.TIME_CONFIG_CONTEXT_LENGTH]
        max_agents = max(1, int(num_entities * 0.9))
        prompt = f"""Based on the simulation context, produce a time configuration.

{ctx}

Reference activity heuristics (adapt to the audience implied by the context):
- 00:00-05:00: almost no activity (multiplier ~0.05)
- 06:00-08:00: ramp-up (~0.4)
- 09:00-18:00: working hours, medium (~0.7)
- 19:00-22:00: evening peak (~1.5)
- 23:00: cooldown (~0.5)

Return JSON only (no markdown):
{{
    "total_simulation_hours": <int 24-168>,
    "minutes_per_round": <int 30-120, default 60>,
    "agents_per_hour_min": <int 1-{max_agents}>,
    "agents_per_hour_max": <int 1-{max_agents}>,
    "peak_hours": [<ints 0-23>],
    "off_peak_hours": [<ints 0-23>],
    "morning_hours": [<ints 0-23>],
    "work_hours": [<ints 0-23>],
    "reasoning": "<why these choices>"
}}"""
        system = (
            "You are a social-media simulation expert. Return strictly valid JSON. "
            "Match the audience's daily rhythm.\n\n" + get_language_instruction()
        )
        try:
            return self._call_llm_with_retry(prompt, system)
        except Exception as exc:
            logger.warning(f"Time config LLM failed: {exc}, using defaults")
            return self._default_time_config(num_entities)

    @staticmethod
    def _default_time_config(num_entities: int) -> Dict[str, Any]:
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": list(range(9, 19)),
            "reasoning": "default profile",
        }

    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        a_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        a_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        if a_min > num_entities:
            logger.warning(f"agents_per_hour_min {a_min} > total {num_entities}; corrected")
            a_min = max(1, num_entities // 10)
        if a_max > num_entities:
            logger.warning(f"agents_per_hour_max {a_max} > total {num_entities}; corrected")
            a_max = max(a_min + 1, num_entities // 2)
        if a_min >= a_max:
            a_min = max(1, a_max // 2)
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),
            agents_per_hour_min=a_min,
            agents_per_hour_max=a_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            work_hours=result.get("work_hours", list(range(9, 19))),
        )

    # ----- event --------------------------------------------------------

    def _generate_event_config(
        self,
        context: str,
        simulation_requirement: str,
        entities: List[EntityNode],
    ) -> Dict[str, Any]:
        type_examples: Dict[str, List[str]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in type_examples:
                type_examples[t] = []
            if len(type_examples[t]) < 3:
                type_examples[t].append(e.name)
        type_info = "\n".join(f"- {t}: {', '.join(v)}" for t, v in type_examples.items())

        ctx = context[: self.EVENT_CONFIG_CONTEXT_LENGTH]
        prompt = f"""Based on the simulation requirement, produce an event configuration.

Simulation requirement: {simulation_requirement}

{ctx}

## Available entity types and examples
{type_info}

Task:
- Extract hot-topic keywords
- Describe the narrative direction
- Design initial posts; each MUST set `poster_type` to one of the entity types above

Return JSON only (no markdown):
{{
    "hot_topics": [<strings>],
    "narrative_direction": "<string>",
    "initial_posts": [
        {{"content": "...", "poster_type": "<entity type exactly as above>"}}
    ],
    "reasoning": "<brief>"
}}"""
        system = (
            "You are an opinion-dynamics analyst. Return strictly valid JSON. "
            "`poster_type` MUST match the available entity types exactly.\n\n"
            + get_language_instruction()
            + "\nIMPORTANT: `poster_type` values MUST be in English PascalCase matching "
            "the available types. Only `content`, `narrative_direction`, `hot_topics` "
            "and `reasoning` use the specified language."
        )
        try:
            return self._call_llm_with_retry(prompt, system)
        except Exception as exc:
            logger.warning(f"Event config LLM failed: {exc}, using defaults")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "defaults",
            }

    @staticmethod
    def _parse_event_config(result: Dict[str, Any]) -> EventConfig:
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", ""),
        )

    @staticmethod
    def _assign_initial_post_agents(
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig],
    ) -> EventConfig:
        if not event_config.initial_posts:
            return event_config

        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for a in agent_configs:
            agents_by_type.setdefault(a.entity_type.lower(), []).append(a)

        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
            "brand": ["brand", "company", "organization"],
            "consumer": ["consumer", "person"],
            "competitor": ["competitor", "brand", "company"],
        }

        used: Dict[str, int] = {}
        updated: List[Dict[str, Any]] = []

        for post in event_config.initial_posts:
            poster_type = (post.get("poster_type") or "").lower()
            matched: Optional[int] = None

            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used.get(poster_type, 0) % len(agents)
                matched = agents[idx].agent_id
                used[poster_type] = idx + 1
            else:
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used.get(alias, 0) % len(agents)
                                matched = agents[idx].agent_id
                                used[alias] = idx + 1
                                break
                    if matched is not None:
                        break

            if matched is None and agent_configs:
                matched = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)[0].agent_id
            elif matched is None:
                matched = 0

            updated.append(
                {
                    "content": post.get("content", ""),
                    "poster_type": post.get("poster_type", "Unknown"),
                    "poster_agent_id": matched,
                }
            )
            logger.info(f"Initial post assigned: poster_type={poster_type!r} → agent_id={matched}")

        event_config.initial_posts = updated
        return event_config

    # ----- agents -------------------------------------------------------

    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str,
    ) -> List[AgentActivityConfig]:
        entity_list = []
        for i, e in enumerate(entities):
            entity_list.append(
                {
                    "agent_id": start_idx + i,
                    "entity_name": e.name,
                    "entity_type": e.get_entity_type() or "Unknown",
                    "summary": e.summary[: self.AGENT_SUMMARY_LENGTH] if e.summary else "",
                }
            )

        prompt = f"""Generate social-media activity configs for each entity.

Simulation requirement: {simulation_requirement}

## Entities
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

Heuristics (adapt to the audience implied by context):
- Institutions (University/GovernmentAgency): low activity (0.1-0.3), working hours, slow response (60-240 min), high influence (2.5-3.0)
- Media (MediaOutlet): medium activity (0.4-0.6), all-day (8-23), fast response (5-30 min), high influence (2.0-2.5)
- Individuals (Student/Person/Alumni/Consumer): high activity (0.6-0.9), mainly evening (18-23), fast response (1-15 min), low influence (0.8-1.2)
- Public figures/experts: medium activity (0.4-0.6), medium-high influence (1.5-2.0)

Return JSON only (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <same as input>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <float>,
            "comments_per_hour": <float>,
            "active_hours": [<ints 0-23>],
            "response_delay_min": <int>,
            "response_delay_max": <int>,
            "sentiment_bias": <-1.0..1.0>,
            "stance": "supportive|opposing|neutral|observer",
            "influence_weight": <float>
        }}
    ]
}}"""
        system = (
            "You are a social-media behaviour expert. Return strictly valid JSON.\n\n"
            + get_language_instruction()
            + "\nIMPORTANT: `stance` MUST be one of: 'supportive', 'opposing', 'neutral', "
            "'observer'. JSON field names and numeric values must remain unchanged."
        )

        try:
            result = self._call_llm_with_retry(prompt, system)
            llm_cfgs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as exc:
            logger.warning(f"Agent batch LLM failed: {exc}, using rule-based")
            llm_cfgs = {}

        out: List[AgentActivityConfig] = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_cfgs.get(agent_id) or self._rule_based_agent_config(entity)
            out.append(
                AgentActivityConfig(
                    agent_id=agent_id,
                    entity_uuid=entity.uuid,
                    entity_name=entity.name,
                    entity_type=entity.get_entity_type() or "Unknown",
                    activity_level=cfg.get("activity_level", 0.5),
                    posts_per_hour=cfg.get("posts_per_hour", 0.5),
                    comments_per_hour=cfg.get("comments_per_hour", 1.0),
                    active_hours=cfg.get("active_hours", list(range(9, 23))),
                    response_delay_min=cfg.get("response_delay_min", 5),
                    response_delay_max=cfg.get("response_delay_max", 60),
                    sentiment_bias=cfg.get("sentiment_bias", 0.0),
                    stance=cfg.get("stance", "neutral"),
                    influence_weight=cfg.get("influence_weight", 1.0),
                )
            )
        return out

    @staticmethod
    def _rule_based_agent_config(entity: EntityNode) -> Dict[str, Any]:
        t = (entity.get_entity_type() or "Unknown").lower()
        if t in ("university", "governmentagency", "ngo", "organization"):
            return dict(
                activity_level=0.2, posts_per_hour=0.1, comments_per_hour=0.05,
                active_hours=list(range(9, 18)),
                response_delay_min=60, response_delay_max=240,
                sentiment_bias=0.0, stance="neutral", influence_weight=3.0,
            )
        if t in ("mediaoutlet", "media"):
            return dict(
                activity_level=0.5, posts_per_hour=0.8, comments_per_hour=0.3,
                active_hours=list(range(7, 24)),
                response_delay_min=5, response_delay_max=30,
                sentiment_bias=0.0, stance="observer", influence_weight=2.5,
            )
        if t in ("professor", "expert", "official", "influencer", "publicfigure"):
            return dict(
                activity_level=0.4, posts_per_hour=0.3, comments_per_hour=0.5,
                active_hours=list(range(8, 22)),
                response_delay_min=15, response_delay_max=90,
                sentiment_bias=0.0, stance="neutral", influence_weight=2.0,
            )
        if t in ("brand", "company", "competitor", "retailer"):
            return dict(
                activity_level=0.3, posts_per_hour=0.2, comments_per_hour=0.1,
                active_hours=list(range(8, 21)),
                response_delay_min=30, response_delay_max=120,
                sentiment_bias=0.2, stance="supportive", influence_weight=2.0,
            )
        if t in ("student",):
            return dict(
                activity_level=0.8, posts_per_hour=0.6, comments_per_hour=1.5,
                active_hours=[8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],
                response_delay_min=1, response_delay_max=15,
                sentiment_bias=0.0, stance="neutral", influence_weight=0.8,
            )
        if t in ("alumni",):
            return dict(
                activity_level=0.6, posts_per_hour=0.4, comments_per_hour=0.8,
                active_hours=[12, 13, 19, 20, 21, 22, 23],
                response_delay_min=5, response_delay_max=30,
                sentiment_bias=0.0, stance="neutral", influence_weight=1.0,
            )
        # default: consumer / person
        return dict(
            activity_level=0.7, posts_per_hour=0.5, comments_per_hour=1.2,
            active_hours=[9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],
            response_delay_min=2, response_delay_max=20,
            sentiment_bias=0.0, stance="neutral", influence_weight=1.0,
        )
