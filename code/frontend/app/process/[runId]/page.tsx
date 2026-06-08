'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { getReport } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { formatDateTime } from '@/lib/format';
import type { RunRecord } from '@/lib/types';
import Wizard from '@/components/Wizard';
import StatusBadge from '@/components/StatusBadge';
import ProgressLive from '@/components/ProgressLive';
import IngestLiveCards from '@/components/IngestLiveCards';

const STEP_TO_WIZARD: Record<string, 1 | 2 | 3 | 4 | 5> = {
    ingest: 2,
    baseline_report: 2,
    simulation: 3,
    kpi: 4,
    executive_summary: 4,
    action_plan: 4,
};

export default function ProcessPage({
    params,
}: {
    params: Promise<{ runId: string }>;
}) {
    const { runId } = use(params);
    const { t } = useT();
    const [rec, setRec] = useState<RunRecord | null>(null);
    const [err, setErr] = useState<string | null>(null);

    useEffect(() => {
        let alive = true;
        let stop = false;
        const tick = async () => {
            try {
                const r = await getReport(runId);
                if (!alive) return;
                setRec(r);
                if (r.status === 'succeeded' || r.status === 'failed') {
                    stop = true;
                    return;
                }
            } catch (e: unknown) {
                if (alive) setErr(e instanceof Error ? e.message : 'error');
            }
            if (!stop && alive) setTimeout(tick, 2000);
        };
        tick();
        return () => {
            alive = false;
            stop = true;
        };
    }, [runId]);

    const current: 1 | 2 | 3 | 4 | 5 = 2; // we're on the SETUP / process page
    const done = (() => {
        if (!rec) return 1;
        if (rec.simulation_status === 'succeeded') return 5;
        if (
            rec.simulation_status === 'running' ||
            rec.simulation_status === 'pending'
        )
            return 3;
        if (rec.status === 'succeeded') return 2;
        const step = rec.progress?.step ?? '';
        return STEP_TO_WIZARD[step] ?? 2;
    })();

    return (
        <main className="me-wizard">
            <Wizard runId={runId} current={current} done={done} />
            <section className="me-wizard-body">
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: 16,
                        alignItems: 'flex-end',
                        marginBottom: 28,
                    }}
                >
                    <div>
                        <div
                            style={{
                                fontFamily: 'var(--mono)',
                                fontSize: 9,
                                letterSpacing: '0.2em',
                                textTransform: 'uppercase',
                                color: 'var(--red)',
                                marginBottom: 12,
                            }}
                        >
                            {t('process.eyebrow')} · {runId.slice(0, 12)}…
                        </div>
                        <h1
                            style={{
                                fontFamily: 'var(--display)',
                                fontSize: 'clamp(40px, 6vw, 96px)',
                                lineHeight: 0.95,
                            }}
                        >
                            {rec?.brand ?? t('process.loading')}
                        </h1>
                    </div>
                    {rec && <StatusBadge status={rec.status} />}
                </div>

                {err && (
                    <div
                        style={{
                            color: 'var(--red)',
                            fontFamily: 'var(--mono)',
                            fontSize: 12,
                        }}
                    >
                        {err}
                    </div>
                )}

                {rec && (
                    <div
                        style={{
                            display: 'grid',
                            gridTemplateColumns:
                                'repeat(auto-fit, minmax(160px, 1fr))',
                            border: '1px solid var(--ink)',
                            marginBottom: 32,
                            maxWidth: 920,
                        }}
                    >
                        <Meta label={t('common.brand')} value={rec.brand} />
                        <Meta
                            label={t('common.mode')}
                            value={rec.mode.toUpperCase()}
                        />
                        <Meta
                            label={t('common.source')}
                            value={rec.source_type}
                        />
                        <Meta
                            label={t('common.created')}
                            value={formatDateTime(rec.created_at)}
                        />
                    </div>
                )}

                {rec &&
                    (rec.status === 'queued' || rec.status === 'running') && (
                        <ProgressLive runId={runId} />
                    )}

                {rec && (
                    <IngestLiveCards
                        preview={
                            (rec.progress as { ingest_preview?: unknown })
                                ?.ingest_preview as never
                        }
                    />
                )}

                {rec?.status === 'succeeded' && (
                    <div
                        style={{
                            display: 'flex',
                            gap: 12,
                            flexWrap: 'wrap',
                            marginTop: 16,
                        }}
                    >
                        <Link href={`/simulation/${runId}`} className="me-btn">
                            {rec.simulation_status === 'succeeded'
                                ? t('process.go_sim')
                                : `${t('process.go_sim')} →`}
                        </Link>
                        {rec.simulation_status === 'succeeded' && (
                            <>
                                <Link
                                    href={`/report/${runId}`}
                                    className="me-btn ghost"
                                >
                                    {t('process.go_report')} →
                                </Link>
                                <Link
                                    href={`/interaction/${runId}`}
                                    className="me-btn ghost"
                                >
                                    {t('process.go_interaction')}
                                </Link>
                            </>
                        )}
                        {rec.simulation_status !== 'succeeded' && (
                            <div
                                style={{
                                    fontFamily: 'var(--serif)',
                                    fontStyle: 'italic',
                                    color: '#444',
                                    alignSelf: 'center',
                                }}
                            >
                                {t('sim.report_unlocks')}
                            </div>
                        )}
                    </div>
                )}

                {rec?.status === 'failed' && rec.error && (
                    <div
                        style={{
                            border: '2px solid var(--red)',
                            padding: 16,
                            marginTop: 16,
                            fontFamily: 'var(--mono)',
                            fontSize: 12,
                            color: 'var(--red)',
                            maxWidth: 920,
                        }}
                    >
                        ERROR: {rec.error}
                    </div>
                )}

                {rec?.result?.warnings && rec.result.warnings.length > 0 && (
                    <div style={{ marginTop: 24 }}>
                        <h3
                            style={{
                                fontFamily: 'var(--mono)',
                                fontSize: 10,
                                letterSpacing: '0.2em',
                                textTransform: 'uppercase',
                                color: 'var(--mid)',
                                marginBottom: 10,
                            }}
                        >
                            {t('process.warnings')}
                        </h3>
                        <ul
                            style={{
                                paddingLeft: 22,
                                fontFamily: 'var(--serif)',
                                fontSize: 13,
                                color: '#444',
                            }}
                        >
                            {rec.result.warnings.map((w, i) => (
                                <li key={i}>{w}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </section>
        </main>
    );
}

function Meta({ label, value }: { label: string; value: string }) {
    return (
        <div
            style={{
                padding: '12px 16px',
                borderRight: '1px solid var(--ink)',
            }}
        >
            <div
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 9,
                    letterSpacing: '0.15em',
                    textTransform: 'uppercase',
                    color: 'var(--mid)',
                    marginBottom: 4,
                }}
            >
                {label}
            </div>
            <div
                style={{
                    fontFamily: 'var(--cond)',
                    fontWeight: 700,
                    fontSize: 16,
                    textTransform: 'uppercase',
                }}
            >
                {value}
            </div>
        </div>
    );
}
