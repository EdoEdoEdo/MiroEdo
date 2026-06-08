'use client';

import { useMemo } from 'react';
import * as d3 from 'd3';
import type { BrandSeed } from '../lib/types';
import { useElementSize } from '../lib/d3Hooks';
import ChartTooltip, { useChartTooltip } from './ChartTooltip';

const COLORS: Record<string, string> = {
    positive: '#137b3a',
    neutral: '#6b6b6b',
    negative: '#b8332b',
    mixed: '#a87a00',
};

export default function SentimentDonut({ seed }: { seed: BrandSeed }) {
    const data = useMemo(() => {
        const b = seed.sentiment_breakdown;
        if (!b) return [];
        const entries: { key: string; value: number }[] = [
            { key: 'positive', value: b.positive ?? 0 },
            { key: 'neutral', value: b.neutral ?? 0 },
            { key: 'negative', value: b.negative ?? 0 },
        ];
        if (b.mixed) entries.push({ key: 'mixed', value: b.mixed });
        return entries.filter((e) => e.value > 0);
    }, [seed]);

    const { ref, size } = useElementSize<HTMLDivElement>({
        width: 260,
        height: 200,
    });

    if (data.length === 0) return null;

    const total = d3.sum(data, (d) => d.value);
    const height = 200;
    const r = Math.min(size.width, height) / 2;
    const outerR = Math.max(40, r - 12);
    const innerR = Math.max(20, outerR - 32);

    const pie = d3
        .pie<{ key: string; value: number }>()
        .value((d) => d.value)
        .sort(null);
    const arc = d3
        .arc<d3.PieArcDatum<{ key: string; value: number }>>()
        .innerRadius(innerR)
        .outerRadius(outerR);

    const arcs = pie(data);
    const { tip, show, hide } = useChartTooltip();

    return (
        <div
            style={{
                background: '#fff',
                border: '1px solid #ddd',
                padding: 16,
                position: 'relative',
            }}
        >
            <div
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.2em',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    marginBottom: 8,
                }}
            >
                Distribuzione sentiment
            </div>
            <div ref={ref} style={{ width: '100%', height }}>
                <svg width={size.width} height={height} role="img">
                    <g transform={`translate(${size.width / 2},${height / 2})`}>
                        {arcs.map((a) => (
                            <path
                                key={a.data.key}
                                d={arc(a) ?? ''}
                                fill={COLORS[a.data.key] ?? '#888'}
                                stroke="#fff"
                                strokeWidth={1}
                                style={{ cursor: 'pointer' }}
                                onMouseMove={(e) =>
                                    show(
                                        e,
                                        `${a.data.key}\n${a.data.value.toLocaleString()} menzioni\n${Math.round((a.data.value / total) * 100)}% del totale`,
                                    )
                                }
                                onMouseLeave={hide}
                            >
                                <title>{`${a.data.key}: ${Math.round((a.data.value / total) * 100)}%`}</title>
                            </path>
                        ))}
                        <text
                            textAnchor="middle"
                            dy="-0.2em"
                            fontSize={11}
                            fill="#666"
                            style={{ fontFamily: 'var(--mono)' }}
                        >
                            Sentiment medio
                        </text>
                        <text
                            textAnchor="middle"
                            dy="1.1em"
                            fontSize={16}
                            fill="#222"
                            fontWeight={600}
                        >
                            {(seed.overall_sentiment ?? 0).toFixed(2)}
                        </text>
                    </g>
                </svg>
            </div>
            <div
                style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    fontSize: 11,
                    color: '#555',
                    marginTop: 6,
                }}
            >
                {data.map((d) => (
                    <span
                        key={d.key}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                        }}
                    >
                        <span
                            style={{
                                width: 10,
                                height: 10,
                                background: COLORS[d.key],
                                display: 'inline-block',
                            }}
                        />
                        {d.key} · {Math.round((d.value / total) * 100)}%
                    </span>
                ))}
            </div>
            <ChartTooltip tip={tip} />
        </div>
    );
}
