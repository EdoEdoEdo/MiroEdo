'use client';

import { useT } from '../lib/i18n';
import type { Ontology } from '../lib/types';

/**
 * Displays the LLM-generated stakeholder ontology: entity types + relations.
 * Renders nothing when ontology is missing or empty.
 */
export default function OntologyPanel({
    ontology,
}: {
    ontology: Ontology | null | undefined;
}) {
    const { t } = useT();
    if (!ontology || ontology.status !== 'ok') return null;
    const entities = ontology.entity_types ?? [];
    const edges = ontology.edge_types ?? [];
    if (entities.length === 0) return null;

    return (
        <div style={{ marginTop: 16 }}>
            <div
                style={{
                    display: 'flex',
                    gap: 10,
                    alignItems: 'baseline',
                    flexWrap: 'wrap',
                    marginBottom: 8,
                }}
            >
                <span
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 9,
                        letterSpacing: '0.2em',
                        textTransform: 'uppercase',
                        color: 'var(--red)',
                    }}
                >
                    AI-INFERRED
                </span>
                <span style={{ fontSize: 12, color: '#666' }}>
                    Ontologia di stakeholder dedotta da LLM, non dal dataset.
                </span>
            </div>
            {ontology.analysis_summary && (
                <p
                    style={{
                        fontStyle: 'italic',
                        color: '#444',
                        margin: '0 0 16px',
                        fontSize: 14,
                        lineHeight: 1.5,
                    }}
                >
                    {ontology.analysis_summary}
                </p>
            )}

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                    gap: 12,
                }}
            >
                {entities.map((e) => (
                    <div
                        key={e.name}
                        style={{
                            border: '1px solid var(--ink)',
                            padding: 12,
                            background: '#fff',
                            fontFamily: 'var(--sans)',
                        }}
                    >
                        <div
                            style={{
                                fontFamily: 'var(--mono)',
                                fontSize: 11,
                                letterSpacing: '0.08em',
                                color: '#111',
                                fontWeight: 700,
                            }}
                        >
                            {e.name}
                        </div>
                        {e.description && (
                            <div
                                style={{
                                    fontSize: 12,
                                    color: '#444',
                                    marginTop: 4,
                                    lineHeight: 1.4,
                                }}
                            >
                                {e.description}
                            </div>
                        )}
                        {e.examples && e.examples.length > 0 && (
                            <div
                                style={{
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: 4,
                                    marginTop: 6,
                                }}
                            >
                                {e.examples.map((x, i) => (
                                    <span
                                        key={i}
                                        style={{
                                            fontSize: 10,
                                            background: '#f0ebe0',
                                            border: '1px solid #d4cdbe',
                                            padding: '1px 6px',
                                            fontFamily: 'var(--mono)',
                                            color: '#555',
                                        }}
                                    >
                                        {x}
                                    </span>
                                ))}
                            </div>
                        )}
                        {e.role_in_simulation && (
                            <div
                                style={{
                                    fontSize: 11,
                                    color: '#666',
                                    marginTop: 6,
                                    fontStyle: 'italic',
                                }}
                            >
                                {e.role_in_simulation}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {edges.length > 0 && (
                <div style={{ marginTop: 16 }}>
                    <div
                        style={{
                            fontFamily: 'var(--mono)',
                            fontSize: 10,
                            letterSpacing: '0.2em',
                            textTransform: 'uppercase',
                            color: 'var(--mid)',
                            marginBottom: 6,
                        }}
                    >
                        Relazioni
                    </div>
                    <div
                        style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: 8,
                        }}
                    >
                        {edges.map((ed) => (
                            <div
                                key={ed.name}
                                style={{
                                    fontFamily: 'var(--mono)',
                                    fontSize: 11,
                                    padding: '6px 10px',
                                    border: '1px dashed #888',
                                    background: '#fafafa',
                                    color: '#333',
                                }}
                                title={ed.description}
                            >
                                <span style={{ color: 'var(--red)' }}>
                                    {ed.name}
                                </span>
                                {ed.source_targets.length > 0 && (
                                    <span style={{ color: '#666' }}>
                                        {' '}
                                        ·{' '}
                                        {ed.source_targets
                                            .slice(0, 3)
                                            .map(
                                                (p) =>
                                                    `${p.source}→${p.target}`,
                                            )
                                            .join(', ')}
                                        {ed.source_targets.length > 3 && '…'}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
            {ontology.model && (
                <div
                    style={{
                        marginTop: 12,
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        color: '#888',
                    }}
                >
                    {t('ontology.model_label')} {ontology.model}
                </div>
            )}
        </div>
    );
}
