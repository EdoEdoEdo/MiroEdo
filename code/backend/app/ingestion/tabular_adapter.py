"""
BrandwatchCSVAdapter — parse export Brandwatch (Mentions CSV) → BrandSeed.

Brandwatch esporta tipicamente CSV con queste colonne (variabili per versione):
- Date, Url, Resource (=Twitter/Instagram/...), Hit Sentence, Author,
  Country, Language, Sentiment (positive/neutral/negative), Reach, Impressions,
  Engagement, Topics (semicolon-separated), Tags

Per il DEMO accettiamo uno schema "permissivo":
  - tutte le colonne sopra sono opzionali (eccetto Date e qualcosa di testuale)
  - le mancanti vengono inferite o riempite con default

NOTA: questo è un adapter no-LLM, deterministico. La segmentazione audience
qui è euristica (per Country/Tag). Una segmentazione semantica più ricca
verrà fatta in Fase B con un LLM-based segmenter opzionale.
"""

from __future__ import annotations

import io
import re
from collections import Counter, defaultdict

import pandas as pd

from app.schemas import BrandSeed, GroupStat, Segment, SentimentBreakdown, TimelineEvent, Topic


# Mapping case-insensitive nome-colonna → canonico.
# Coprono Brandwatch, Talkwalker, Meltwater, Sprinklr, Brand24, esportazioni IT.
_COLUMN_ALIASES = {
    "date": ["date", "data", "timestamp", "published", "published date", "post date", "created", "created at", "data pubblicazione"],
    "text": ["full text", "hit sentence", "snippet", "text", "content", "mention", "message", "post text", "body", "testo", "contenuto"],
    "sentiment": ["sentiment", "sentiment label", "polarity", "tone", "tono"],
    "country": ["country", "paese", "nazione", "country name"],
    "language": ["language", "lingua", "lang"],
    "topics": ["topics", "themes", "tematiche", "category details", "categories", "tags merged", "argomenti"],
    "tags": ["tags", "tag", "labels", "etichette"],
    "reach": ["reach", "reach (new)", "impressions", "potential reach", "audience"],
    "author": ["author", "username", "user", "screen name", "full name", "autore"],
    "platform": ["page type", "page type name", "content source name", "platform", "source", "resource", "piattaforma"],
    "domain": ["domain", "url domain", "site", "dominio"],
    "hashtags": ["hashtags", "hashtag", "tags hashtags"],
    "mentioned_authors": ["mentioned authors", "mentions to", "menzionati"],
}


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    """Rinomina colonne in lowercase canonico secondo gli alias."""
    rename: dict[str, str] = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                rename[lower_cols[alias]] = canonical
                break
    return df.rename(columns=rename)


def _sentiment_to_score(s: str | None) -> float:
    if not isinstance(s, str):
        return 0.0
    s = s.strip().lower()
    return {"positive": 1.0, "neutral": 0.0, "negative": -1.0, "mixed": 0.0}.get(s, 0.0)


# Brandwatch "Category Details" pattern: "{id=..., name=Foo, ...}, {id=..., name=Bar, ...}"
_CATEGORY_NAME_RE = re.compile(r"name=([^,}]+)")

# Skip labels that look like usernames, URLs, retweets, raw IDs.
_TOPIC_BLOCKLIST_RE = re.compile(
    r"^(@|#?rt\b|https?://|www\.|id=|user_?id|t\.co/|bit\.ly/)",
    re.IGNORECASE,
)


def _is_valid_topic(label: str) -> bool:
    if not label or len(label) > 60:
        return False
    if label.lower() in {"null", "none", "n/a", "nan", "-"}:
        return False
    if _TOPIC_BLOCKLIST_RE.match(label):
        return False
    # discard pure-numeric or pure-symbol labels
    if not re.search(r"[a-zA-Zà-ÿÀ-Ÿ]", label):
        return False
    return True


def _split_topics(raw: str) -> list[str]:
    """Split a topics/tags cell into individual labels.

    Handles three styles:
    - semicolon-separated: ``"foo;bar;baz"`` (Brandwatch CSV, Talkwalker)
    - comma-separated: ``"foo, bar"`` (Meltwater)
    - Brandwatch ``Category Details`` JSON-ish: ``"{id=1, name=Foo}, {id=2, name=Bar}"``

    Filters out @usernames, URLs, RT prefixes, raw IDs, numeric-only labels.
    Output deduplicated, order preserved, max 8 per cell.
    """
    raw = raw.strip()
    if not raw:
        return []
    if "name=" in raw:
        items = _CATEGORY_NAME_RE.findall(raw)
    elif ";" in raw:
        items = raw.split(";")
    else:
        items = raw.split(",")
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = it.strip().strip('"').strip("'")
        if not _is_valid_topic(s):
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= 8:
            break
    return out


def _build_segments(df: pd.DataFrame) -> list[Segment]:
    """
    Euristica DEMO:
    - Se c'è 'country' usiamo i top 5 paesi come segmenti.
    - Altrimenti, se c'è 'tags' usiamo i top 5 tag.
    - Altrimenti, segmento unico "Tutto il pubblico".
    """
    segments: list[Segment] = []
    total = len(df) or 1

    if "country" in df.columns and df["country"].notna().any():
        counts = df["country"].dropna().value_counts().head(8)
        # Drop noise: long-tail countries with < 2% share are usually
        # geo-IP false positives, not real audience segments.
        counts = counts[counts / total >= 0.02].head(5)
        for country, n in counts.items():
            sub = df[df["country"] == country]
            sent = sub["sentiment"].map(_sentiment_to_score).mean() if "sentiment" in sub else 0.0
            label = "positive" if sent > 0.2 else "negative" if sent < -0.2 else "mixed"
            segments.append(
                Segment(
                    name=str(country),
                    weight=round(n / total, 4),
                    description=f"Pubblico geografico — {country} ({n} mention)",
                    sentiment_baseline=label,
                    sample_quotes=_sample_quotes(sub, 2, keyword=str(country)),
                )
            )
        return segments

    if "tags" in df.columns and df["tags"].notna().any():
        tag_counter: Counter[str] = Counter()
        for raw in df["tags"].dropna():
            for t in _split_topics(str(raw)):
                if t:
                    tag_counter[t] += 1
        for tag, n in tag_counter.most_common(5):
            mask = df["tags"].fillna("").str.contains(tag, regex=False)
            sub = df[mask]
            sent = sub["sentiment"].map(_sentiment_to_score).mean() if "sentiment" in sub else 0.0
            label = "positive" if sent > 0.2 else "negative" if sent < -0.2 else "mixed"
            segments.append(
                Segment(
                    name=tag,
                    weight=round(n / total, 4),
                    description=f"Segmento tematico — tag '{tag}'",
                    sentiment_baseline=label,
                    sample_quotes=_sample_quotes(sub, 2, keyword=tag),
                )
            )
        return segments

    return [
        Segment(
            name="Tutto il pubblico",
            weight=1.0,
            description="Segmentazione non disponibile nel CSV sorgente",
            sentiment_baseline="mixed",
            sample_quotes=_sample_quotes(df, 3),
        )
    ]


def _sample_quotes(df: pd.DataFrame, k: int, keyword: str | None = None) -> list[str]:
    """Return up to k diverse, relevant quotes.

    Ranking criteria (highest first):
    1. If keyword provided, texts containing it (case-insensitive) win.
    2. Sentiment extremes (positive/negative) preferred over neutral.
    3. Medium length (60-400 chars) preferred over very short/long.
    4. Deduplication on first 80-char normalised prefix.
    """
    if "text" not in df.columns:
        return []
    texts = df["text"].dropna().astype(str)
    if texts.empty:
        return []

    sentiments = (
        df.loc[texts.index, "sentiment"].fillna("neutral").astype(str).str.lower()
        if "sentiment" in df.columns
        else pd.Series(["neutral"] * len(texts), index=texts.index)
    )
    kw = (keyword or "").strip().lower()

    def _score(text: str, sent: str) -> tuple[int, int, int]:
        kw_hit = 1 if kw and kw in text.lower() else 0
        sent_hit = 1 if sent in {"positive", "negative"} else 0
        n = len(text)
        len_hit = 1 if 60 <= n <= 400 else 0
        return (kw_hit, sent_hit, len_hit)

    ranked = sorted(
        ((t, sentiments.loc[i]) for i, t in texts.items()),
        key=lambda x: _score(x[0], x[1]),
        reverse=True,
    )

    seen_prefixes: set[str] = set()
    out: list[str] = []
    for text, _sent in ranked:
        prefix = re.sub(r"\s+", " ", text.strip().lower())[:80]
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        out.append(text[:280])
        if len(out) >= k:
            break
    return out


def _build_topics(df: pd.DataFrame) -> list[Topic]:
    topic_to_rows: dict[str, list[int]] = defaultdict(list)

    if "topics" in df.columns and df["topics"].notna().any():
        for idx, raw in df["topics"].dropna().items():
            for t in _split_topics(str(raw)):
                if t:
                    topic_to_rows[t].append(idx)

    if not topic_to_rows:
        # fallback: un solo topic "Conversazione generale"
        topic_to_rows["Conversazione generale"] = list(df.index)

    topics: list[Topic] = []
    for name, idxs in sorted(topic_to_rows.items(), key=lambda kv: -len(kv[1]))[:10]:
        sub = df.loc[idxs]
        sent = sub["sentiment"].map(_sentiment_to_score).mean() if "sentiment" in sub else 0.0
        topics.append(
            Topic(
                name=name,
                mentions=len(idxs),
                sentiment_score=round(float(sent), 3),
                sample_quotes=_sample_quotes(sub, 2, keyword=name),
            )
        )
    return topics


def _build_timeline(df: pd.DataFrame) -> list[TimelineEvent]:
    """Aggregate mentions by ISO week and surface only the top 12 buckets
    plus weeks whose volume is >= 2x the median ("spike" weeks).

    Returns at most 20 entries, chronologically sorted, to keep the
    rendered markdown readable.
    """
    if "date" not in df.columns:
        return []
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return []
    # Bucket per ISO week (Monday). Use Period to get stable week labels.
    weekly = dates.dt.to_period("W").value_counts().sort_index()
    if weekly.empty:
        return []
    median = float(weekly.median())
    spike_threshold = max(median * 2.0, weekly.max() * 0.4)
    selected_idx = set(weekly.nlargest(12).index)
    selected_idx.update(weekly[weekly >= spike_threshold].index)
    selected = weekly.loc[sorted(selected_idx)].head(20)
    return [
        TimelineEvent(
            date=str(period.start_time.date()),
            label=f"settimana del {period.start_time.date()} — {int(n)} mention",
            mentions=int(n),
            note="picco" if n >= spike_threshold else "",
        )
        for period, n in selected.items()
    ]


def parse_csv(
    csv_bytes: bytes | str,
    brand: str,
    market: str = "IT",
    language: str = "it",
) -> BrandSeed:
    """
    Entrypoint principale.

    Args:
        csv_bytes: contenuto del file CSV (bytes o str già decodificata).
        brand: nome del brand (es. "Mulino Bianco").
        market: codice mercato ISO (default IT).
        language: codice lingua principale (default it).

    Returns:
        BrandSeed pronto per essere inviato a MiroFish.

    Raises:
        ValueError: se il CSV non contiene almeno una colonna testuale e una data
            oppure è completamente vuoto.
    """
    buf = io.BytesIO(csv_bytes) if isinstance(csv_bytes, bytes) else io.StringIO(csv_bytes)
    try:
        df = pd.read_csv(buf)
    except Exception:
        # Retry with semicolon separator (common in IT exports)
        if isinstance(csv_bytes, bytes):
            buf = io.BytesIO(csv_bytes)
        else:
            buf = io.StringIO(csv_bytes)
        df = pd.read_csv(buf, sep=";")
    return parse_dataframe(df, brand=brand, market=market, language=language)


def _build_knowledge_graph(df: pd.DataFrame, brand: str, max_per_type: int = 12) -> dict:
    """Extract a Brand-centric knowledge graph from a canonicalised DataFrame.

    Node types: Brand (1), Topic, Country, Platform, Author, MediaOutlet, Hashtag.
    Edge types: MENTIONS (brand→topic, brand→country), POSTS_ON (brand→platform),
    AUTHORED_BY (brand→author), PUBLISHED_BY (brand→media), TAGGED (brand→hashtag).

    Each node carries weight (mention count) and average sentiment.
    """
    nodes: list[dict] = []
    links: list[dict] = []

    def _add_node(node_id: str, ntype: str, label: str, weight: int, sentiment: float) -> None:
        nodes.append(
            {
                "id": node_id,
                "type": ntype,
                "label": label[:60],
                "weight": int(weight),
                "sentiment": round(float(sentiment), 3),
            }
        )

    def _add_link(source: str, target: str, rel: str, weight: int) -> None:
        links.append(
            {"source": source, "target": target, "type": rel, "weight": int(weight)}
        )

    brand_id = f"brand::{brand}"
    overall_sent = (
        df["sentiment"].map(_sentiment_to_score).mean() if "sentiment" in df.columns else 0.0
    )
    _add_node(brand_id, "Brand", brand, len(df), float(overall_sent))

    sent_series = (
        df["sentiment"].map(_sentiment_to_score) if "sentiment" in df.columns else None
    )

    def _agg_column(column: str, ntype: str, rel: str, splitter=None) -> None:
        if column not in df.columns:
            return
        counter: Counter[str] = Counter()
        sent_sum: dict[str, float] = defaultdict(float)
        for idx, raw in df[column].dropna().items():
            values = splitter(str(raw)) if splitter else [str(raw).strip()]
            local_sent = float(sent_series.iloc[idx]) if sent_series is not None and idx in sent_series.index else 0.0
            for v in values:
                v = v.strip()
                if not v or len(v) > 80:
                    continue
                counter[v] += 1
                sent_sum[v] += local_sent
        for value, n in counter.most_common(max_per_type):
            node_id = f"{ntype.lower()}::{value}"
            avg_sent = sent_sum[value] / max(n, 1)
            _add_node(node_id, ntype, value, n, avg_sent)
            _add_link(brand_id, node_id, rel, n)

    _agg_column("topics", "Topic", "MENTIONS", splitter=_split_topics)
    _agg_column("country", "Country", "LOCATED_IN")
    _agg_column("platform", "Platform", "POSTS_ON")
    _agg_column("author", "Author", "AUTHORED_BY")
    _agg_column("domain", "MediaOutlet", "PUBLISHED_BY")
    _agg_column(
        "hashtags",
        "Hashtag",
        "TAGGED",
        splitter=lambda s: [h.strip() for h in re.split(r"[,;\s]+", s) if h.strip().startswith("#")],
    )
    _agg_column(
        "mentioned_authors",
        "Author",
        "REPLIES_TO",
        splitter=lambda s: [a.strip() for a in re.split(r"[,;\s]+", s) if a.strip()],
    )

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "node_count": len(nodes),
            "link_count": len(links),
            "node_types": sorted({n["type"] for n in nodes}),
            "edge_types": sorted({l["type"] for l in links}),
        },
    }


def parse_dataframe(
    df: pd.DataFrame,
    *,
    brand: str,
    market: str = "IT",
    language: str = "it",
    source_tag: str = "brandwatch_csv",
) -> BrandSeed:
    """Versione riusabile: parte da un DataFrame già caricato."""
    if df.empty:
        raise ValueError("Tabella vuota: nessuna mention da processare")

    df = _canonicalize(df)
    if "text" not in df.columns:
        raise ValueError(
            "Tabella senza colonna testuale riconoscibile "
            f"(uno tra: {_COLUMN_ALIASES['text']}). Trovate: {list(df.columns)}"
        )

    overall_sent = (
        df["sentiment"].map(_sentiment_to_score).mean() if "sentiment" in df.columns else 0.0
    )

    # window: differenza fra prima e ultima data, clampato a 365 per BrandSeed schema
    window = 30
    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not dates.empty:
            window = max(1, int((dates.max() - dates.min()).days) + 1)
    window = min(window, 365)

    return BrandSeed(
        brand=brand,
        market=market,
        language=language,
        monitoring_window_days=window,
        total_mentions=len(df),
        overall_sentiment=round(float(overall_sent), 3),
        segments=_build_segments(df),
        topics=_build_topics(df),
        timeline=_build_timeline(df),
        sentiment_breakdown=_build_sentiment_breakdown(df),
        platforms=_build_group_stats(df, "platform", top_n=8),
        countries=_build_group_stats(df, "country", top_n=10),
        knowledge_graph=_build_knowledge_graph(df, brand),
        source=source_tag,  # type: ignore[arg-type]
    )


def _build_sentiment_breakdown(df: pd.DataFrame) -> SentimentBreakdown:
    if "sentiment" not in df.columns:
        return SentimentBreakdown(neutral=len(df))
    counts = (
        df["sentiment"]
        .fillna("neutral")
        .astype(str)
        .str.lower()
        .str.strip()
        .value_counts()
    )
    return SentimentBreakdown(
        positive=int(counts.get("positive", 0)),
        neutral=int(counts.get("neutral", 0)),
        negative=int(counts.get("negative", 0)),
        mixed=int(counts.get("mixed", 0)),
    )


def _build_group_stats(df: pd.DataFrame, column: str, *, top_n: int = 8) -> list[GroupStat]:
    """Top-N values for `column` with mention count + share + avg sentiment."""
    if column not in df.columns or df[column].isna().all():
        return []
    series = df[column].fillna("").astype(str).str.strip()
    series = series[series != ""]
    if series.empty:
        return []
    total = len(series)
    sent_map = (
        df.loc[series.index, "sentiment"].map(_sentiment_to_score)
        if "sentiment" in df.columns
        else pd.Series([0.0] * len(series), index=series.index)
    )
    grouped = series.groupby(series).size().sort_values(ascending=False)
    out: list[GroupStat] = []
    for name, count in grouped.head(top_n).items():
        idx = series[series == name].index
        avg_sent = float(sent_map.loc[idx].mean()) if len(idx) else 0.0
        out.append(
            GroupStat(
                name=str(name)[:60],
                count=int(count),
                share=round(count / total, 3),
                sentiment=round(avg_sent, 3),
            )
        )
    return out
