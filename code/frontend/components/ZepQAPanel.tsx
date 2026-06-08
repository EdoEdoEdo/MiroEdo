'use client';

import { useT } from '../lib/i18n';
import type { SimulationSummary } from '../lib/types';

/**
 * Renders the LLM-synthesised Q&A panel on Zep brand graph.
 * Each Q&A shows the question, the LLM answer, and the supporting facts.
 */
export default function ZepQAPanel({
    qa,
}: {
    qa: SimulationSummary['zep_qa'] | undefined;
}) {
    const { t } = useT();
    if (!qa || qa.status !== 'ok' || qa.questions.length === 0) return null;

    return (
        <div style={{ marginTop: 32 }}>
            <h2 style={{ margin: '0 0 6px' }}>{t('zepqa.title')}</h2>
            <p
                style={{
                    fontStyle: 'italic',
                    color: '#555',
                    marginTop: 0,
                    fontSize: 14,
                }}
            >
                {t('zepqa.subtitle')}
            </p>

            <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
                {qa.questions.map((q, i) => (
                    <div
                        key={i}
                        style={{
                            border: '1px solid var(--ink)',
                            background: '#fff',
                            padding: 16,
                        }}
                    >
                        <div
                            style={{
                                fontFamily: 'var(--mono)',
                                fontSize: 10,
                                letterSpacing: '0.18em',
                                color: 'var(--red)',
                                marginBottom: 6,
                            }}
                        >
                            {t('zepqa.question')}{' '}
                            {String(i + 1).padStart(2, '0')}
                        </div>
                        <div
                            style={{
                                fontFamily: 'var(--serif)',
                                fontWeight: 600,
                                fontSize: 15,
                                color: '#111',
                                marginBottom: 10,
                                lineHeight: 1.35,
                            }}
                        >
                            {q.question}
                        </div>
                        <div
                            style={{
                                fontFamily: 'var(--sans)',
                                fontSize: 14,
                                color: '#222',
                                lineHeight: 1.5,
                                whiteSpace: 'pre-wrap',
                            }}
                        >
                            {q.answer}
                        </div>
                        {q.facts.length > 0 && (
                            <details style={{ marginTop: 10 }}>
                                <summary
                                    style={{
                                        cursor: 'pointer',
                                        fontFamily: 'var(--mono)',
                                        fontSize: 11,
                                        color: '#666',
                                    }}
                                >
                                    {q.fact_count} {t('zepqa.facts_support')}
                                </summary>
                                <ul
                                    style={{
                                        margin: '6px 0 0',
                                        paddingLeft: 18,
                                        fontSize: 12,
                                        color: '#555',
                                        fontFamily: 'var(--mono)',
                                    }}
                                >
                                    {q.facts.map((f, j) => (
                                        <li key={j} style={{ marginBottom: 3 }}>
                                            {f}
                                        </li>
                                    ))}
                                </ul>
                            </details>
                        )}
                    </div>
                ))}
            </div>
            {qa.model && (
                <div
                    style={{
                        marginTop: 10,
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        color: '#888',
                    }}
                >
                    {t('zepqa.synthesis')} · {qa.model}
                </div>
            )}
        </div>
    );
}
