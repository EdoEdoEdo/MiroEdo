'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { getReport } from '@/lib/api';
import { useT } from '@/lib/i18n';
import type { RunRecord } from '@/lib/types';
import Wizard from '@/components/Wizard';
import ReportChat from '@/components/ReportChat';

export default function InteractionPage({
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
        getReport(runId)
            .then((r) => {
                if (alive) setRec(r);
            })
            .catch((e: unknown) => {
                if (alive) setErr(e instanceof Error ? e.message : 'error');
            });
        return () => {
            alive = false;
        };
    }, [runId]);

    const simComplete =
        rec?.simulation_status === 'succeeded' ||
        Boolean(rec?.result?.simulation);
    const ready =
        rec?.status === 'succeeded' &&
        !!rec.result?.report_markdown &&
        simComplete;

    return (
        <main className="me-wizard">
            <Wizard runId={runId} current={5} done={simComplete ? 5 : 3} />
            <section className="me-wizard-body">
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

                {!err && !rec && (
                    <div className="me-stub">
                        <div className="me-stub-sub">
                            {t('process.loading')}
                        </div>
                    </div>
                )}

                {rec && !ready && (
                    <div className="me-stub">
                        <div className="me-stub-eyebrow">
                            STATUS · {rec.status.toUpperCase()}
                        </div>
                        <h1 className="me-stub-title">{t('report.empty')}</h1>
                        <div
                            style={{ marginTop: 28, display: 'flex', gap: 12 }}
                        >
                            <Link href={`/process/${runId}`} className="me-btn">
                                ← {t('sim.back')}
                            </Link>
                            {rec.status === 'succeeded' && !simComplete && (
                                <Link
                                    href={`/simulation/${runId}`}
                                    className="me-btn ghost"
                                >
                                    VAI ALLA SIMULAZIONE →
                                </Link>
                            )}
                        </div>
                    </div>
                )}

                {ready && rec && (
                    <>
                        <div style={{ marginBottom: 24 }}>
                            <div
                                style={{
                                    fontFamily: 'var(--mono)',
                                    fontSize: 9,
                                    letterSpacing: '0.2em',
                                    textTransform: 'uppercase',
                                    color: 'var(--red)',
                                    marginBottom: 10,
                                }}
                            >
                                STEP 05 · INTERACTION
                            </div>
                            <h1
                                style={{
                                    fontFamily: 'var(--display)',
                                    fontSize: 'clamp(36px, 5vw, 72px)',
                                    lineHeight: 0.95,
                                }}
                            >
                                {t('interaction.title')}
                            </h1>
                        </div>

                        <ReportChat
                            runId={runId}
                            brand={rec.brand}
                            suggestions={[
                                t('interaction.sug.sentiment'),
                                t('interaction.sug.topic'),
                                t('interaction.sug.actions'),
                                ...(rec.result?.simulation
                                    ? [t('interaction.sug.sim')]
                                    : []),
                            ]}
                        />

                        <div
                            style={{
                                marginTop: 28,
                                display: 'flex',
                                gap: 12,
                                flexWrap: 'wrap',
                            }}
                        >
                            <Link
                                href={`/report/${runId}`}
                                className="me-btn ghost"
                            >
                                ← {t('process.go_report')}
                            </Link>
                            <Link href="/" className="me-btn ghost">
                                {t('common.back_home')}
                            </Link>
                        </div>
                    </>
                )}
            </section>
        </main>
    );
}
