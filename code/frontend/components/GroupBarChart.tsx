'use client';

import { useMemo } from 'react';
import * as d3 from 'd3';
import { useT } from '../lib/i18n';
import { sentColor, useElementSize } from '../lib/d3Hooks';
import ChartTooltip, { useChartTooltip } from './ChartTooltip';

interface GroupStat {
    name: string;
    count: number;
    share: number;
    sentiment: number;
}

export default function GroupBarChart({
    title,
    data,
}: {
    title: string;
    data?: GroupStat[];
}) {
    const { t } = useT();
    const rows = useMemo(
        () =>
            (data ?? [])
                .slice(0, 10)
                .map((d) => ({ ...d, name: d.name || '—' })),
        [data],
    );
    const height = Math.max(160, rows.length * 28);
    const { ref, size } = useElementSize<HTMLDivElement>({
        width: 600,
        height,
    });

    if (!data || data.length === 0) return null;

    const margin = { top: 6, right: 56, bottom: 20, left: 110 };
    const innerW = Math.max(40, size.width - margin.left - margin.right);
    const innerH = Math.max(40, height - margin.top - margin.bottom);

    const x = d3
        .scaleLinear()
        .domain([0, d3.max(rows, (r) => r.count) ?? 1])
        .nice()
        .range([0, innerW]);
    const y = d3
        .scaleBand()
        .domain(rows.map((r) => r.name))
        .range([0, innerH])
        .padding(0.18);

    const xTicks = x.ticks(4);
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
                {title}
            </div>
            <div ref={ref} style={{ width: '100%', height }}>
                <svg width={size.width} height={height} role="img">
                    <g transform={`translate(${margin.left},${margin.top})`}>
                        {xTicks.map((t) => (
                            <line
                                key={t}
                                x1={x(t)}
                                x2={x(t)}
                                y1={0}
                                y2={innerH}
                                stroke="#eee"
                                strokeDasharray="3 3"
                            />
                        ))}
                        {rows.map((r) => {
                            const yy = y(r.name) ?? 0;
                            const bw = x(r.count);
                            return (
                                <g
                                    key={r.name}
                                    transform={`translate(0,${yy})`}
                                >
                                    <text
                                        x={-8}
                                        y={y.bandwidth() / 2}
                                        dy="0.35em"
                                        textAnchor="end"
                                        fontSize={11}
                                        fill="#444"
                                    >
                                        {r.name.length > 16
                                            ? r.name.slice(0, 15) + '…'
                                            : r.name}
                                    </text>
                                    <rect
                                        x={0}
                                        y={0}
                                        width={bw}
                                        height={y.bandwidth()}
                                        fill={sentColor(r.sentiment)}
                                        style={{ cursor: 'pointer' }}
                                        onMouseMove={(e) =>
                                            show(
                                                e,
                                                `${r.name}\n${r.count.toLocaleString()} menzioni (${Math.round(r.share * 100)}%)\nsentiment ${r.sentiment.toFixed(2)}`,
                                            )
                                        }
                                        onMouseLeave={hide}
                                    >
                                        <title>{`${r.name}: ${r.count.toLocaleString()} (${Math.round(r.share * 100)}%) · sent ${r.sentiment.toFixed(2)}`}</title>
                                    </rect>
                                    <text
                                        x={bw + 6}
                                        y={y.bandwidth() / 2}
                                        dy="0.35em"
                                        fontSize={10}
                                        fill="#666"
                                    >
                                        {r.count.toLocaleString()}
                                    </text>
                                </g>
                            );
                        })}
                        <g transform={`translate(0,${innerH})`}>
                            <line x1={0} x2={innerW} stroke="#888" />
                            {xTicks.map((t) => (
                                <text
                                    key={t}
                                    x={x(t)}
                                    y={14}
                                    fontSize={10}
                                    fill="#888"
                                    textAnchor="middle"
                                >
                                    {t}
                                </text>
                            ))}
                        </g>
                    </g>
                </svg>
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 4 }}>
                {t('chart.groupbar_note')}
            </div>
            <ChartTooltip tip={tip} />
        </div>
    );
}
