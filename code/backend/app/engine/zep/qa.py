"""Brand Q&A from Zep facts (post-simulation semantic queries).

Given a Zep graph populated by `enrichment.maybe_enrich_with_zep`, this module:

1. Builds a list of brand-specific questions (default set + custom from scenario_brief)
2. For each question: runs `graph.search` to fetch relevant facts
3. Asks the LLM to synthesise an answer in italiano, citing the facts

Best-effort: if Zep is unavailable, returns `{"status": "skipped"}` so the
pipeline never blocks.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from app.llm.mistral import MistralClient
from app.schemas import BrandSeed

logger = logging.getLogger(__name__)


DEFAULT_QUESTIONS = [
    "Quali sono i segmenti di audience più critici per il brand?",
    "Quali topic generano sentiment più negativo e perché?",
    "Quali leve di azione possono ridurre il rischio reputazionale?",
    "Quali competitor o alternative emergono dalle conversazioni?",
]


SYSTEM_PROMPT = """Sei un analista di brand monitoring. Rispondi in italiano, in modo conciso (3-5 frasi).
Devi basare la risposta SOLO sui fact forniti. Se i fact non sono sufficienti, dillo esplicitamente.
Cita 2-3 fact specifici tra parentesi quadre alla fine della risposta, es: [fact 1, fact 3].
"""


def generate_zep_qa(
    *,
    seed: BrandSeed,
    zep_result: dict[str, Any],
    scenario_brief: Optional[str] = None,
    custom_questions: Optional[list[str]] = None,
    client: Optional[MistralClient] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Run a Q&A pass on the Zep graph populated for this brand.

    Returns:
        {
            "status": "ok" | "skipped" | "error",
            "reason": str,
            "questions": [
                {
                    "question": str,
                    "answer": str,
                    "facts": [str, ...],
                    "fact_count": int,
                }
            ],
            "model": str | None,
        }
    """
    if zep_result.get("status") != "ok":
        return {
            "status": "skipped",
            "reason": f"Zep enrichment status={zep_result.get('status')}",
            "questions": [],
            "model": None,
        }

    graph_id = zep_result.get("graph_id")
    if not graph_id:
        return {"status": "skipped", "reason": "no graph_id", "questions": [], "model": None}

    key = api_key or os.environ.get("ZEP_API_KEY", "")
    if not key:
        return {
            "status": "skipped",
            "reason": "ZEP_API_KEY not set",
            "questions": [],
            "model": None,
        }

    # Lazy-import to keep Zep optional.
    try:
        from app.engine.zep import create_zep_client, is_zep_available
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": f"zep import: {exc}", "questions": [], "model": None}
    if not is_zep_available():
        return {
            "status": "skipped",
            "reason": "zep_cloud not installed",
            "questions": [],
            "model": None,
        }

    if client is None:
        try:
            client = MistralClient()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "skipped",
                "reason": f"LLM unavailable: {exc}",
                "questions": [],
                "model": None,
            }

    zep_client = create_zep_client(key)

    questions = list(custom_questions or DEFAULT_QUESTIONS)
    # Add a scenario-specific question if provided.
    if scenario_brief and scenario_brief.strip():
        questions.append(
            f"Rispetto allo scenario richiesto dall'utente ('{scenario_brief.strip()[:160]}…'),"
            " quali fact emersi dalla simulazione sono più rilevanti?"
        )

    qa_items: list[dict[str, Any]] = []
    for q in questions[:6]:
        facts = _search_facts(zep_client, graph_id, q, limit=6)
        if not facts:
            qa_items.append(
                {
                    "question": q,
                    "answer": "Nessun fact rilevante trovato nel grafo Zep.",
                    "facts": [],
                    "fact_count": 0,
                }
            )
            continue
        answer = _synthesise_answer(client, brand=seed.brand, question=q, facts=facts)
        qa_items.append(
            {
                "question": q,
                "answer": answer,
                "facts": facts,
                "fact_count": len(facts),
            }
        )

    return {
        "status": "ok",
        "reason": "",
        "questions": qa_items,
        "model": client.config.model,
    }


def _search_facts(zep_client: Any, graph_id: str, query: str, *, limit: int = 6) -> list[str]:
    """Best-effort facts retrieval via Zep graph.search; returns list of fact strings."""
    try:
        result = zep_client.graph.search(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Zep search failed (%s): %s", query[:40], exc)
        return []

    facts: list[str] = []
    edges = getattr(result, "edges", None) or []
    for edge in edges:
        fact = getattr(edge, "fact", None)
        if fact:
            facts.append(str(fact))
    # Sometimes facts come back via nodes too.
    nodes = getattr(result, "nodes", None) or []
    for node in nodes:
        summary = getattr(node, "summary", None)
        name = getattr(node, "name", None)
        if summary and name:
            facts.append(f"[{name}] {summary}")
    # Dedup while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for f in facts:
        if f in seen:
            continue
        seen.add(f)
        deduped.append(f)
    return deduped[:limit]


def _synthesise_answer(
    client: MistralClient, *, brand: str, question: str, facts: list[str]
) -> str:
    """Ask LLM to compose an Italian answer based on the supplied facts."""
    facts_block = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts))
    user = (
        f"Brand: {brand}\n\n"
        f"Domanda: {question}\n\n"
        f"Fact dal grafo Zep:\n{facts_block}\n\n"
        "Rispondi in italiano, 3-5 frasi. Cita i numeri dei fact usati tra parentesi quadre."
    )
    try:
        return client.chat(
            system=SYSTEM_PROMPT,
            user=user,
            temperature=0.2,
            response_format_json=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM Q&A synthesis failed: %s", exc)
        return f"(Risposta non disponibile: {exc})"
