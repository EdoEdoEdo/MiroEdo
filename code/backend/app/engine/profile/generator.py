"""
OASIS Agent Profile Generator.

Adapted from MiroFish `app/services/oasis_profile_generator.py`. Changes:
- Takes `EngineConfig` instead of `Config` class
- Zep client is fully optional (passed in; None → skip enrichment gracefully)
- Removed hardcoded Chinese fallback strings; uses engine locale (`t()`)
- Uses `app.engine.utils.llm_client.LLMClient` indirectly (still uses OpenAI
  client directly for `response_format` + temperature retry — that's intentional
  to match MiroFish behaviour exactly)

Public API:
    OasisAgentProfile (dataclass)
    OasisProfileGenerator (class)
"""

from __future__ import annotations

import concurrent.futures
import csv
import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

from openai import OpenAI

from app.engine.config import EngineConfig
from app.engine.types import EntityNode
from app.engine.utils.locale import get_language_instruction, get_locale, set_default_locale, t
from app.engine.utils.logger import get_logger

logger = get_logger("miroedo.engine.profile")


# ============================================================
# Data classes
# ============================================================


@dataclass
class OasisAgentProfile:
    """OASIS Agent profile (platform-agnostic; serialized to twitter or reddit format)."""

    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str

    # Reddit
    karma: int = 1000
    # Twitter
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500

    # Extra
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)

    # Provenance
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None

    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def to_reddit_format(self) -> Dict[str, Any]:
        profile: Dict[str, Any] = {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        for key in ("age", "gender", "mbti", "country", "profession"):
            v = getattr(self, key)
            if v:
                profile[key] = v
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        return profile

    def to_twitter_format(self) -> Dict[str, Any]:
        profile: Dict[str, Any] = {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        for key in ("age", "gender", "mbti", "country", "profession"):
            v = getattr(self, key)
            if v:
                profile[key] = v
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        return profile

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


# ============================================================
# Generator
# ============================================================


class OasisProfileGenerator:
    """Generate OASIS agent profiles from EntityNode objects.

    Zep is OPTIONAL: pass `zep_client=None` to skip graph enrichment.
    When Zep is unavailable, the generator falls back to prompt-only mode
    (LLM gets entity name + summary + attributes only, no graph facts).
    """

    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
    ]

    COUNTRIES = [
        "Italy", "US", "UK", "Germany", "France", "Spain", "Switzerland",
        "Netherlands", "Belgium", "Austria",
    ]

    INDIVIDUAL_ENTITY_TYPES = {
        "student", "alumni", "professor", "person", "publicfigure",
        "expert", "faculty", "official", "journalist", "activist",
        "consumer", "influencer",
    }

    GROUP_ENTITY_TYPES = {
        "university", "governmentagency", "organization", "ngo",
        "mediaoutlet", "company", "institution", "group", "community",
        "brand", "competitor", "retailer",
    }

    def __init__(
        self,
        config: EngineConfig,
        zep_client: Optional[Any] = None,
        graph_id: Optional[str] = None,
    ) -> None:
        """
        Args:
            config: EngineConfig (LLM keys etc.)
            zep_client: optional `zep_cloud.client.Zep` instance. None → no enrichment.
            graph_id: Zep graph id (required only if zep_client is provided)
        """
        self.config = config
        if not config.llm_api_key:
            raise ValueError("EngineConfig.llm_api_key is required")

        self.client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
        self.model_name = config.llm_model

        self.zep_client = zep_client
        self.graph_id = graph_id

    # ----- public API ---------------------------------------------------

    def set_graph_id(self, graph_id: str) -> None:
        self.graph_id = graph_id

    def generate_profile_from_entity(
        self,
        entity: EntityNode,
        user_id: int,
        use_llm: bool = True,
    ) -> OasisAgentProfile:
        entity_type = entity.get_entity_type() or "Entity"
        name = entity.name
        user_name = self._generate_username(name)

        context = self._build_entity_context(entity)

        if use_llm:
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context,
            )
        else:
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
            )

        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )

    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit",
    ) -> List[OasisAgentProfile]:
        """Batch profile generation with thread pool."""
        if graph_id:
            self.graph_id = graph_id

        total = len(entities)
        profiles: List[Optional[OasisAgentProfile]] = [None] * total
        completed = [0]
        lock = Lock()

        def save_realtime() -> None:
            if not realtime_output_path:
                return
            with lock:
                existing = [p for p in profiles if p is not None]
                if not existing:
                    return
                try:
                    if output_platform == "reddit":
                        self._save_reddit_json(existing, realtime_output_path)
                    else:
                        self._save_twitter_csv(existing, realtime_output_path)
                except Exception as exc:
                    logger.warning(f"Realtime save failed: {exc}")

        current_locale = get_locale()

        def generate_one(idx: int, entity: EntityNode) -> Tuple[int, OasisAgentProfile, Optional[str]]:
            set_default_locale(current_locale)
            entity_type = entity.get_entity_type() or "Entity"
            try:
                profile = self.generate_profile_from_entity(entity, idx, use_llm)
                self._log_profile(entity.name, entity_type, profile)
                return idx, profile, None
            except Exception as exc:
                logger.error(f"Profile gen failed for {entity.name}: {exc}")
                fallback = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or "A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback, str(exc)

        logger.info(f"Generating {total} profiles (parallel={parallel_count})")

        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            futures = {executor.submit(generate_one, i, e): (i, e) for i, e in enumerate(entities)}
            for fut in concurrent.futures.as_completed(futures):
                i, e = futures[fut]
                try:
                    result_idx, profile, err = fut.result()
                    profiles[result_idx] = profile
                    with lock:
                        completed[0] += 1
                        current = completed[0]
                    save_realtime()
                    if progress_callback:
                        progress_callback(current, total, f"{current}/{total}: {e.name}")
                    if err:
                        logger.warning(f"[{current}/{total}] fallback {e.name}: {err}")
                except Exception as exc:
                    logger.error(f"Future error for {e.name}: {exc}")

        logger.info(f"Profile generation done: {len([p for p in profiles if p])}/{total}")
        return [p for p in profiles if p is not None]

    # ----- Zep enrichment (graceful no-op if zep_client is None) --------

    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """Hybrid search Zep for entity facts/related nodes. No-op when zep disabled."""
        empty = {"facts": [], "node_summaries": [], "context": ""}
        if self.zep_client is None or not self.graph_id:
            return empty

        entity_name = entity.name
        query = t("progress.zepSearchQuery", name=entity_name)
        results: Dict[str, Any] = {"facts": [], "node_summaries": [], "context": ""}

        def _retry(fn: Callable[[], Any], desc: str) -> Any:
            delay = 2.0
            for attempt in range(3):
                try:
                    return fn()
                except Exception as exc:
                    if attempt == 2:
                        logger.debug(f"Zep {desc} failed after 3 attempts: {exc}")
                        return None
                    time.sleep(delay)
                    delay *= 2
            return None

        def search_edges() -> Any:
            return _retry(
                lambda: self.zep_client.graph.search(
                    query=query, graph_id=self.graph_id, limit=30, scope="edges", reranker="rrf"
                ),
                "edge search",
            )

        def search_nodes() -> Any:
            return _retry(
                lambda: self.zep_client.graph.search(
                    query=query, graph_id=self.graph_id, limit=20, scope="nodes", reranker="rrf"
                ),
                "node search",
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                edge_fut = ex.submit(search_edges)
                node_fut = ex.submit(search_nodes)
                edge_res = edge_fut.result(timeout=30)
                node_res = node_fut.result(timeout=30)

            facts = set()
            if edge_res and getattr(edge_res, "edges", None):
                for edge in edge_res.edges:
                    if getattr(edge, "fact", None):
                        facts.add(edge.fact)
            results["facts"] = list(facts)

            summaries = set()
            if node_res and getattr(node_res, "nodes", None):
                for node in node_res.nodes:
                    if getattr(node, "summary", None):
                        summaries.add(node.summary)
                    if getattr(node, "name", None) and node.name != entity_name:
                        summaries.add(f"Related entity: {node.name}")
            results["node_summaries"] = list(summaries)

            parts = []
            if results["facts"]:
                parts.append("Facts:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                parts.append("Related:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(parts)
            logger.info(
                f"Zep enrichment for {entity_name}: {len(results['facts'])} facts, "
                f"{len(results['node_summaries'])} related"
            )
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep enrichment timeout for {entity_name}")
        except Exception as exc:
            logger.warning(f"Zep enrichment failed for {entity_name}: {exc}")

        return results

    def _build_entity_context(self, entity: EntityNode) -> str:
        parts: List[str] = []

        if entity.attributes:
            attrs = [f"- {k}: {v}" for k, v in entity.attributes.items() if v and str(v).strip()]
            if attrs:
                parts.append("### Entity attributes\n" + "\n".join(attrs))

        existing_facts: set = set()
        if entity.related_edges:
            rels = []
            for edge in entity.related_edges:
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                if fact:
                    rels.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    arrow = f"-[{edge_name}]->" if direction == "outgoing" else f"<-[{edge_name}]-"
                    rels.append(f"- {entity.name} {arrow} (related)")
            if rels:
                parts.append("### Relations\n" + "\n".join(rels))

        if entity.related_nodes:
            info = []
            for node in entity.related_nodes:
                node_name = node.get("name", "")
                labels = [l for l in node.get("labels", []) if l not in ("Entity", "Node")]
                summary = node.get("summary", "")
                lbl = f" ({', '.join(labels)})" if labels else ""
                if summary:
                    info.append(f"- **{node_name}**{lbl}: {summary}")
                else:
                    info.append(f"- **{node_name}**{lbl}")
            if info:
                parts.append("### Related entities\n" + "\n".join(info))

        zep_results = self._search_zep_for_entity(entity)
        if zep_results.get("facts"):
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                parts.append("### Zep facts\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        if zep_results.get("node_summaries"):
            parts.append(
                "### Zep related nodes\n"
                + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10])
            )

        return "\n\n".join(parts)

    # ----- LLM persona generation --------------------------------------

    def _is_individual_entity(self, entity_type: str) -> bool:
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES

    def _is_group_entity(self, entity_type: str) -> bool:
        return entity_type.lower() in self.GROUP_ENTITY_TYPES

    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> Dict[str, Any]:
        is_individual = self._is_individual_entity(entity_type)

        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        max_attempts = 3
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._system_prompt(is_individual)},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),
                )
                content = response.choices[0].message.content or ""

                if response.choices[0].finish_reason == "length":
                    logger.warning(f"LLM truncated (attempt {attempt + 1}), trying to fix")
                    content = self._fix_truncated_json(content)

                try:
                    result = json.loads(content)
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} is a {entity_type}."
                    return result
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON parse failed (attempt {attempt + 1}): {str(je)[:80]}")
                    fixed = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if fixed.pop("_fixed", False):
                        return fixed
                    last_error = je

            except Exception as exc:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {str(exc)[:80]}")
                last_error = exc
                time.sleep(1 * (attempt + 1))

        logger.warning(f"LLM persona gen failed after {max_attempts}: {last_error}, using rules")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )

    def _fix_truncated_json(self, content: str) -> str:
        content = content.strip()
        open_braces = content.count("{") - content.count("}")
        open_brackets = content.count("[") - content.count("]")
        if content and content[-1] not in '",}]':
            content += '"'
        content += "]" * open_brackets
        content += "}" * open_braces
        return content

    def _try_fix_json(
        self, content: str, entity_name: str, entity_type: str, entity_summary: str = ""
    ) -> Dict[str, Any]:
        content = self._fix_truncated_json(content)
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            json_str = match.group()
            json_str = re.sub(
                r'"[^"\\]*(?:\\.[^"\\]*)*"',
                lambda m: re.sub(r"\s+", " ", m.group(0).replace("\n", " ").replace("\r", " ")),
                json_str,
            )
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError:
                try:
                    json_str = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", json_str)
                    json_str = re.sub(r"\s+", " ", json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except Exception:
                    pass

        bio_m = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_m = re.search(r'"persona"\s*:\s*"([^"]*)', content)
        bio = bio_m.group(1) if bio_m else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_m.group(1) if persona_m else (entity_summary or f"{entity_name} is a {entity_type}.")
        if bio_m or persona_m:
            return {"bio": bio, "persona": persona, "_fixed": True}

        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} is a {entity_type}.",
        }

    def _system_prompt(self, is_individual: bool) -> str:
        base = (
            "You are an expert at generating realistic social-media user personas for "
            "opinion simulation. Personas must be detailed, grounded in the provided "
            "context, and consistent with reality. Always return valid JSON; string "
            "values must not contain unescaped newlines."
        )
        return f"{base}\n\n{get_language_instruction()}"

    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> str:
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "none"
        ctx = context[:3000] if context else "no additional context"

        return f"""Generate a detailed social-media user persona, grounded in real signals.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context:
{ctx}

Return JSON with these fields:

1. bio: social-media bio, ~200 chars
2. persona: detailed persona description (~2000 chars, plain text), including:
   - Basic info (age, occupation, education, location)
   - Background (key experiences, connection to events, social ties)
   - Personality (MBTI, core traits, emotional expression)
   - Social-media behaviour (posting frequency, content preferences, interaction style, tone)
   - Stances (attitude toward key topics, what triggers/moves them)
   - Distinctive traits (catchphrases, unique experiences, hobbies)
   - Memory of relevant events
3. age: integer
4. gender: "male" or "female"
5. mbti: e.g. "INTJ", "ENFP"
6. country: country name
7. profession: occupation string
8. interested_topics: array of strings

Rules:
- All values must be strings or numbers; no newlines in string values
- {get_language_instruction()} (but gender must be english: male/female)
- Stay consistent with the entity context
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> str:
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "none"
        ctx = context[:3000] if context else "no additional context"

        return f"""Generate a detailed social-media account persona for an organization/group entity.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context:
{ctx}

Return JSON with these fields:

1. bio: official account bio, ~200 chars, professional tone
2. persona: detailed account spec (~2000 chars, plain text), including:
   - Institution info (formal name, type, founding, main functions)
   - Account positioning (account type, target audience, core role)
   - Voice (language style, common expressions, taboo topics)
   - Content profile (content types, posting frequency, peak hours)
   - Stances (official position on key topics, how it handles controversy)
   - Notes (audience represented, operational habits)
   - Memory of relevant events
3. age: integer 30 (virtual age for institutions)
4. gender: "other"
5. mbti: account-style MBTI (e.g. ISTJ for strict/conservative)
6. country: country name
7. profession: institutional function description
8. interested_topics: array of strings

Rules:
- All values must be strings or numbers (no null)
- {get_language_instruction()} (gender must be english: "other")
- age must be integer 30, gender must be string "other"
"""

    # ----- Rule-based fallback -----------------------------------------

    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
    ) -> Dict[str, Any]:
        t_low = entity_type.lower()

        if t_low in ("student", "alumni"):
            return {
                "bio": f"{entity_type} interested in academics and social issues.",
                "persona": f"{entity_name} is a {t_low} actively engaged in academic and social discussions.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        if t_low in ("publicfigure", "expert", "faculty", "influencer"):
            return {
                "bio": "Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {t_low} sharing insights on important matters.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        if t_low in ("mediaoutlet", "socialmediaplatform"):
            return {
                "bio": f"Official account of {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity reporting news and facilitating public discourse.",
                "age": 30,
                "gender": "other",
                "mbti": "ISTJ",
                "country": "Italy",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events"],
            }
        if t_low in ("university", "governmentagency", "ngo", "organization", "brand", "company"):
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions and engages stakeholders.",
                "age": 30,
                "gender": "other",
                "mbti": "ISTJ",
                "country": "Italy",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community"],
            }
        return {
            "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} is a {t_low} participating in social discussions.",
            "age": random.randint(25, 50),
            "gender": random.choice(["male", "female"]),
            "mbti": random.choice(self.MBTI_TYPES),
            "country": random.choice(self.COUNTRIES),
            "profession": entity_type,
            "interested_topics": ["General", "Social Issues"],
        }

    # ----- helpers ------------------------------------------------------

    def _generate_username(self, name: str) -> str:
        u = name.lower().replace(" ", "_")
        u = "".join(c for c in u if c.isalnum() or c == "_")
        return f"{u}_{random.randint(100, 999)}"

    def _log_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile) -> None:
        topics = ", ".join(profile.interested_topics) if profile.interested_topics else "—"
        logger.info(
            f"[Generated] {entity_name} ({entity_type}) → "
            f"@{profile.user_name} | age={profile.age} | gender={profile.gender} | "
            f"mbti={profile.mbti} | country={profile.country} | topics={topics}"
        )

    # ----- save methods ------------------------------------------------

    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit",
    ) -> None:
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)

    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str) -> None:
        if not file_path.endswith(".csv"):
            file_path = file_path.replace(".json", ".csv")
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "name", "username", "user_char", "description"])
            for idx, p in enumerate(profiles):
                user_char = p.bio
                if p.persona and p.persona != p.bio:
                    user_char = f"{p.bio} {p.persona}"
                user_char = user_char.replace("\n", " ").replace("\r", " ")
                description = p.bio.replace("\n", " ").replace("\r", " ")
                writer.writerow([idx, p.name, p.user_name, user_char, description])
        logger.info(f"Saved {len(profiles)} Twitter profiles → {file_path}")

    def _normalize_gender(self, gender: Optional[str]) -> str:
        if not gender:
            return "other"
        return {"male": "male", "female": "female", "other": "other"}.get(
            gender.lower().strip(), "other"
        )

    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str) -> None:
        data = []
        for idx, p in enumerate(profiles):
            item = {
                "user_id": p.user_id if p.user_id is not None else idx,
                "username": p.user_name,
                "name": p.name,
                "bio": p.bio[:150] if p.bio else p.name,
                "persona": p.persona or f"{p.name} is a participant in social discussions.",
                "karma": p.karma or 1000,
                "created_at": p.created_at,
                "age": p.age or 30,
                "gender": self._normalize_gender(p.gender),
                "mbti": p.mbti or "ISTJ",
                "country": p.country or "Italy",
            }
            if p.profession:
                item["profession"] = p.profession
            if p.interested_topics:
                item["interested_topics"] = p.interested_topics
            data.append(item)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(profiles)} Reddit profiles → {file_path}")
