'use client';

import Link from 'next/link';
import { use, useCallback, useEffect, useRef, useState } from 'react';
import {
    DATA_SOURCE,
    getReport,
    listLLMModels,
    runSimulation,
    type LLMModelInfo,
} from '@/lib/api';
import { useT } from '@/lib/i18n';
import type { RunRecord, SimulationSummary } from '@/lib/types';
import Wizard from '@/components/Wizard';
import LiveSimulation from '@/components/LiveSimulation';
import SamplePostsPanel from '@/components/SamplePostsPanel';

const OASIS_MODEL_OPTIONS = [
    {
        model: 'gpt-4o',
        label: 'GPT-4o',
        provider: 'openai',
    },
    {
        model: 'gpt-4o-mini',
        label: 'GPT-4o mini',
        provider: 'openai',
    },
    {
        model: 'llama-3.3-70b-versatile',
        label: 'Llama 3.3 70B (Groq)',
        provider: 'groq',
    },
    {
        model: 'llama-3.1-8b-instant',
        label: 'Llama 3.1 8B (Groq)',
        provider: 'groq',
    },
] as const;

export default function SimulationPage({
    params,
}: {
    params: Promise<{ runId: string }>;
}) {
    const { runId } = use(params);
    const { t } = useT();
    const [rec, setRec] = useState<RunRecord | null>(null);
    const [profiles, setProfiles] = useState<number>(120);
    const [rounds, setRounds] = useState<number>(10);
    const [model, setModel] = useState<string>('gpt-4o');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const refresh = useCallback(async () => {
        try {
            const r = await getReport(runId);
            setRec(r);
            return r;
        } catch {
            return null;
        }
    }, [runId]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const simStatus = rec?.simulation_status ?? 'idle';

    useEffect(() => {
        if (simStatus === 'running' || simStatus === 'pending') {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = setInterval(refresh, 3000);
            return () => {
                if (pollRef.current) {
                    clearInterval(pollRef.current);
                    pollRef.current = null;
                }
            };
        }
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, [simStatus, refresh]);

    const onLaunch = useCallback(async () => {
        setError(null);
        setSubmitting(true);
        try {
            const updated = await runSimulation(runId, {
                profiles,
                rounds,
                model,
            });
            setRec(updated);
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setSubmitting(false);
        }
    }, [runId, profiles, rounds, model]);

    const sim: SimulationSummary | null | undefined = rec?.result?.simulation;
    const baseReady = rec?.status === 'succeeded';

    return (
        <main className="me-wizard">
            <Wizard
                runId={runId}
                current={3}
                done={simStatus === 'succeeded' ? 5 : 3}
            />
            <section className="me-wizard-body">
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
                    {t('sim.eyebrow_step')}
                </div>
                <h1
                    style={{
                        fontFamily: 'var(--display)',
                        fontSize: 'clamp(40px, 6vw, 88px)',
                        lineHeight: 0.95,
                        marginBottom: 12,
                    }}
                >
                    {t('sim.title')}
                </h1>
                <p
                    style={{
                        fontFamily: 'var(--serif)',
                        fontStyle: 'italic',
                        color: '#333',
                        maxWidth: 620,
                        fontSize: 16,
                        marginBottom: 28,
                    }}
                >
                    {t('sim.sub')}
                </p>

                {!baseReady && (
                    <div
                        style={{
                            border: '2px dashed var(--ink)',
                            padding: 24,
                            fontFamily: 'var(--serif)',
                            fontStyle: 'italic',
                            color: '#444',
                            maxWidth: 720,
                        }}
                    >
                        {t('sim.base_not_ready')}
                    </div>
                )}

                {baseReady && simStatus === 'idle' && (
                    <SimulationLauncher
                        profiles={profiles}
                        rounds={rounds}
                        model={model}
                        onProfiles={setProfiles}
                        onRounds={setRounds}
                        onModel={setModel}
                        onLaunch={onLaunch}
                        submitting={submitting}
                        error={error}
                    />
                )}

                {(simStatus === 'pending' || simStatus === 'running') && (
                    <>
                        <RunningPanel progress={rec?.simulation_progress} />
                        <ActionBar runId={runId} showReport={false} t={t} />
                        <LiveSimulation
                            runId={runId}
                            simStatus={simStatus}
                            sim={sim ?? null}
                        />
                    </>
                )}

                {simStatus === 'failed' && (
                    <div
                        style={{
                            border: '2px solid var(--red)',
                            padding: 24,
                            maxWidth: 720,
                            marginBottom: 24,
                        }}
                    >
                        <div
                            style={{
                                fontFamily: 'var(--mono)',
                                fontSize: 10,
                                letterSpacing: '0.2em',
                                color: 'var(--red)',
                                marginBottom: 8,
                            }}
                        >
                            {t('sim.failed_label')}
                        </div>
                        <div
                            style={{
                                fontFamily: 'var(--serif)',
                                marginBottom: 16,
                            }}
                        >
                            {rec?.simulation_error ?? t('sim.unknown_error')}
                        </div>
                        <button
                            type="button"
                            className="me-btn ghost"
                            onClick={onLaunch}
                            disabled={submitting}
                        >
                            {t('sim.retry')}
                        </button>
                    </div>
                )}

                {sim && simStatus === 'succeeded' && (
                    <>
                        <div
                            className="me-kpi-grid"
                            style={{
                                gridTemplateColumns: 'repeat(3, 1fr)',
                                maxWidth: 720,
                            }}
                        >
                            <KpiCell
                                label={t('sim.kpi_profiles')}
                                value={sim.profiles_count ?? 0}
                            />
                            <KpiCell
                                label={t('sim.kpi_actions')}
                                value={sim.total_actions ?? 0}
                            />
                            <KpiCell
                                label={t('sim.kpi_zep')}
                                value={(
                                    sim.zep?.status ?? 'skipped'
                                ).toUpperCase()}
                            />
                        </div>
                        <ActionBar runId={runId} showReport t={t} />
                        <LiveSimulation
                            runId={runId}
                            simStatus={simStatus}
                            sim={sim}
                        />
                        <SamplePostsPanel sim={sim} />
                    </>
                )}
            </section>
        </main>
    );
}

function ActionBar({
    runId,
    showReport,
    t,
}: {
    runId: string;
    showReport: boolean;
    t: (key: string) => string;
}) {
    return (
        <div
            style={{
                display: 'flex',
                gap: 12,
                flexWrap: 'wrap',
                margin: '12px 0 20px',
            }}
        >
            <Link href={`/process/${runId}`} className="me-btn ghost">
                ← {t('sim.back')}
            </Link>
            {showReport && (
                <Link href={`/report/${runId}`} className="me-btn">
                    {t('sim.open_report_cta')}
                </Link>
            )}
        </div>
    );
}

function SimulationLauncher({
    profiles,
    rounds,
    model,
    onProfiles,
    onRounds,
    onModel,
    onLaunch,
    submitting,
    error,
}: {
    profiles: number;
    rounds: number;
    model: string;
    onProfiles: (n: number) => void;
    onRounds: (n: number) => void;
    onModel: (model: string) => void;
    onLaunch: () => void;
    submitting: boolean;
    error: string | null;
}) {
    const { t } = useT();
    const [catalog, setCatalog] = useState<LLMModelInfo[]>([]);

    useEffect(() => {
        listLLMModels()
            .then(setCatalog)
            .catch(() => setCatalog([]));
    }, []);

    const isModelAvailable = useCallback(
        (candidate: (typeof OASIS_MODEL_OPTIONS)[number]) => {
            if (DATA_SOURCE === 'mock') return candidate.model === 'gpt-4o';
            if (catalog.length === 0) return true;
            const available = catalog.filter((m) => m.available);
            return available.some(
                (m) =>
                    m.model === candidate.model ||
                    m.provider === candidate.provider,
            );
        },
        [catalog],
    );

    useEffect(() => {
        if (DATA_SOURCE === 'mock') {
            if (model !== 'gpt-4o') onModel('gpt-4o');
            return;
        }
        if (catalog.length === 0) return;
        const current = OASIS_MODEL_OPTIONS.find((o) => o.model === model);
        if (current && isModelAvailable(current)) return;
        const firstAvailable = OASIS_MODEL_OPTIONS.find(isModelAvailable);
        if (firstAvailable) onModel(firstAvailable.model);
    }, [catalog, isModelAvailable, model, onModel]);

    return (
        <div
            style={{
                border: '2px solid var(--ink)',
                padding: 24,
                maxWidth: 720,
                marginBottom: 24,
            }}
        >
            <div
                style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.2em',
                    marginBottom: 16,
                }}
            >
                {t('sim.config_title')}
            </div>
            <div
                className="me-form-grid"
                style={{
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                }}
            >
                <label className="me-field">
                    <span className="me-field-label">
                        {t('sim.field_agents')}
                    </span>
                    <input
                        className="me-field-input"
                        type="number"
                        min={3}
                        max={120}
                        step={1}
                        value={profiles}
                        onChange={(e) =>
                            onProfiles(
                                Math.max(
                                    3,
                                    Math.min(120, Number(e.target.value) || 40),
                                ),
                            )
                        }
                    />
                    <span className="me-field-hint">
                        {t('sim.field_agents_hint')}
                    </span>
                </label>
                <label className="me-field">
                    <span className="me-field-label">
                        {t('sim.field_rounds')}
                    </span>
                    <input
                        className="me-field-input"
                        type="number"
                        min={1}
                        max={10}
                        step={1}
                        value={rounds}
                        onChange={(e) =>
                            onRounds(
                                Math.max(
                                    1,
                                    Math.min(10, Number(e.target.value) || 4),
                                ),
                            )
                        }
                    />
                    <span className="me-field-hint">
                        {t('sim.field_rounds_hint')}
                    </span>
                </label>
                <label className="me-field">
                    <span className="me-field-label">
                        {t('sim.field_model')}
                    </span>
                    <select
                        className="me-field-select"
                        value={model}
                        onChange={(e) => onModel(e.target.value)}
                        disabled={DATA_SOURCE === 'mock'}
                    >
                        {OASIS_MODEL_OPTIONS.map((option) => (
                            <option
                                key={option.model}
                                value={option.model}
                                disabled={!isModelAvailable(option)}
                            >
                                {option.label}
                            </option>
                        ))}
                    </select>
                    <span className="me-field-hint">
                        {DATA_SOURCE === 'mock'
                            ? t('sim.field_model_hint_static')
                            : t('sim.field_model_hint')}
                    </span>
                </label>
            </div>
            {error && (
                <div
                    style={{
                        color: 'var(--red)',
                        fontFamily: 'var(--mono)',
                        fontSize: 12,
                        marginTop: 16,
                    }}
                >
                    {error}
                </div>
            )}
            <button
                type="button"
                className="me-btn"
                onClick={onLaunch}
                disabled={submitting}
                style={{ marginTop: 20 }}
            >
                {submitting ? t('sim.starting') : t('sim.launch_cta')}
            </button>
        </div>
    );
}

function RunningPanel({
    progress,
}: {
    progress?: Record<string, unknown> | undefined;
}) {
    const step =
        progress && typeof progress.step === 'string'
            ? (progress.step as string)
            : 'starting';
    const steps: [string, string][] = [
        ['starting', 'job dispatched'],
        ['simulation_validating', 'validating OASIS runtime'],
        ['simulation_entities', 'building entity graph'],
        ['simulation_profiles', 'generating personas (LLM)'],
        ['simulation_seed_posts', 'preparing seed posts'],
        ['simulation_oasis', 'running OASIS rounds'],
        ['simulation_zep', 'enriching with Zep'],
        ['simulation_done', 'finalizing summary'],
    ];
    const activeIndex = Math.max(
        0,
        steps.findIndex(([key]) => key === step),
    );

    const TERM_BG = '#0d0d0d';
    const TERM_FG = '#e6e6e6';
    const TERM_DIM = '#8a8a8a';
    const TERM_OK = '#7fdc8a';
    const TERM_ACCENT = '#79c0ff';
    const TERM_WARN = '#f0c674';

    return (
        <div
            style={{
                background: TERM_BG,
                border: '1px solid #1a1a1a',
                marginBottom: 24,
                fontFamily: 'var(--mono)',
                fontSize: 12,
                lineHeight: 1.6,
                color: TERM_FG,
            }}
        >
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderBottom: '1px solid #1f1f1f',
                    fontSize: 10,
                    letterSpacing: '0.2em',
                    color: TERM_DIM,
                    textTransform: 'uppercase',
                }}
            >
                <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span
                        style={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            background: TERM_OK,
                            boxShadow: `0 0 10px ${TERM_OK}`,
                        }}
                    />
                    miroedo · pipeline log
                </span>
                <span>
                    step {activeIndex + 1}/{steps.length}
                </span>
            </div>
            <div style={{ padding: 12 }}>
                {steps.map(([key, label], i) => {
                    const done = i < activeIndex;
                    const active = i === activeIndex;
                    const color = done
                        ? TERM_OK
                        : active
                          ? TERM_WARN
                          : TERM_DIM;
                    const marker = done ? '✓' : active ? '▸' : '·';
                    return (
                        <div key={key} style={{ color }}>
                            <span style={{ color: TERM_DIM }}>
                                {String(i + 1).padStart(2, '0')}{' '}
                            </span>
                            <span
                                style={{ width: 14, display: 'inline-block' }}
                            >
                                {marker}
                            </span>{' '}
                            <span style={{ color: TERM_ACCENT }}>
                                [{key.padEnd(24, ' ')}]
                            </span>{' '}
                            {label}
                            {active && ' …'}
                        </div>
                    );
                })}
                <div style={{ color: TERM_DIM, marginTop: 6 }}>
                    streaming agent actions below
                    <span
                        style={{
                            display: 'inline-block',
                            width: 7,
                            height: 13,
                            background: TERM_FG,
                            marginLeft: 4,
                            verticalAlign: 'middle',
                            animation: 'me-caret-blink 1s steps(2) infinite',
                        }}
                    />
                </div>
            </div>
            <style jsx>{`
                @keyframes me-caret-blink {
                    50% {
                        opacity: 0;
                    }
                }
            `}</style>
        </div>
    );
}

function KpiCell({ label, value }: { label: string; value: string | number }) {
    return (
        <div className="me-kpi-card">
            <div className="me-kpi-label">{label}</div>
            <div className="me-kpi-value">{value}</div>
        </div>
    );
}
