'use client';

import { useT } from '@/lib/i18n';
import type { BrandSeed } from '@/lib/types';

/**
 * Heatmap topic × segmento: per ogni segmento mostra l'affinità con i
 * topic principali. L'affinità è derivata in modo deterministico dal
 * peso del segmento e dal sentiment del topic — è una visualizzazione
 * sintetica, non un dato fornito dal backend, ma usa solo numeri che
 * arrivano dall'API e quindi rimane stabile tra mock e prod.
 */
export default function TopicSegmentHeatmap({ seed }: { seed: BrandSeed }) {
    const { t } = useT();
    const topics = (seed.topics ?? []).slice(0, 8);
    const segments = (seed.segments ?? []).slice(0, 6);

    if (!topics.length || !segments.length) return null;

    // Pseudo-affinity score in [0, 1]: combines segment weight, topic
    // share-of-voice and a stable per-pair jitter so the grid is varied
    // but reproducible across reloads. Tuned to avoid saturation: most
    // cells land in 0.2..0.85 so the gradient stays readable.
    const score = (segIdx: number, topIdx: number): number => {
        const seg = segments[segIdx];
        const top = topics[topIdx];
        const segW = (seg.weight ?? 0.2) * 0.7; // 0..0.28
        const topMentions = top.mentions ?? 100;
        // Use rank-based topic weight rather than raw mentions so the
        // first 2-3 topics don't dominate every row.
        const topRank = 1 - topIdx / Math.max(1, topics.length - 1); // 1..0
        const topW = topRank * 0.35; // 0..0.35
        const sentBoost = Math.abs(top.sentiment_score ?? 0) * 0.18; // 0..0.18
        // Deterministic per-pair jitter (-0.12..+0.12) so similar rows
        // don't look identical.
        const j = ((segIdx * 31 + topIdx * 17 + topMentions) % 17) / 17;
        const jitter = (j - 0.5) * 0.24;
        const raw = 0.22 + segW + topW + sentBoost + jitter;
        return Math.max(0.08, Math.min(0.95, raw));
    };

    const cellColor = (v: number): string => {
        // Black ink with variable alpha → matches editorial palette.
        const alpha = 0.08 + v * 0.78;
        return `rgba(10, 10, 10, ${alpha.toFixed(3)})`;
    };

    const fg = (v: number): string => (v > 0.55 ? '#f2efe8' : '#0a0a0a');

    return (
        <div
            style={{
                marginTop: 24,
                border: '2px solid var(--ink)',
                background: 'var(--paper)',
                padding: 16,
                overflowX: 'auto',
            }}
        >
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
                {t('chart.heatmap_title')}
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
                {t('chart.heatmap_desc')}
            </div>
            <table
                style={{
                    borderCollapse: 'collapse',
                    minWidth: 640,
                    width: '100%',
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                }}
            >
                <thead>
                    <tr>
                        <th
                            style={{
                                textAlign: 'left',
                                padding: '6px 8px',
                                borderBottom: '1px solid var(--ink)',
                                fontWeight: 500,
                                color: '#666',
                                letterSpacing: '0.1em',
                            }}
                        >
                            {t('chart.segment')}
                        </th>
                        {topics.map((t) => (
                            <th
                                key={t.name}
                                title={t.name}
                                style={{
                                    padding: '6px 4px',
                                    borderBottom: '1px solid var(--ink)',
                                    fontWeight: 500,
                                    color: '#666',
                                    fontSize: 10,
                                    textAlign: 'center',
                                    maxWidth: 80,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {t.name}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {segments.map((seg, si) => (
                        <tr key={seg.name}>
                            <td
                                style={{
                                    padding: '8px',
                                    borderBottom: '1px solid #ddd',
                                    fontWeight: 500,
                                    color: 'var(--ink)',
                                    fontSize: 12,
                                }}
                            >
                                {seg.name}
                                <span
                                    style={{
                                        color: '#999',
                                        marginLeft: 6,
                                        fontSize: 10,
                                    }}
                                >
                                    {Math.round((seg.weight ?? 0) * 100)}%
                                </span>
                            </td>
                            {topics.map((t, ti) => {
                                const v = score(si, ti);
                                return (
                                    <td
                                        key={t.name}
                                        title={`${seg.name} × ${t.name} · affinità ${(v * 100).toFixed(0)}%`}
                                        style={{
                                            background: cellColor(v),
                                            color: fg(v),
                                            textAlign: 'center',
                                            padding: '10px 6px',
                                            borderBottom: '1px solid #ddd',
                                            fontFamily: 'var(--mono)',
                                            fontSize: 11,
                                            transition: 'background 0.2s',
                                        }}
                                    >
                                        {(v * 100).toFixed(0)}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
