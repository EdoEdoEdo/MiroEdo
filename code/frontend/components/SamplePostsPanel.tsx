'use client';

import { useT } from '@/lib/i18n';
import type { SimulationSummary } from '@/lib/types';

/**
 * Top sample posts dalla simulazione OASIS, arricchiti con uno score
 * di influenza derivato in modo deterministico da (a) lunghezza del
 * contenuto, (b) presenza di hashtag/menzioni, (c) intensità di topic
 * polarizzanti, (d) jitter stabile per non avere tutti gli score uguali.
 */
export default function SamplePostsPanel({
    sim,
}: {
    sim: NonNullable<SimulationSummary>;
}) {
    const { t } = useT();
    const posts = sim.sample_posts ?? [];
    if (!posts.length) return null;

    type Row = {
        post_id?: number | string;
        user_id?: number | string;
        content?: string;
        influence: number;
        sentiment: 'positive' | 'negative' | 'mixed' | 'neutral';
        tags: string[];
    };

    const HOT_WORDS = [
        'greenwashing',
        'boicotta',
        'prezzo',
        'lidl',
        'esselunga',
        'tracciab',
        'audit',
        'qr',
        'sostenibil',
        'esg',
        'whistle',
        'package',
    ];

    const NEG_HINTS = [
        'greenwashing',
        'boicotta',
        'manda',
        'caro',
        'discount',
        'lusso',
        'marketing',
        'finto',
        'fake',
    ];
    const POS_HINTS = [
        'finalmente',
        'bravi',
        'serio',
        'credibile',
        'trasparenza',
        'audited',
        'vera',
        'finally',
    ];

    const rows: Row[] = posts.map((p, idx) => {
        const text = (p.content ?? '').toLowerCase();
        const len = text.length;
        const hot = HOT_WORDS.filter((w) => text.includes(w)).length;
        const neg = NEG_HINTS.filter((w) => text.includes(w)).length;
        const pos = POS_HINTS.filter((w) => text.includes(w)).length;
        const jitter = ((idx * 17) % 13) / 26; // 0..0.5

        // Influence in [0, 100]: weighted blend of length + heat + jitter.
        const raw =
            Math.min(1, len / 220) * 40 +
            Math.min(4, hot) * 10 +
            (pos + neg) * 4 +
            jitter * 20;
        const influence = Math.round(Math.max(8, Math.min(100, raw + 20)));

        let sentiment: Row['sentiment'] = 'neutral';
        if (pos > neg && pos > 0) sentiment = 'positive';
        else if (neg > pos && neg > 0) sentiment = 'negative';
        else if (pos > 0 && neg > 0) sentiment = 'mixed';

        const tags = HOT_WORDS.filter((w) => text.includes(w)).slice(0, 3);

        return {
            post_id: p.post_id,
            user_id: p.user_id,
            content: p.content,
            influence,
            sentiment,
            tags,
        };
    });

    rows.sort((a, b) => b.influence - a.influence);

    return (
        <div style={{ marginTop: 24 }}>
            <div
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                    color: 'var(--red)',
                    marginBottom: 4,
                }}
            >
                {t('samples.title')}
            </div>
            <div
                style={{
                    fontFamily: 'var(--serif)',
                    fontStyle: 'italic',
                    fontSize: 13,
                    color: '#555',
                    marginBottom: 16,
                }}
            >
                {t('samples.subtitle')}
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
                {rows.map((r) => (
                    <PostRow key={r.post_id ?? Math.random()} row={r} />
                ))}
            </div>
        </div>
    );
}

function PostRow({
    row,
}: {
    row: {
        post_id?: number | string;
        user_id?: number | string;
        content?: string;
        influence: number;
        sentiment: 'positive' | 'negative' | 'mixed' | 'neutral';
        tags: string[];
    };
}) {
    const sentColor = {
        positive: '#1b7a3e',
        negative: '#c41e1e',
        mixed: '#b8741b',
        neutral: '#666',
    }[row.sentiment];
    return (
        <div
            style={{
                background: '#fff',
                border: '1px solid var(--ink)',
                padding: '12px 14px',
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) 80px',
                gap: 14,
                alignItems: 'center',
            }}
        >
            <div style={{ minWidth: 0 }}>
                <div
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 9,
                        letterSpacing: '0.18em',
                        color: '#888',
                        marginBottom: 4,
                    }}
                >
                    POST#{row.post_id} · AGENT#{row.user_id} ·{' '}
                    <span
                        style={{
                            color: sentColor,
                            fontWeight: 600,
                            letterSpacing: '0.15em',
                        }}
                    >
                        {row.sentiment.toUpperCase()}
                    </span>
                </div>
                <div
                    style={{
                        fontFamily: 'var(--serif)',
                        fontSize: 14,
                        lineHeight: 1.45,
                        color: 'var(--ink)',
                    }}
                >
                    «{row.content}»
                </div>
                {row.tags.length > 0 && (
                    <div
                        style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: 4,
                            marginTop: 6,
                        }}
                    >
                        {row.tags.map((t) => (
                            <span
                                key={t}
                                style={{
                                    background: 'var(--ink)',
                                    color: '#fff',
                                    fontFamily: 'var(--mono)',
                                    fontSize: 9,
                                    padding: '2px 6px',
                                    letterSpacing: '0.08em',
                                }}
                            >
                                #{t}
                            </span>
                        ))}
                    </div>
                )}
            </div>
            <div
                style={{
                    textAlign: 'right',
                    fontFamily: 'var(--mono)',
                }}
            >
                <div
                    style={{
                        fontSize: 9,
                        letterSpacing: '0.18em',
                        color: '#888',
                    }}
                >
                    INFLUENCE
                </div>
                <div
                    style={{
                        fontFamily: 'var(--display)',
                        fontSize: 28,
                        lineHeight: 1,
                        color: 'var(--ink)',
                    }}
                >
                    {row.influence}
                </div>
                <div
                    style={{
                        height: 4,
                        background: '#eee',
                        marginTop: 4,
                        overflow: 'hidden',
                    }}
                >
                    <div
                        style={{
                            width: `${row.influence}%`,
                            height: '100%',
                            background:
                                row.influence > 70
                                    ? 'var(--red)'
                                    : 'var(--ink)',
                        }}
                    />
                </div>
            </div>
        </div>
    );
}
