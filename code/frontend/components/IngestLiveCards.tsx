'use client';

import { useEffect, useMemo, useState } from 'react';

interface IngestPreview {
    brand?: string;
    total_mentions?: number;
    overall_sentiment?: number;
    window_days?: number;
    topics?: { name: string; mentions: number; sentiment: number }[];
    platforms?: { name: string; count: number; share: number }[];
    countries?: { name: string; count: number; share: number }[];
    segments_count?: number;
    graph_nodes?: number;
    graph_links?: number;
    sentiment_breakdown?: {
        positive: number;
        neutral: number;
        negative: number;
        mixed?: number;
    };
}

interface Card {
    key: string;
    type: 'brand' | 'topic' | 'platform' | 'country' | 'graph' | 'sentiment';
    label: string;
    sub?: string;
    accent?: 'pos' | 'neg' | 'neu';
}

function sentLabel(s: number): 'pos' | 'neg' | 'neu' {
    if (s <= -0.05) return 'neg';
    if (s >= 0.05) return 'pos';
    return 'neu';
}

const ACCENT_BG = {
    pos: '#e8f3eb',
    neg: '#f6e2e0',
    neu: '#efefef',
};
const ACCENT_BAR = {
    pos: '#137b3a',
    neg: '#b8332b',
    neu: '#6b6b6b',
};

const TYPE_META: Record<
    Card['type'],
    { icon: string; label: string; color: string }
> = {
    brand: { icon: '◆', label: 'Brand', color: '#3b6cd9' },
    topic: { icon: '▲', label: 'Topic', color: '#a53d5a' },
    platform: { icon: '◉', label: 'Platform', color: '#7b3da5' },
    country: { icon: '●', label: 'Country', color: '#3da57b' },
    graph: { icon: '⬡', label: 'Graph', color: '#444' },
    sentiment: { icon: '◐', label: 'Sentiment', color: '#a87a00' },
};

export default function IngestLiveCards({
    preview,
}: {
    preview?: IngestPreview | null;
}) {
    const allCards = useMemo<Card[]>(() => {
        if (!preview) return [];
        const out: Card[] = [];
        if (preview.brand) {
            out.push({
                key: 'brand',
                type: 'brand',
                label: preview.brand,
                sub: `${(preview.total_mentions ?? 0).toLocaleString()} mention · ${preview.window_days ?? '?'}gg`,
            });
        }
        const sb = preview.sentiment_breakdown;
        if (sb) {
            const total =
                sb.positive + sb.neutral + sb.negative + (sb.mixed ?? 0);
            if (total > 0) {
                out.push({
                    key: 'sentiment',
                    type: 'sentiment',
                    label: `Sentiment ${(preview.overall_sentiment ?? 0).toFixed(2)}`,
                    sub: `+${sb.positive} / =${sb.neutral} / -${sb.negative}`,
                    accent: sentLabel(preview.overall_sentiment ?? 0),
                });
            }
        }
        for (const t of preview.topics ?? []) {
            out.push({
                key: `topic:${t.name}`,
                type: 'topic',
                label: t.name,
                sub: `${t.mentions.toLocaleString()} mention · sent ${t.sentiment.toFixed(2)}`,
                accent: sentLabel(t.sentiment),
            });
        }
        for (const p of preview.platforms ?? []) {
            out.push({
                key: `plat:${p.name}`,
                type: 'platform',
                label: p.name,
                sub: `${p.count.toLocaleString()} (${Math.round(p.share * 100)}%)`,
            });
        }
        for (const c of preview.countries ?? []) {
            out.push({
                key: `cty:${c.name}`,
                type: 'country',
                label: c.name,
                sub: `${c.count.toLocaleString()} (${Math.round(c.share * 100)}%)`,
            });
        }
        if (preview.graph_nodes) {
            out.push({
                key: 'graph',
                type: 'graph',
                label: 'Knowledge graph',
                sub: `${preview.graph_nodes} nodi · ${preview.graph_links} relazioni`,
            });
        }
        return out;
    }, [preview]);

    // Staggered reveal
    const [revealed, setRevealed] = useState(0);
    useEffect(() => {
        if (revealed >= allCards.length) return;
        const id = setTimeout(() => setRevealed((n) => n + 1), 180);
        return () => clearTimeout(id);
    }, [revealed, allCards.length]);
    useEffect(() => {
        // reset when new preview arrives
        setRevealed(0);
    }, [preview?.brand, preview?.total_mentions]);

    if (!preview || allCards.length === 0) return null;

    // Reserve room for ~20 cards (5 rows × 4 cols ≈ 320px) so the layout
    // doesn't jump as cards appear one-by-one.
    const reservedRows = Math.max(4, Math.ceil(allCards.length / 4));
    const reservedHeight = reservedRows * 70 + 16;

    return (
        <div style={{ marginTop: 24 }}>
            <div
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.2em',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    marginBottom: 10,
                }}
            >
                Entità estratte dal dataset
            </div>
            <div
                style={{
                    minHeight: reservedHeight,
                    display: 'grid',
                    gridTemplateColumns:
                        'repeat(auto-fill, minmax(220px, 1fr))',
                    gap: 8,
                    alignContent: 'start',
                }}
            >
                {allCards.slice(0, revealed).map((c) => {
                    const meta = TYPE_META[c.type];
                    const bg = c.accent ? ACCENT_BG[c.accent] : '#fafafa';
                    const bar = c.accent ? ACCENT_BAR[c.accent] : meta.color;
                    return (
                        <div
                            key={c.key}
                            style={{
                                background: bg,
                                borderLeft: `3px solid ${bar}`,
                                padding: '8px 12px',
                                fontFamily: 'var(--sans)',
                                animation: 'me-fade-in 250ms ease-out',
                            }}
                        >
                            <div
                                style={{
                                    fontFamily: 'var(--mono)',
                                    fontSize: 9,
                                    letterSpacing: '0.15em',
                                    textTransform: 'uppercase',
                                    color: meta.color,
                                    marginBottom: 2,
                                }}
                            >
                                <span style={{ marginRight: 4 }}>
                                    {meta.icon}
                                </span>
                                {meta.label}
                            </div>
                            <div style={{ fontSize: 13, fontWeight: 600 }}>
                                {c.label}
                            </div>
                            {c.sub && (
                                <div
                                    style={{
                                        fontSize: 11,
                                        color: '#555',
                                        marginTop: 2,
                                    }}
                                >
                                    {c.sub}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
            <style jsx>{`
                @keyframes me-fade-in {
                    from {
                        opacity: 0;
                        transform: translateY(4px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
            `}</style>
        </div>
    );
}
