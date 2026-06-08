'use client';

import { useT } from '@/lib/i18n';
import type { ActionPlan } from '@/lib/types';

export default function ActionPlanList({ plan }: { plan: ActionPlan }) {
    const { t } = useT();
    if (!plan?.actions?.length) return null;
    return (
        <>
            <h3
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.2em',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    margin: '32px 0 12px',
                }}
            >
                {t('report.actions_label')}
                {plan.horizon_hours ? ` (${plan.horizon_hours}H)` : ''}
            </h3>
            <div className="me-actions-grid">
                {plan.actions.map((a, i) => {
                    const title = a.action || a.title || '—';
                    const desc = a.rationale || a.description;
                    const tf =
                        typeof a.timeframe_h === 'number'
                            ? `${a.timeframe_h}h`
                            : a.due_in;
                    const meta = [a.priority, tf, a.owner]
                        .filter(Boolean)
                        .join(' · ');
                    return (
                        <div key={i} className="me-action">
                            <span className="me-action-num">
                                {String(i + 1).padStart(2, '0')}
                            </span>
                            <div className="me-action-body">
                                <div className="me-action-title">{title}</div>
                                {desc && (
                                    <div className="me-action-desc">{desc}</div>
                                )}
                                {a.kpi_target && (
                                    <div
                                        style={{
                                            fontFamily: 'var(--mono)',
                                            fontSize: 10,
                                            color: 'var(--mid)',
                                            letterSpacing: '0.05em',
                                            marginTop: 6,
                                        }}
                                    >
                                        KPI · {a.kpi_target}
                                    </div>
                                )}
                                {a.expected_impact && (
                                    <div
                                        style={{
                                            fontSize: 12,
                                            color: '#444',
                                            marginTop: 4,
                                        }}
                                    >
                                        <strong>
                                            {t('action.expected_impact')}
                                        </strong>{' '}
                                        {a.expected_impact}
                                    </div>
                                )}
                                {a.targets_drivers &&
                                    a.targets_drivers.length > 0 && (
                                        <div
                                            style={{
                                                display: 'flex',
                                                flexWrap: 'wrap',
                                                gap: 6,
                                                marginTop: 8,
                                            }}
                                        >
                                            {a.targets_drivers.map((d, di) => (
                                                <span
                                                    key={di}
                                                    style={{
                                                        fontFamily:
                                                            'var(--mono)',
                                                        fontSize: 9,
                                                        letterSpacing: '0.1em',
                                                        textTransform:
                                                            'uppercase',
                                                        padding: '2px 6px',
                                                        border: '1px solid var(--ink)',
                                                        background: '#f5f5f5',
                                                    }}
                                                >
                                                    → {d}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                            </div>
                            <span className="me-action-meta">{meta}</span>
                        </div>
                    );
                })}
            </div>
        </>
    );
}
