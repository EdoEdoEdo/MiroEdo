'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { getReport } from '@/lib/api';
import { useT } from '@/lib/i18n';
import type { RunRecord } from '@/lib/types';
import Wizard from '@/components/Wizard';
import KpiGrid from '@/components/KpiGrid';
import ReportMarkdown from '@/components/ReportMarkdown';
import ActionPlanList from '@/components/ActionPlanList';
import DriverCards from '@/components/DriverCards';
import KnowledgeGraph from '@/components/KnowledgeGraph';
import ScenarioCards from '@/components/ScenarioCards';
import TimelineForecastChart from '@/components/TimelineForecastChart';
import SentimentDonut from '@/components/SentimentDonut';
import TopicTreemap from '@/components/TopicTreemap';
import GroupBarChart from '@/components/GroupBarChart';
import TopicSegmentHeatmap from '@/components/TopicSegmentHeatmap';
import OntologyPanel from '@/components/OntologyPanel';
import ZepQAPanel from '@/components/ZepQAPanel';

export default function ReportPage({
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

    const result = rec?.result;
    const simComplete =
        rec?.simulation_status === 'succeeded' || Boolean(result?.simulation);

    const downloadMd = () => {
        if (!result?.report_markdown) return;
        const blob = new Blob([result.report_markdown], {
            type: 'text/markdown',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `miroedo_${(rec?.brand ?? 'report').replace(/\s+/g, '_')}_${runId.slice(0, 8)}.md`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <main className="me-wizard">
            <Wizard runId={runId} current={4} done={simComplete ? 5 : 3} />
            <section className="me-wizard-body" style={{ padding: 0 }}>
                <div className="doc-header">
                    <div className="doc-query-label">
                        {t('report.title').toUpperCase()}
                    </div>
                    <h1 className="doc-query-title">{rec?.brand ?? '…'}</h1>
                    <div className="doc-meta-row">
                        <span>
                            <strong>{t('common.mode')}</strong> · {rec?.mode}
                        </span>
                        <span>
                            <strong>{t('common.run_id')}</strong> ·{' '}
                            {runId.slice(0, 12)}…
                        </span>
                        <span>
                            <strong>{t('common.created')}</strong> ·{' '}
                            {rec?.created_at?.slice(0, 16)}
                        </span>
                        <span>
                            <strong>{t('common.source')}</strong> ·{' '}
                            {rec?.source_filename ?? rec?.source_type}
                        </span>
                    </div>
                </div>

                {err && (
                    <div className="me-report" style={{ color: 'var(--red)' }}>
                        {err}
                    </div>
                )}
                {!err && rec && !result && (
                    <div className="me-report">
                        <p>{t('report.empty')}</p>
                        <Link
                            href={`/process/${runId}`}
                            className="me-btn ghost"
                        >
                            ← {t('sim.back')}
                        </Link>
                    </div>
                )}

                {!err && rec && result && !simComplete && (
                    <div className="me-report">
                        <h2>{t('report.locked_title')}</h2>
                        <p style={{ fontStyle: 'italic' }}>
                            {t('report.locked_body')}
                        </p>
                        <Link href={`/simulation/${runId}`} className="me-btn">
                            {t('report.go_sim_cta')}
                        </Link>
                    </div>
                )}

                {result && simComplete && (
                    <div className="me-report">
                        <KpiGrid result={result} />

                        <div
                            style={{
                                display: 'flex',
                                gap: 12,
                                flexWrap: 'wrap',
                                margin: '20px 0 28px',
                            }}
                        >
                            <button
                                type="button"
                                className="me-btn"
                                onClick={downloadMd}
                            >
                                ↓ {t('report.download_md')}
                            </button>
                            <button
                                type="button"
                                className="me-btn"
                                onClick={() => window.print()}
                            >
                                ↓ {t('report.download_pdf')}
                            </button>
                            <Link
                                href={`/interaction/${runId}`}
                                className="me-btn ghost"
                            >
                                {t('process.go_interaction')} →
                            </Link>
                            <Link href="/" className="me-btn ghost">
                                {t('common.back_home')}
                            </Link>
                        </div>

                        <h2>{t('report.summary_label')}</h2>
                        <p style={{ fontStyle: 'italic' }}>
                            {result.executive_summary.summary_it}
                        </p>
                        {result.executive_summary.highlights &&
                            result.executive_summary.highlights.length > 0 && (
                                <ul>
                                    {result.executive_summary.highlights.map(
                                        (h, i) => (
                                            <li key={i}>{h}</li>
                                        ),
                                    )}
                                </ul>
                            )}

                        <DriverCards drivers={result.scenario_drivers} />
                        <ActionPlanList plan={result.action_plan} />

                        <h2 style={{ marginTop: 36 }}>Snapshot dati</h2>
                        <p
                            style={{
                                fontStyle: 'italic',
                                color: '#555',
                                marginTop: 0,
                            }}
                        >
                            Distribuzione sentiment, topic share-of-voice, mix
                            piattaforme e geo.
                        </p>
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns:
                                    'repeat(auto-fit, minmax(320px, 1fr))',
                                gap: 16,
                                marginTop: 12,
                            }}
                        >
                            <SentimentDonut seed={result.brand_seed} />
                            <TopicTreemap seed={result.brand_seed} />
                            <GroupBarChart
                                title="Top piattaforme"
                                data={result.brand_seed.platforms}
                            />
                            <GroupBarChart
                                title="Top paesi"
                                data={result.brand_seed.countries}
                            />
                        </div>

                        <TopicSegmentHeatmap seed={result.brand_seed} />

                        <ScenarioCards set={result.scenarios} />
                        <TimelineForecastChart fc={result.volume_forecast} />

                        {result.ontology && (
                            <>
                                <h2 style={{ marginTop: 36 }}>
                                    Ontologia stakeholder
                                </h2>
                                <OntologyPanel ontology={result.ontology} />
                            </>
                        )}

                        {result.brand_seed.knowledge_graph &&
                            (result.brand_seed.knowledge_graph.nodes?.length ??
                                0) > 0 && (
                                <>
                                    <h2 style={{ marginTop: 36 }}>
                                        Knowledge graph
                                    </h2>
                                    <p
                                        style={{
                                            fontStyle: 'italic',
                                            color: '#555',
                                            marginTop: 0,
                                        }}
                                    >
                                        {result.brand_seed.knowledge_graph.stats
                                            ?.inferred
                                            ? 'Grafo dedotto dall\u2019ontologia AI (nessun dataset strutturato).'
                                            : 'Entità e relazioni estratte dal dataset: brand, topic, country, platform, autori, media outlet, hashtag.'}
                                    </p>
                                    <KnowledgeGraph
                                        graph={
                                            result.brand_seed.knowledge_graph
                                        }
                                    />
                                </>
                            )}

                        <ZepQAPanel qa={result.simulation?.zep_qa} />

                        {result.warnings && result.warnings.length > 0 && (
                            <>
                                <h3>{t('report.warnings')}</h3>
                                <ul>
                                    {result.warnings.map((w, i) => (
                                        <li key={i}>{w}</li>
                                    ))}
                                </ul>
                            </>
                        )}

                        <hr
                            style={{
                                margin: '32px 0',
                                border: 'none',
                                borderTop: '2px solid var(--ink)',
                            }}
                        />

                        <ReportMarkdown md={result.report_markdown} />
                    </div>
                )}
            </section>
        </main>
    );
}
