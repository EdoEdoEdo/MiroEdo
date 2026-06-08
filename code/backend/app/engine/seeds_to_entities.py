"""
Convert a `BrandSeed` (from Brandwatch CSV) into a list of `EntityNode`
suitable for the OASIS profile generator.

Heuristic mapping:
- Brand itself → 1 EntityNode (label="Brand")
- Each segment → N representative consumer entities (label="Consumer"),
  with N proportional to segment weight (min 1, max 5 per segment)
- Each top topic → 1 EntityNode (label="Topic") — used as "interest hub"
"""

from __future__ import annotations

import math
from typing import List

from app.engine.types import EntityNode
from app.schemas import BrandSeed


def seed_to_entities(
    seed: BrandSeed,
    total_consumers: int = 20,
    top_topics: int = 5,
) -> List[EntityNode]:
    """Produce a synthetic entity list grounded in the BrandSeed."""
    entities: List[EntityNode] = []

    # 1. Brand
    entities.append(
        EntityNode(
            uuid=f"brand-{_slug(seed.brand)}",
            name=seed.brand,
            labels=["Brand"],
            summary=(
                f"{seed.brand} ({seed.market}, {seed.language}). "
                f"Monitored over {seed.monitoring_window_days} days, "
                f"{seed.total_mentions} total mentions, overall sentiment {seed.overall_sentiment:+.2f}."
            ),
            attributes={
                "market": seed.market,
                "language": seed.language,
                "monitoring_window_days": seed.monitoring_window_days,
                "total_mentions": seed.total_mentions,
                "overall_sentiment": seed.overall_sentiment,
            },
        )
    )

    # 2. Consumers per segment (weighted)
    total_weight = sum(s.weight for s in seed.segments) or 1.0
    for seg in seed.segments:
        share = seg.weight / total_weight
        # Cap per-segment count at total_consumers (not a hardcoded 5) so the
        # user-provided `sim_profiles` actually drives population size.
        count = max(1, min(total_consumers, math.ceil(share * total_consumers)))
        for i in range(count):
            entities.append(
                EntityNode(
                    uuid=f"consumer-{_slug(seg.name)}-{i + 1}",
                    name=f"{seg.name} consumer #{i + 1}",
                    labels=["Consumer"],
                    summary=(
                        f"{seg.description} Sentiment baseline: {seg.sentiment_baseline}. "
                        f"Segment weight: {seg.weight:.2f}."
                    ),
                    attributes={
                        "segment": seg.name,
                        "segment_weight": seg.weight,
                        "sentiment_baseline": seg.sentiment_baseline,
                        "sample_quote": (seg.sample_quotes or [""])[0],
                    },
                )
            )

    # 3. Top topics
    sorted_topics = sorted(seed.topics, key=lambda t: t.mentions, reverse=True)[:top_topics]
    for topic in sorted_topics:
        entities.append(
            EntityNode(
                uuid=f"topic-{_slug(topic.name)}",
                name=topic.name,
                labels=["Topic"],
                summary=(
                    f"Conversation topic with {topic.mentions} mentions, "
                    f"sentiment {topic.sentiment_score:+.2f}."
                ),
                attributes={
                    "mentions": topic.mentions,
                    "sentiment_score": topic.sentiment_score,
                    "sample_quote": (topic.sample_quotes or [""])[0],
                },
            )
        )

    return entities


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")[:50]
