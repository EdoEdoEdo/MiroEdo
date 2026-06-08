"""
Build a deterministic baseline markdown report from a `BrandSeed`.

Used by the quick-pipeline mode (no simulation): we need a markdown report
to feed into the postprocess layer (KPI extractor + executive summary +
action plan). The baseline report mirrors the structural shape of a
MiroFish full report (## chapters, blockquotes, numbered predictions)
so that the deterministic KPI extractor produces meaningful scores.
"""

from __future__ import annotations

from app.schemas import BrandSeed


def render_baseline_report(seed: BrandSeed) -> str:
    """Render a markdown brief from a BrandSeed. Italian copy."""
    lines: list[str] = []

    lines.append(f"# {seed.brand} — Brand Snapshot ({seed.market})")
    lines.append("")
    lines.append(
        f"Periodo monitorato: ultimi {seed.monitoring_window_days} giorni. "
        f"Menzioni totali: {seed.total_mentions:,}. "
        f"Sentiment medio: {seed.overall_sentiment:+.2f}."
    )
    lines.append("")

    # --- Chapter 01: Audience segments
    lines.append("## 01 Segmenti audience")
    lines.append("")
    total_w = sum(s.weight for s in seed.segments) or 1.0
    for seg in seed.segments:
        share_pct = round(seg.weight * 100 / total_w, 1)
        lines.append(
            f"- **{seg.name}** ({share_pct}%, sentiment {seg.sentiment_baseline}): "
            f"{seg.description}"
        )
        for q in seg.sample_quotes[:2]:
            lines.append(f"> {q}")
    lines.append("")

    # --- Chapter 02: Topics
    lines.append("## 02 Topic principali")
    lines.append("")
    total_mentions = sum(t.mentions for t in seed.topics) or 1
    for topic in seed.topics:
        share = round(topic.mentions * 100 / total_mentions, 1)
        lines.append(
            f"- **{topic.name}** — {topic.mentions:,} menzioni ({share}%), "
            f"sentiment {topic.sentiment_score:+.2f}."
        )
        for q in topic.sample_quotes[:1]:
            lines.append(f"> {q}")
    lines.append("")

    # --- Chapter 03: Timeline (if present)
    if seed.timeline:
        lines.append("## 03 Timeline eventi")
        lines.append("")
        for ev in seed.timeline:
            lines.append(f"- **{ev.date}** — {ev.label} ({ev.mentions:,} menzioni). {ev.note}")
        lines.append("")

    # --- Chapter 04: Numeric predictions (proxy for KPI extractor)
    lines.append("## 04 Predizioni baseline")
    lines.append("")
    pos = sum(1 for s in seed.segments if s.sentiment_baseline == "positive")
    neg = sum(1 for s in seed.segments if s.sentiment_baseline == "negative")
    pos_share = round(pos * 100 / max(len(seed.segments), 1), 1)
    neg_share = round(neg * 100 / max(len(seed.segments), 1), 1)
    lines.append(
        f"1. Nelle prossime 72 ore lo share di sentiment positivo si attesta intorno al {pos_share}%."
    )
    lines.append(
        f"2. Entro 2 settimane i segmenti negativi ({neg_share}%) "
        "richiedono attenzione attiva da Customer Care."
    )
    top_topic = seed.topics[0].name if seed.topics else "topic principale"
    lines.append(
        f"3. Nei prossimi 7 giorni il topic dominante resta '{top_topic}' con quota >30% delle menzioni."
    )
    lines.append("")

    return "\n".join(lines).strip() + "\n"
