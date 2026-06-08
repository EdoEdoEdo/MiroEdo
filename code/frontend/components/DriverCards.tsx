'use client';

import { useT } from '@/lib/i18n';
import type { ScenarioDriver, ScenarioDriversSet } from '@/lib/types';

const STRENGTH_META: Record<
    ScenarioDriver['strength'],
    { glyph: string; label: string; color: string }
> = {
    high: { glyph: '●', label: 'ALTA', color: 'var(--red, #C8102E)' },
    medium: { glyph: '●', label: 'MEDIA', color: '#E0A800' },
    low: { glyph: '○', label: 'BASSA', color: '#888' },
};

function fmtSent(v: number): string {
    if (typeof v !== 'number' || Number.isNaN(v)) return '—';
    const s = v > 0 ? '+' : '';
    return `${s}${v.toFixed(2)}`;
}

export default function DriverCards({
    drivers,
}: {
    drivers?: ScenarioDriversSet | null;
}) {
    if (!drivers?.drivers?.length) return null;
    return (
        <>
            <h3
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.2em',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    margin: '32px 0 6px',
                }}
            >
                Driver osservati
                {drivers.scenario_focus
                    ? ` · risposta a: «${drivers.scenario_focus}»`
                    : ''}
            </h3>
            <p
                style={{
                    fontStyle: 'italic',
                    color: '#555',
                    margin: '0 0 12px',
                }}
            >
                Fattori inferiti dall&apos;analisi semantica del corpus social,
                ancorati a topic, mention e sentiment del dataset.
            </p>
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 12,
                }}
            >
                {drivers.drivers.map((d, i) => {
                    const meta = STRENGTH_META[d.strength] ?? STRENGTH_META.low;
                    return (
                        <div
                            key={i}
                            style={{
                                border: '1px solid var(--ink)',
                                padding: '14px 16px',
                                background: '#fff',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 8,
                            }}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 8,
                                }}
                            >
                                <span
                                    style={{
                                        color: meta.color,
                                        fontSize: 14,
                                    }}
                                    aria-hidden
                                >
                                    {meta.glyph}
                                </span>
                                <span
                                    style={{
                                        fontFamily: 'var(--mono)',
                                        fontSize: 9,
                                        letterSpacing: '0.18em',
                                        color: meta.color,
                                    }}
                                >
                                    {meta.label}
                                </span>
                            </div>
                            <div
                                style={{
                                    fontWeight: 600,
                                    fontSize: 15,
                                    lineHeight: 1.3,
                                }}
                            >
                                {d.label}
                            </div>
                            <div
                                style={{
                                    fontFamily: 'var(--mono)',
                                    fontSize: 10,
                                    color: 'var(--mid)',
                                    letterSpacing: '0.05em',
                                }}
                            >
                                {d.evidence_topic
                                    ? `${d.evidence_topic} · `
                                    : ''}
                                {d.mentions.toLocaleString()} mention ·
                                sentiment {fmtSent(d.sentiment)}
                            </div>
                            {d.rationale && (
                                <div
                                    style={{
                                        fontSize: 13,
                                        lineHeight: 1.45,
                                        color: '#222',
                                    }}
                                >
                                    {d.rationale}
                                </div>
                            )}
                            {d.sample_quotes && d.sample_quotes.length > 0 && (
                                <div
                                    style={{
                                        borderLeft: '2px solid var(--ink)',
                                        paddingLeft: 10,
                                        marginTop: 4,
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: 4,
                                    }}
                                >
                                    {d.sample_quotes
                                        .slice(0, 2)
                                        .map((q, qi) => (
                                            <div
                                                key={qi}
                                                style={{
                                                    fontStyle: 'italic',
                                                    fontSize: 12,
                                                    color: '#555',
                                                    lineHeight: 1.4,
                                                }}
                                            >
                                                «{q}»
                                            </div>
                                        ))}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
            {(drivers.notes || drivers.model) && (
                <p
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        color: 'var(--mid)',
                        marginTop: 10,
                        letterSpacing: '0.05em',
                    }}
                >
                    {drivers.notes && <>{drivers.notes} · </>}
                    {drivers.model && <>model: {drivers.model}</>}
                </p>
            )}
        </>
    );
}
