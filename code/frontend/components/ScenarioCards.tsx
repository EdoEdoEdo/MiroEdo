'use client';

import type { ScenarioSet } from '@/lib/types';

const LABEL_META: Record<
    string,
    { icon: string; color: string; title: string }
> = {
    best: { icon: '🟢', color: '#137b3a', title: 'Best case' },
    base: { icon: '🟡', color: '#a87a00', title: 'Base case' },
    worst: { icon: '🔴', color: '#b8332b', title: 'Worst case' },
};

export default function ScenarioCards({
    set,
}: {
    set: ScenarioSet | null | undefined;
}) {
    if (!set || !set.scenarios?.length) return null;
    return (
        <>
            <h2 style={{ marginTop: 36 }}>
                Scenari prospettici ({set.horizon_weeks} settimane)
            </h2>
            <p style={{ fontStyle: 'italic', color: '#555', marginTop: 0 }}>
                Tre traiettorie qualitative generate da LLM su dati canonici e
                scenario di business.
                {set.model ? ` Generato da ${set.model}.` : ''}
            </p>
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 16,
                    marginTop: 16,
                }}
            >
                {set.scenarios.map((s) => {
                    const meta = LABEL_META[s.label] ?? LABEL_META.base;
                    return (
                        <div
                            key={s.label}
                            style={{
                                border: '1px solid #ddd',
                                borderTop: `4px solid ${meta.color}`,
                                padding: 16,
                                background: '#fff',
                            }}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'baseline',
                                    marginBottom: 8,
                                }}
                            >
                                <span
                                    style={{
                                        fontFamily: 'var(--mono)',
                                        fontSize: 10,
                                        letterSpacing: '0.2em',
                                        textTransform: 'uppercase',
                                        color: meta.color,
                                    }}
                                >
                                    {meta.icon} {meta.title}
                                </span>
                                <span
                                    style={{
                                        fontFamily: 'var(--mono)',
                                        fontSize: 14,
                                        fontWeight: 600,
                                    }}
                                >
                                    {Math.round(s.probability * 100)}%
                                </span>
                            </div>
                            <h3 style={{ margin: '4px 0 12px', fontSize: 16 }}>
                                {s.title}
                            </h3>
                            <p
                                style={{
                                    fontSize: 13,
                                    lineHeight: 1.55,
                                    marginTop: 0,
                                }}
                            >
                                {s.narrative}
                            </p>
                            {s.drivers?.length > 0 && (
                                <div style={{ marginTop: 12 }}>
                                    <div
                                        style={{
                                            fontFamily: 'var(--mono)',
                                            fontSize: 10,
                                            letterSpacing: '0.15em',
                                            textTransform: 'uppercase',
                                            color: '#666',
                                            marginBottom: 4,
                                        }}
                                    >
                                        Driver
                                    </div>
                                    <ul
                                        style={{
                                            margin: 0,
                                            paddingLeft: 18,
                                            fontSize: 12,
                                        }}
                                    >
                                        {s.drivers.map((d, i) => (
                                            <li key={i}>{d}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {s.early_signals?.length > 0 && (
                                <div style={{ marginTop: 10 }}>
                                    <div
                                        style={{
                                            fontFamily: 'var(--mono)',
                                            fontSize: 10,
                                            letterSpacing: '0.15em',
                                            textTransform: 'uppercase',
                                            color: '#666',
                                            marginBottom: 4,
                                        }}
                                    >
                                        Early signals
                                    </div>
                                    <ul
                                        style={{
                                            margin: 0,
                                            paddingLeft: 18,
                                            fontSize: 12,
                                        }}
                                    >
                                        {s.early_signals.map((sig, i) => (
                                            <li key={i}>{sig}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </>
    );
}
