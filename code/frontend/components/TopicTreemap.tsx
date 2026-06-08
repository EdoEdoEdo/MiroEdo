'use client';

import { useMemo } from 'react';
import * as d3 from 'd3';
import { useT } from '../lib/i18n';
import type { BrandSeed } from '../lib/types';
import { sentColor, useElementSize } from '../lib/d3Hooks';
import ChartTooltip, { useChartTooltip } from './ChartTooltip';

export default function TopicTreemap({ seed }: { seed: BrandSeed }) {
    const { t } = useT();
    const items = useMemo(() => {
        return (seed.topics ?? [])
            .filter((t) => (t.mentions ?? 0) > 0)
            .slice(0, 16)
            .map((t) => ({
                name: t.name,
                value: t.mentions,
                sentiment: t.sentiment_score ?? 0,
            }));
    }, [seed]);

    const { ref, size } = useElementSize<HTMLDivElement>({
        width: 360,
        height: 260,
    });

    if (items.length === 0) return null;

    const height = 260;
    type Datum = {
        name?: string;
        value?: number;
        sentiment?: number;
        children?: Datum[];
    };
    const root = d3
        .hierarchy<Datum>({ children: items as Datum[] })
        .sum((d) => (typeof d.value === 'number' ? d.value : 0))
        .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    d3.treemap<Datum>().size([size.width, height]).paddingInner(2).round(true)(
        root,
    );

    const leaves = root.leaves() as d3.HierarchyRectangularNode<Datum>[];
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
                {t('chart.top_topics')}
            </div>
            <div ref={ref} style={{ width: '100%', height }}>
                <svg width={size.width} height={height} role="img">
                    {leaves.map((leaf, i) => {
                        const w = leaf.x1 - leaf.x0 || 0;
                        const h = leaf.y1 - leaf.y0 || 0;
                        const showLabel = w > 60 && h > 24;
                        const name = leaf.data.name ?? '—';
                        const value = leaf.data.value ?? 0;
                        const sentiment = leaf.data.sentiment ?? 0;
                        return (
                            <g
                                key={i}
                                transform={`translate(${leaf.x0},${leaf.y0})`}
                            >
                                <rect
                                    width={w}
                                    height={h}
                                    fill={sentColor(sentiment)}
                                    stroke="#fff"
                                    style={{ cursor: 'pointer' }}
                                    onMouseMove={(e) =>
                                        show(
                                            e,
                                            `${name}\n${value.toLocaleString()} menzioni\nsentiment ${sentiment.toFixed(2)}`,
                                        )
                                    }
                                    onMouseLeave={hide}
                                >
                                    <title>{`${name}: ${value.toLocaleString()} · sent ${sentiment.toFixed(2)}`}</title>
                                </rect>
                                {showLabel && (
                                    <>
                                        <text
                                            x={6}
                                            y={14}
                                            fontSize={11}
                                            fill="#fff"
                                            fontWeight={600}
                                        >
                                            {name.length > Math.floor(w / 7)
                                                ? name.slice(
                                                      0,
                                                      Math.max(
                                                          3,
                                                          Math.floor(w / 7) - 1,
                                                      ),
                                                  ) + '…'
                                                : name}
                                        </text>
                                        <text
                                            x={6}
                                            y={28}
                                            fontSize={10}
                                            fill="#fff"
                                            opacity={0.85}
                                        >
                                            {value.toLocaleString()}
                                        </text>
                                    </>
                                )}
                            </g>
                        );
                    })}
                </svg>
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 4 }}>
                {t('chart.treemap_note')}
            </div>
            <ChartTooltip tip={tip} />
        </div>
    );
}
