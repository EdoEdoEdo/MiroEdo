'use client';

import { useMemo, useState, type MouseEvent } from 'react';
import * as d3 from 'd3';
import { useT } from '../lib/i18n';
import type { VolumeForecast, ForecastPoint } from '../lib/types';
import { useElementSize } from '../lib/d3Hooks';
import ChartTooltip, { useChartTooltip } from './ChartTooltip';

interface Pt {
    date: Date;
    yhat: number;
    lo: number;
    hi: number;
}

function toPts(arr: ForecastPoint[]): Pt[] {
    return arr
        .map((p) => ({
            date: new Date(p.date),
            yhat: p.yhat,
            lo: p.yhat_lower,
            hi: p.yhat_upper,
        }))
        .filter((p) => !Number.isNaN(p.date.getTime()));
}

export default function TimelineForecastChart({
    fc,
}: {
    fc: VolumeForecast | null | undefined;
}) {
    const { t } = useT();
    const { ref, size } = useElementSize<HTMLDivElement>({
        width: 720,
        height: 280,
    });
    const hist = useMemo(() => (fc ? toPts(fc.historical) : []), [fc]);
    const fore = useMemo(() => (fc ? toPts(fc.forecast) : []), [fc]);

    if (!fc || (hist.length === 0 && fore.length === 0)) return null;

    const height = 280;
    const margin = { top: 12, right: 16, bottom: 28, left: 44 };
    const innerW = Math.max(40, size.width - margin.left - margin.right);
    const innerH = Math.max(40, height - margin.top - margin.bottom);

    const allPts = [...hist, ...fore];
    const splitDate =
        hist.length > 0 ? hist[hist.length - 1].date : fore[0]?.date;

    const x = d3
        .scaleTime()
        .domain(d3.extent(allPts, (p) => p.date) as [Date, Date])
        .range([0, innerW]);

    const yMax = d3.max(allPts, (p) => Math.max(p.hi, p.yhat)) ?? 1;
    const yMin = Math.min(
        0,
        d3.min(allPts, (p) => Math.min(p.lo, p.yhat)) ?? 0,
    );
    const y = d3.scaleLinear().domain([yMin, yMax]).nice().range([innerH, 0]);

    const lineGen = d3
        .line<Pt>()
        .x((p) => x(p.date))
        .y((p) => y(p.yhat))
        .curve(d3.curveMonotoneX);

    const areaGen = d3
        .area<Pt>()
        .x((p) => x(p.date))
        .y0((p) => y(p.lo))
        .y1((p) => y(p.hi))
        .curve(d3.curveMonotoneX);

    const xTicks = x.ticks(6);
    const yTicks = y.ticks(5);
    const fmt = d3.timeFormat('%d %b');
    const fmtFull = d3.timeFormat('%d %b %Y');
    const { tip, show, hide } = useChartTooltip();
    const [hoverX, setHoverX] = useState<number | null>(null);

    const sortedAll = useMemo(
        () => [...allPts].sort((a, b) => a.date.getTime() - b.date.getTime()),
        [allPts],
    );
    const bisect = d3.bisector<Pt, Date>((p) => p.date).left;

    function handleMove(e: MouseEvent<SVGRectElement>) {
        const rect = (
            e.currentTarget as SVGRectElement
        ).getBoundingClientRect();
        const px = e.clientX - rect.left;
        const date = x.invert(px);
        const idx = bisect(sortedAll, date);
        const p0 = sortedAll[Math.max(0, idx - 1)];
        const p1 = sortedAll[Math.min(sortedAll.length - 1, idx)];
        const pt = !p0
            ? p1
            : !p1
              ? p0
              : Math.abs(p0.date.getTime() - date.getTime()) <
                  Math.abs(p1.date.getTime() - date.getTime())
                ? p0
                : p1;
        if (!pt) return;
        setHoverX(x(pt.date));
        const isForecast = !!splitDate && pt.date > splitDate;
        const label = isForecast ? t('chart.forecast') : t('chart.history');
        const range = isForecast
            ? `\nIC 95%: ${Math.round(pt.lo).toLocaleString()} – ${Math.round(pt.hi).toLocaleString()}`
            : '';
        show(
            e,
            `${fmtFull(pt.date)}\n${label}: ${Math.round(pt.yhat).toLocaleString()} mention${range}`,
        );
    }

    function handleLeave() {
        setHoverX(null);
        hide();
    }

    return (
        <div
            style={{
                background: '#fff',
                border: '1px solid #ddd',
                padding: 16,
                marginTop: 16,
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
                {t('chart.timeline_title')} ({fc.method})
            </div>
            <div ref={ref} style={{ width: '100%', height }}>
                <svg width={size.width} height={height} role="img">
                    <g transform={`translate(${margin.left},${margin.top})`}>
                        {yTicks.map((t) => (
                            <g key={t} transform={`translate(0,${y(t)})`}>
                                <line x1={0} x2={innerW} stroke="#eee" />
                                <text
                                    x={-6}
                                    dy="0.32em"
                                    textAnchor="end"
                                    fontSize={10}
                                    fill="#888"
                                >
                                    {t}
                                </text>
                            </g>
                        ))}
                        {fore.length > 0 && (
                            <path
                                d={areaGen(fore) ?? ''}
                                fill="#2f6fb5"
                                fillOpacity={0.15}
                                stroke="none"
                            />
                        )}
                        {hist.length > 0 && (
                            <path
                                d={lineGen(hist) ?? ''}
                                fill="none"
                                stroke="#111"
                                strokeWidth={1.6}
                            />
                        )}
                        {fore.length > 0 && (
                            <path
                                d={lineGen(fore) ?? ''}
                                fill="none"
                                stroke="#2f6fb5"
                                strokeWidth={1.6}
                                strokeDasharray="5 4"
                            />
                        )}
                        {splitDate && (
                            <g transform={`translate(${x(splitDate)},0)`}>
                                <line
                                    y1={0}
                                    y2={innerH}
                                    stroke="#aa3a2b"
                                    strokeDasharray="3 3"
                                />
                                <text x={4} y={10} fontSize={10} fill="#aa3a2b">
                                    {t('chart.today')}
                                </text>
                            </g>
                        )}
                        <g transform={`translate(0,${innerH})`}>
                            <line x1={0} x2={innerW} stroke="#888" />
                            {xTicks.map((t, i) => (
                                <text
                                    key={i}
                                    x={x(t)}
                                    y={16}
                                    fontSize={10}
                                    fill="#666"
                                    textAnchor="middle"
                                >
                                    {fmt(t)}
                                </text>
                            ))}
                        </g>
                        {hoverX !== null && (
                            <line
                                x1={hoverX}
                                x2={hoverX}
                                y1={0}
                                y2={innerH}
                                stroke="#111"
                                strokeWidth={1}
                                strokeDasharray="2 2"
                                pointerEvents="none"
                            />
                        )}
                        <rect
                            x={0}
                            y={0}
                            width={innerW}
                            height={innerH}
                            fill="transparent"
                            onMouseMove={handleMove}
                            onMouseLeave={handleLeave}
                        />
                    </g>
                </svg>
            </div>
            <div
                style={{
                    display: 'flex',
                    gap: 16,
                    fontSize: 11,
                    color: '#555',
                    marginTop: 6,
                }}
            >
                <span>
                    <span
                        style={{
                            display: 'inline-block',
                            width: 18,
                            borderTop: '2px solid #111',
                            verticalAlign: 'middle',
                            marginRight: 4,
                        }}
                    />
                    {t('chart.history')}
                </span>
                <span>
                    <span
                        style={{
                            display: 'inline-block',
                            width: 18,
                            borderTop: '2px dashed #2f6fb5',
                            verticalAlign: 'middle',
                            marginRight: 4,
                        }}
                    />
                    {t('chart.forecast_ci')}
                </span>
                {fc.notes && (
                    <span style={{ color: '#888' }}>· {fc.notes}</span>
                )}
            </div>
            <ChartTooltip tip={tip} />
        </div>
    );
}
