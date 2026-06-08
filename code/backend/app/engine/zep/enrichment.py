"""
Optional Zep enrichment: register brand seed facts in a Zep graph.

Best-effort module:
- if ZEP_API_KEY missing → returns `{"status": "skipped", ...}`
- if zep_cloud not importable → returns `{"status": "unavailable", ...}`
- if Zep API call fails → returns `{"status": "error", ...}` (never raises)

Designed to be cheap (a few graph.add calls) so it can be enabled by default.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.schemas import BrandSeed


def maybe_enrich_with_zep(
    seed: BrandSeed,
    *,
    api_key: Optional[str] = None,
    graph_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Register brand+segments+topics as facts in a Zep graph (best-effort).

    Returns a structured dict describing what happened. Never raises.
    """
    gid = graph_id or _default_graph_id(seed.brand)
    graph_preview = _build_graph_preview(seed, gid)
    key = api_key or os.environ.get("ZEP_API_KEY", "")
    if not key:
        return {
            "status": "skipped",
            "reason": "ZEP_API_KEY not set",
            "graph_id": None,
            "facts_registered": 0,
            "graph_preview": graph_preview,
        }

    try:
        from app.engine.zep import create_zep_client, is_zep_available
    except Exception as exc:  # pragma: no cover
        return {
            "status": "unavailable",
            "reason": f"engine.zep import failed: {exc}",
            "graph_id": None,
            "facts_registered": 0,
            "graph_preview": graph_preview,
        }

    if not is_zep_available():
        return {
            "status": "unavailable",
            "reason": "zep_cloud package not installed",
            "graph_id": None,
            "facts_registered": 0,
            "graph_preview": graph_preview,
        }

    try:
        client = create_zep_client(key)
        _ensure_graph(client, gid)
        registered = _register_facts(client, gid, seed)
        return {
            "status": "ok",
            "reason": "",
            "graph_id": gid,
            "facts_registered": registered,
            "graph_preview": graph_preview,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
            "graph_id": gid,
            "facts_registered": 0,
            "graph_preview": graph_preview,
        }


# === Internals ===


def _default_graph_id(brand: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in brand.lower()).strip("_")
    return f"miroedo_{safe or 'brand'}"


def _build_graph_preview(seed: BrandSeed, graph_id: str) -> Dict[str, Any]:
    """Build a compact graph preview mirroring the facts sent to Zep.

    This is deterministic and local: even if Zep is unavailable, the frontend can
    render the intended memory graph shape and distinguish it from the persisted
    Zep status via `status`/`facts_registered`.
    """
    nodes: list[Dict[str, Any]] = []
    links: list[Dict[str, str]] = []

    brand_id = "brand"
    sentiment_id = "sentiment"
    nodes.append(
        {
            "id": brand_id,
            "label": seed.brand,
            "type": "brand",
            "weight": max(1, int(seed.total_mentions or 1)),
            "sentiment": float(seed.overall_sentiment or 0),
        }
    )
    nodes.append(
        {
            "id": sentiment_id,
            "label": f"Sentiment {seed.overall_sentiment:+.2f}",
            "type": "sentiment",
            "weight": 1,
            "sentiment": float(seed.overall_sentiment or 0),
        }
    )
    links.append({"source": brand_id, "target": sentiment_id, "type": "has_sentiment"})

    for i, seg in enumerate(seed.segments[:6]):
        sid = f"segment:{i}"
        sentiment = _segment_sentiment_score(seg.sentiment_baseline)
        nodes.append(
            {
                "id": sid,
                "label": seg.name,
                "type": "segment",
                "weight": float(seg.weight or 0),
                "sentiment": sentiment,
            }
        )
        links.append({"source": brand_id, "target": sid, "type": "segment"})

    for i, topic in enumerate(seed.topics[:8]):
        tid = f"topic:{i}"
        nodes.append(
            {
                "id": tid,
                "label": topic.name,
                "type": "topic",
                "weight": int(topic.mentions or 0),
                "sentiment": float(topic.sentiment_score or 0),
            }
        )
        links.append({"source": brand_id, "target": tid, "type": "topic"})
        if seed.segments:
            links.append({"source": tid, "target": f"segment:{i % min(len(seed.segments), 6)}", "type": "resonates_with"})

    for i, group in enumerate((seed.platforms or [])[:4]):
        pid = f"platform:{i}"
        nodes.append(
            {
                "id": pid,
                "label": group.name,
                "type": "platform",
                "weight": float(group.share or group.count or 0),
                "sentiment": float(group.sentiment or 0),
            }
        )
        links.append({"source": brand_id, "target": pid, "type": "mentioned_on"})

    return {"graph_id": graph_id, "nodes": nodes, "links": links}


def _segment_sentiment_score(label: str) -> float:
    value = (label or "").lower()
    if "neg" in value:
        return -0.6
    if "pos" in value:
        return 0.6
    return 0.0


def _ensure_graph(client: Any, graph_id: str) -> None:
    """Create the graph if it doesn't already exist. Idempotent."""
    try:
        # Most Zep SDK versions: client.graph.create(graph_id=...)
        client.graph.create(graph_id=graph_id)
    except Exception:
        # Already exists, or different SDK shape — keep going.
        pass


def _register_facts(client: Any, graph_id: str, seed: BrandSeed) -> int:
    """Push compact text facts about brand/segments/topics into the graph."""
    facts: list[str] = []
    facts.append(
        f"Brand: {seed.brand}. Market: {seed.market}. Language: {seed.language}. "
        f"Monitoring window: {seed.monitoring_window_days} days. "
        f"Total mentions: {seed.total_mentions}. "
        f"Overall sentiment: {seed.overall_sentiment:+.2f}."
    )
    for seg in seed.segments:
        facts.append(
            f"{seed.brand} segment '{seg.name}' weight {seg.weight:.2f}, "
            f"sentiment {seg.sentiment_baseline}: {seg.description}"
        )
    for topic in seed.topics:
        facts.append(
            f"{seed.brand} topic '{topic.name}' {topic.mentions} mentions, "
            f"sentiment {topic.sentiment_score:+.2f}."
        )

    count = 0
    for fact in facts:
        try:
            client.graph.add(graph_id=graph_id, type="text", data=fact)
            count += 1
        except Exception:
            # Skip the single fact; keep going with the rest.
            continue
    return count
