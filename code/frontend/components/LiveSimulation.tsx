'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchActions, type ActionRow } from '@/lib/api';
import { useT } from '@/lib/i18n';
import type { SimulationSummary } from '@/lib/types';
import ForceGraphSVG, { type FGNode, type FGLink } from './ForceGraphSVG';

type ZepGraphPreview = NonNullable<
    NonNullable<SimulationSummary['zep']>['graph_preview']
>;
type ZepNode = NonNullable<ZepGraphPreview['nodes']>[number];

const metricLabelStyle = {
    fontFamily: 'var(--mono)',
    fontSize: 9,
    letterSpacing: '0.18em',
    color: 'var(--mid)',
    marginBottom: 4,
};

const metricValueStyle = {
    fontFamily: 'var(--mono)',
    fontSize: 13,
    color: 'var(--ink)',
    wordBreak: 'break-word' as const,
};

const TERM_BG = '#0d0d0d';
const TERM_FG = '#e6e6e6';
const TERM_DIM = '#8a8a8a';
const TERM_OK = '#7fdc8a';
const TERM_WARN = '#f0c674';
const TERM_ERR = '#ef6a6a';
const TERM_ACCENT = '#79c0ff';

interface LiveSimulationProps {
    runId: string;
    simStatus: 'idle' | 'pending' | 'running' | 'succeeded' | 'failed';
    sim?: SimulationSummary | null;
}

export default function LiveSimulation({
    runId,
    simStatus,
    sim,
}: LiveSimulationProps) {
    const { t } = useT();
    const personas = sim?.profiles_preview ?? [];
    const zepStatus = sim?.zep?.status;
    const zepGraphId = sim?.zep?.graph_id;
    const zepFacts = sim?.zep?.facts_registered ?? 0;
    const zepGraphPreview = sim?.zep?.graph_preview;

    const { rows, cursor, error } = useActionStream(runId, simStatus);

    const actionRowsCount = useMemo(
        () => rows.filter((r) => r.event === 'action').length,
        [rows],
    );
    const graphReplayProgress =
        typeof sim?.total_actions === 'number' && sim.total_actions > 0
            ? Math.min(1, actionRowsCount / sim.total_actions)
            : undefined;

    // Step 3: flash signal map. Bumped whenever a new row arrives.
    // Each PersonaCard reads its own signal and pulses on change.
    const flashSignals = useMemo(() => {
        const map: Record<number, number> = {};
        // Walk last ~120 rows; agents older than that are stale and won't pulse.
        const tail = rows.slice(Math.max(0, rows.length - 120));
        for (const r of tail) {
            const id = r.agent_id;
            if (typeof id === 'number') {
                map[id] = (map[id] ?? 0) + 1;
            }
        }
        return map;
    }, [rows]);

    return (
        <div className="me-livesim">
            {/* Zone 1: Counter bar (sticky top) */}
            <CounterBar
                rows={rows}
                personasCount={personas.length}
                simStatus={simStatus}
                simProgress={extractProgressFraction(sim?.simulation_progress)}
            />

            {/* Zone 2: Knowledge graph (full width, "respira") */}
            <div className="me-livesim-graph">
                <SectionLabel>{t('live.kg_title')}</SectionLabel>
                <ZepGraphPanel
                    status={zepStatus}
                    reason={sim?.zep?.reason}
                    facts={zepFacts}
                    graphId={zepGraphId ?? zepGraphPreview?.graph_id}
                    preview={zepGraphPreview}
                    replayDurationMs={25_000}
                    replayProgress={graphReplayProgress}
                />
            </div>

            {/* Zone 3: cards (grid) + live terminal (sidebar) */}
            <div className="me-livesim-body">
                <div className="me-livesim-cards">
                    <SectionLabel>
                        {t('live.personas_count')} ({personas.length})
                    </SectionLabel>
                    {personas.length === 0 ? (
                        <EmptyPanel>{t('live.personas_empty')}</EmptyPanel>
                    ) : (
                        <div className="me-livesim-cards-grid">
                            {personas.map((p, i) => (
                                <PersonaCard
                                    key={p.user_id ?? i}
                                    persona={p}
                                    flashSignal={
                                        typeof p.user_id === 'number'
                                            ? (flashSignals[p.user_id] ?? 0)
                                            : 0
                                    }
                                />
                            ))}
                        </div>
                    )}
                </div>

                <aside className="me-livesim-stream">
                    <SectionLabel>{t('live.stream_title')}</SectionLabel>
                    <LiveTerminal
                        rows={rows}
                        cursor={cursor}
                        simStatus={simStatus}
                        error={error}
                    />
                </aside>
            </div>

            {/* Zone 4: Mini-timeline (footer) */}
            <MiniTimeline rows={rows} />

            <style jsx>{`
                .me-livesim {
                    display: grid;
                    gap: 16px;
                    margin-top: 16px;
                }
                .me-livesim-graph {
                    min-width: 0;
                }
                .me-livesim-body {
                    display: grid;
                    grid-template-columns: minmax(0, 1fr) minmax(500px, 560px);
                    gap: 16px;
                    align-items: start;
                }
                .me-livesim-cards {
                    min-width: 0;
                }
                .me-livesim-cards-grid {
                    display: grid;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    gap: 10px;
                    align-content: start;
                }
                .me-livesim-stream {
                    min-width: 0;
                    position: sticky;
                    top: 16px;
                    align-self: start;
                }
                @media (max-width: 960px) {
                    .me-livesim-body {
                        grid-template-columns: 1fr;
                    }
                    .me-livesim-stream {
                        position: static;
                    }
                    .me-livesim-cards-grid {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }
                }
                @media (max-width: 560px) {
                    .me-livesim-cards-grid {
                        grid-template-columns: 1fr;
                    }
                }
            `}</style>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Counter bar (zone 1)
// ---------------------------------------------------------------------------

const TOTAL_ROUNDS_FALLBACK = 10;

function extractProgressFraction(
    p?: SimulationSummary['simulation_progress'],
): number | undefined {
    if (!p || typeof p !== 'object') return undefined;
    const obj = p as Record<string, unknown>;
    for (const key of [
        'fraction',
        'pct',
        'percent',
        'progress',
        'completion',
        'value',
    ]) {
        const v = obj[key];
        if (typeof v === 'number' && isFinite(v)) {
            return v > 1.5 ? v / 100 : v; // accept both 0–1 and 0–100
        }
    }
    const done = obj['done'];
    const total = obj['total'];
    if (typeof done === 'number' && typeof total === 'number' && total > 0) {
        return done / total;
    }
    return undefined;
}

function CounterBar({
    rows,
    personasCount,
    simStatus,
    simProgress,
}: {
    rows: ActionRow[];
    personasCount: number;
    simStatus: LiveSimulationProps['simStatus'];
    simProgress?: number;
}) {
    const { t, locale } = useT();
    const numberLocale = locale === 'en' ? 'en-US' : 'it-IT';
    const total = rows.length;
    const lastRound = rows.length > 0 ? (rows[rows.length - 1].round ?? 0) : 0;
    // "active in last 8s": count distinct agents in the tail of the stream.
    const activeAgents = useMemo(() => {
        const tail = rows.slice(Math.max(0, rows.length - 80));
        const set = new Set<number>();
        for (const r of tail) {
            if (typeof r.agent_id === 'number') set.add(r.agent_id);
        }
        return set.size;
    }, [rows]);

    const progress =
        typeof simProgress === 'number'
            ? Math.max(0, Math.min(1, simProgress))
            : Math.max(0, Math.min(1, lastRound / TOTAL_ROUNDS_FALLBACK));

    const statusColor =
        simStatus === 'succeeded'
            ? '#1f7a3a'
            : simStatus === 'failed'
              ? '#b8332b'
              : simStatus === 'running'
                ? '#b8332b'
                : 'var(--mid, #777)';

    return (
        <div
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 5,
                display: 'grid',
                gridTemplateColumns: 'auto auto auto 1fr auto',
                alignItems: 'center',
                gap: 18,
                padding: '10px 14px',
                background: 'var(--paper, #f2efe8)',
                borderTop: '1px solid var(--ink, #111)',
                borderBottom: '1px solid var(--ink, #111)',
                fontFamily: 'var(--mono)',
                fontSize: 11,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: 'var(--ink, #111)',
            }}
        >
            <Metric
                label={t('live.counter_round')}
                value={`${lastRound}/${TOTAL_ROUNDS_FALLBACK}`}
            />
            <Metric
                label={t('live.counter_actions')}
                value={total.toLocaleString(numberLocale)}
            />
            <Metric
                label={t('live.counter_active')}
                value={`${activeAgents}/${personasCount}`}
            />
            {/* progress bar */}
            <div
                style={{
                    height: 6,
                    background: 'rgba(0,0,0,0.08)',
                    border: '1px solid var(--ink, #111)',
                    position: 'relative',
                    overflow: 'hidden',
                }}
                aria-label="simulation progress"
            >
                <div
                    style={{
                        width: `${Math.round(progress * 100)}%`,
                        height: '100%',
                        background: 'var(--red, #b8332b)',
                        transition: 'width 300ms ease',
                    }}
                />
            </div>
            <span
                style={{
                    color: statusColor,
                    fontWeight: 600,
                }}
            >
                {simStatus}
            </span>
        </div>
    );
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <span
            style={{ display: 'inline-flex', gap: 6, alignItems: 'baseline' }}
        >
            <span style={{ color: 'var(--mid, #777)', fontSize: 9 }}>
                {label}
            </span>
            <span style={{ fontWeight: 600 }}>{value}</span>
        </span>
    );
}

// ---------------------------------------------------------------------------
// Mini-timeline (zone 4)
// ---------------------------------------------------------------------------

const ACTION_COLORS: Record<string, string> = {
    create_post: '#b8332b', // red — segnali forti
    create_comment: '#d97706', // amber
    like_post: '#1f7a3a', // green
    dislike_post: '#7c1d6f', // purple
    refresh: '#9aa0a6', // grey — rumore di fondo
    do_nothing: '#cbd5e1', // pale
    sign_up: '#1d4ed8', // blue — onboarding
};

const ACTION_ORDER = [
    'create_post',
    'create_comment',
    'like_post',
    'dislike_post',
    'sign_up',
    'refresh',
    'do_nothing',
];

const BUCKET_COUNT = 60;

function MiniTimeline({ rows }: { rows: ActionRow[] }) {
    const { t, locale } = useT();
    const numberLocale = locale === 'en' ? 'en-US' : 'it-IT';
    const { buckets, maxBucketTotal, totalsByAction } = useMemo(() => {
        const actionRows = rows.filter((r) => r.event === 'action');
        const totalsByAction: Record<string, number> = {};
        for (const r of actionRows) {
            const a = r.action ?? 'do_nothing';
            totalsByAction[a] = (totalsByAction[a] ?? 0) + 1;
        }
        const buckets: Record<string, number>[] = Array.from(
            { length: BUCKET_COUNT },
            () => ({}),
        );
        if (actionRows.length === 0) {
            return { buckets, maxBucketTotal: 0, totalsByAction };
        }
        const len = actionRows.length;
        for (let i = 0; i < len; i++) {
            const r = actionRows[i];
            const bIdx = Math.min(
                BUCKET_COUNT - 1,
                Math.floor((i / len) * BUCKET_COUNT),
            );
            const a = r.action ?? 'do_nothing';
            buckets[bIdx][a] = (buckets[bIdx][a] ?? 0) + 1;
        }
        let maxBucketTotal = 0;
        for (const b of buckets) {
            const sum = Object.values(b).reduce((s, v) => s + v, 0);
            if (sum > maxBucketTotal) maxBucketTotal = sum;
        }
        return { buckets, maxBucketTotal, totalsByAction };
    }, [rows]);

    if (rows.length === 0) return null;

    const usedActions = ACTION_ORDER.filter((a) => totalsByAction[a] > 0);

    return (
        <div
            style={{
                padding: '10px 14px 12px',
                borderTop: '1px solid var(--ink, #111)',
                fontFamily: 'var(--mono)',
                fontSize: 10,
                letterSpacing: '0.16em',
                color: 'var(--mid, #777)',
                textTransform: 'uppercase',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    gap: 14,
                    alignItems: 'baseline',
                    marginBottom: 8,
                    flexWrap: 'wrap',
                }}
            >
                <span style={{ color: 'var(--ink, #111)', fontWeight: 600 }}>
                    {t('live.timeline_title')}
                </span>
                <span>
                    {Object.values(totalsByAction)
                        .reduce((s, v) => s + v, 0)
                        .toLocaleString(numberLocale)}{' '}
                    {t('live.timeline_actions_suffix')} · {BUCKET_COUNT}{' '}
                    {t('live.timeline_meta_suffix')}
                </span>
                <span
                    style={{
                        marginLeft: 'auto',
                        display: 'flex',
                        gap: 10,
                        flexWrap: 'wrap',
                    }}
                >
                    {usedActions.map((a) => (
                        <span
                            key={a}
                            style={{
                                display: 'inline-flex',
                                gap: 4,
                                alignItems: 'center',
                            }}
                        >
                            <span
                                style={{
                                    width: 10,
                                    height: 10,
                                    background: ACTION_COLORS[a],
                                    display: 'inline-block',
                                }}
                            />
                            <span>{a.replace(/_/g, ' ')}</span>
                            <span style={{ opacity: 0.55 }}>
                                {totalsByAction[a]}
                            </span>
                        </span>
                    ))}
                </span>
            </div>
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(${BUCKET_COUNT}, 1fr)`,
                    gap: 1,
                    height: 56,
                    alignItems: 'end',
                    background: '#fff',
                    border: '1px solid var(--ink, #111)',
                    padding: 4,
                }}
            >
                {buckets.map((b, i) => {
                    const total = Object.values(b).reduce((s, v) => s + v, 0);
                    const heightPct =
                        maxBucketTotal > 0 ? (total / maxBucketTotal) * 100 : 0;
                    return (
                        <div
                            key={i}
                            style={{
                                display: 'flex',
                                flexDirection: 'column-reverse',
                                height: `${heightPct}%`,
                                minHeight: total > 0 ? 2 : 0,
                            }}
                            title={`${t('live.timeline_meta_suffix')} ${i + 1} · ${total} ${t('live.timeline_actions_suffix')}`}
                        >
                            {ACTION_ORDER.map((a) => {
                                const v = b[a] ?? 0;
                                if (v === 0) return null;
                                const segPct =
                                    total > 0 ? (v / total) * 100 : 0;
                                return (
                                    <div
                                        key={a}
                                        style={{
                                            height: `${segPct}%`,
                                            background: ACTION_COLORS[a],
                                        }}
                                    />
                                );
                            })}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Polling hook
// ---------------------------------------------------------------------------

function useActionStream(
    runId: string,
    simStatus: LiveSimulationProps['simStatus'],
) {
    const [rows, setRows] = useState<ActionRow[]>([]);
    const [cursor, setCursor] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const cursorRef = useRef(0);
    const stoppedRef = useRef(false);

    useEffect(() => {
        cursorRef.current = 0;
        stoppedRef.current = false;
        setRows([]);
        setCursor(0);
        setError(null);
    }, [runId]);

    useEffect(() => {
        if (simStatus === 'idle') return;
        let cancelled = false;

        const tick = async () => {
            if (cancelled) return;
            try {
                const res = await fetchActions(runId, cursorRef.current, 800);
                if (cancelled) return;
                if (res.rows.length > 0) {
                    setRows((prev) => [...prev, ...res.rows]);
                    cursorRef.current = res.cursor;
                    setCursor(res.cursor);
                }
                if (res.done) {
                    // One last sweep to make sure we caught the tail.
                    if (!stoppedRef.current) {
                        stoppedRef.current = true;
                        setTimeout(tick, 600);
                        return;
                    }
                    return;
                }
            } catch (e) {
                if (!cancelled)
                    setError(
                        e instanceof Error ? e.message : 'errore stream azioni',
                    );
            }
            if (!cancelled && !stoppedRef.current) {
                setTimeout(tick, 1200);
            }
        };

        tick();
        return () => {
            cancelled = true;
        };
    }, [runId, simStatus]);

    return { rows, cursor, error };
}

// ---------------------------------------------------------------------------
// Live terminal (right column, bottom)
// ---------------------------------------------------------------------------

function LiveTerminal({
    rows,
    cursor,
    simStatus,
    error,
}: {
    rows: ActionRow[];
    cursor: number;
    simStatus: LiveSimulationProps['simStatus'];
    error: string | null;
}) {
    const { t } = useT();
    const scrollRef = useRef<HTMLDivElement | null>(null);
    const [autoScroll, setAutoScroll] = useState(true);

    useEffect(() => {
        if (!autoScroll) return;
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }, [rows.length, autoScroll]);

    const counts = useMemo(() => {
        const out: Record<string, number> = {};
        for (const r of rows) {
            if (r.event !== 'action' || !r.action) continue;
            out[r.action] = (out[r.action] ?? 0) + 1;
        }
        return out;
    }, [rows]);

    const totalActions = rows.filter((r) => r.event === 'action').length;
    const running = simStatus === 'running' || simStatus === 'pending';

    return (
        <div
            style={{
                background: TERM_BG,
                border: '1px solid #1a1a1a',
                boxShadow: '0 0 0 1px rgba(255,255,255,0.04) inset',
            }}
        >
            {/* Toolbar */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderBottom: '1px solid #1f1f1f',
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.18em',
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
                            background: running
                                ? TERM_OK
                                : simStatus === 'failed'
                                  ? TERM_ERR
                                  : '#444',
                            boxShadow: running
                                ? `0 0 10px ${TERM_OK}`
                                : undefined,
                        }}
                    />
                    miroedo · live action stream
                </span>
                <span style={{ display: 'flex', gap: 14 }}>
                    <span>
                        rows {totalActions} · cursor {cursor}
                    </span>
                    <label
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            cursor: 'pointer',
                            color: autoScroll ? TERM_ACCENT : TERM_DIM,
                        }}
                    >
                        <input
                            type="checkbox"
                            checked={autoScroll}
                            onChange={(e) => setAutoScroll(e.target.checked)}
                            style={{ accentColor: TERM_ACCENT }}
                        />
                        autoscroll
                    </label>
                </span>
            </div>

            {/* Stream body */}
            <div
                ref={scrollRef}
                style={{
                    height: 380,
                    overflow: 'auto',
                    padding: 12,
                    fontFamily: 'var(--mono)',
                    fontSize: 11.5,
                    lineHeight: 1.55,
                    color: TERM_FG,
                    background: TERM_BG,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                }}
            >
                {rows.length === 0 && (
                    <div style={{ color: TERM_DIM }}>
                        {running
                            ? t('live.terminal_waiting')
                            : simStatus === 'idle'
                              ? t('live.terminal_idle')
                              : t('live.terminal_no_actions')}
                        <Caret />
                    </div>
                )}
                {rows.map((row, i) => (
                    <TerminalLine key={i} row={row} />
                ))}
                {running && rows.length > 0 && (
                    <div style={{ color: TERM_DIM, marginTop: 4 }}>
                        <Caret />
                    </div>
                )}
            </div>

            {/* Footer status */}
            <div
                style={{
                    display: 'flex',
                    gap: 14,
                    flexWrap: 'wrap',
                    padding: '8px 12px',
                    borderTop: '1px solid #1f1f1f',
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    letterSpacing: '0.06em',
                    color: TERM_DIM,
                    background: '#080808',
                }}
            >
                {Object.entries(counts)
                    .sort((a, b) => b[1] - a[1])
                    .map(([k, v]) => (
                        <span key={k}>
                            <span style={{ color: TERM_ACCENT }}>{k}</span>={v}
                        </span>
                    ))}
                {error && (
                    <span style={{ color: TERM_ERR, marginLeft: 'auto' }}>
                        ! {error}
                    </span>
                )}
            </div>
        </div>
    );
}

function TerminalLine({ row }: { row: ActionRow }) {
    const ts = row.created_at ?? '';
    if (row.event === 'simulation_start') {
        return (
            <div style={{ color: TERM_OK }}>
                {ts && <Dim>{ts} </Dim>}
                {'# simulation_start profiles='}
                {row.profiles} rounds={row.rounds} seed_posts={row.seed_posts}
            </div>
        );
    }
    if (row.event === 'simulation_end') {
        return (
            <div style={{ color: TERM_OK }}>
                {ts && <Dim>{ts} </Dim>}
                {'# simulation_end rounds_executed='}
                {row.rounds}
            </div>
        );
    }
    if (row.event === 'round_start') {
        return (
            <div style={{ color: TERM_WARN }}>
                {ts && <Dim>{ts} </Dim>}
                {'-- round '}
                {row.round} start ({row.kind})
            </div>
        );
    }
    if (row.event === 'round_end') {
        return (
            <div style={{ color: TERM_WARN }}>
                {ts && <Dim>{ts} </Dim>}
                {'-- round '}
                {row.round} end · actions={row.actions_count}
            </div>
        );
    }
    if (row.event === 'action') {
        const info = parseInfo(row.info);
        const tag = row.action ?? 'UNKNOWN';
        return (
            <div>
                <Dim>r{row.round} </Dim>
                <span style={{ color: colorForAction(tag) }}>
                    [{tag.padEnd(15, ' ')}]
                </span>{' '}
                <Dim>agent#</Dim>
                {row.agent_id}
                {info && <span style={{ color: TERM_DIM }}> · {info}</span>}
            </div>
        );
    }
    return (
        <div style={{ color: TERM_DIM }}>
            {row.event} {JSON.stringify(row)}
        </div>
    );
}

function parseInfo(info: unknown): string {
    if (!info) return '';
    if (typeof info !== 'string') return '';
    try {
        const obj = JSON.parse(info) as Record<string, unknown>;
        const bits: string[] = [];
        if ('post_id' in obj) bits.push(`post=${obj.post_id}`);
        if ('content' in obj && typeof obj.content === 'string')
            bits.push(`"${obj.content.slice(0, 70)}"`);
        if ('followee_id' in obj) bits.push(`→ #${obj.followee_id}`);
        return bits.join(' ');
    } catch {
        return '';
    }
}

function colorForAction(action: string): string {
    switch (action) {
        case 'CREATE_POST':
            return TERM_ACCENT;
        case 'CREATE_COMMENT':
            return '#d4a5ff';
        case 'LIKE_POST':
            return TERM_OK;
        case 'DISLIKE_POST':
            return TERM_ERR;
        case 'SIGN_UP':
            return TERM_WARN;
        default:
            return TERM_DIM;
    }
}

function Dim({ children }: { children: React.ReactNode }) {
    return <span style={{ color: TERM_DIM }}>{children}</span>;
}

function Caret() {
    return (
        <>
            <span
                style={{
                    display: 'inline-block',
                    width: 7,
                    height: 13,
                    background: TERM_FG,
                    marginLeft: 2,
                    verticalAlign: 'middle',
                    animation: 'me-caret-blink 1s steps(2) infinite',
                }}
            />
            <style jsx>{`
                @keyframes me-caret-blink {
                    50% {
                        opacity: 0;
                    }
                }
            `}</style>
        </>
    );
}

// ---------------------------------------------------------------------------
// Zep graph panel
// ---------------------------------------------------------------------------

function ZepGraphPanel({
    status,
    reason,
    facts,
    graphId,
    preview,
    replayDurationMs,
    replayProgress,
}: {
    status?: string;
    reason?: string;
    facts: number;
    graphId?: string;
    preview?: ZepGraphPreview;
    /**
     * If set, reveal nodes progressively over this many ms instead of all at once.
     * Default: undefined = instant render (back-compat for non-live usages).
     */
    replayDurationMs?: number;
    /** Optional stream-driven progress (0–1): reveal graph as actions arrive. */
    replayProgress?: number;
}) {
    const { t } = useT();
    const nodes = preview?.nodes ?? [];
    const links = preview?.links ?? [];
    const hasGraph = nodes.length > 0;
    const persisted = status === 'ok';

    // Step 5: replay — order nodes topologically so the storyline is coherent.
    // Brand first → Topics → Segments → Actors/Risks → Opportunities → rest.
    const orderedNodes = useMemo(() => {
        const weight = (n: ZepNode) => {
            const t = (n.type ?? '').toLowerCase();
            if (t === 'brand') return 0;
            if (t === 'topic') return 1;
            if (t === 'segment') return 2;
            if (t === 'actor') return 3;
            if (t === 'risk') return 4;
            if (t === 'opportunity') return 5;
            if (t === 'platform') return 6;
            if (t === 'competitor') return 7;
            return 8;
        };
        return [...nodes].sort((a, b) => weight(a) - weight(b));
    }, [nodes]);

    const [revealCount, setRevealCount] = useState(
        replayProgress !== undefined || replayDurationMs
            ? 0
            : orderedNodes.length,
    );

    useEffect(() => {
        if (orderedNodes.length === 0) {
            setRevealCount(0);
            return;
        }
        if (typeof replayProgress === 'number') {
            const progress = Math.max(0, Math.min(1, replayProgress));
            setRevealCount(
                progress === 0
                    ? 1
                    : Math.min(
                          orderedNodes.length,
                          Math.ceil(progress * orderedNodes.length),
                      ),
            );
            return;
        }
        // When replay is disabled or no nodes, show everything immediately.
        if (!replayDurationMs) {
            setRevealCount(orderedNodes.length);
            return;
        }
        setRevealCount(0);
        const total = orderedNodes.length;
        // Ease-out timing: more nodes appear early, plateau toward the end.
        const start = performance.now();
        let raf = 0;
        const tick = (now: number) => {
            const t = Math.min(1, (now - start) / replayDurationMs);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);
            const count = Math.min(total, Math.ceil(eased * total));
            setRevealCount(count);
            if (t < 1) {
                raf = requestAnimationFrame(tick);
            }
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [orderedNodes, replayDurationMs, replayProgress]);

    const visibleNodes = useMemo(
        () => orderedNodes.slice(0, revealCount),
        [orderedNodes, revealCount],
    );

    const { fgNodes, fgLinks } = useMemo(() => {
        const ids = new Set(visibleNodes.map((n) => n.id));
        const fgNodes: FGNode[] = visibleNodes.map((n) => {
            const typ = (n.type ?? '').toLowerCase();
            return {
                id: n.id,
                label: n.label,
                color: colorForNode(n, persisted),
                radius: radiusForNode(n),
                stroke: strokeForSentiment(n.sentiment),
                strokeWidth: typ === 'brand' ? 3 : 1.5,
                bold: typ === 'brand',
            };
        });
        const fgLinks: FGLink[] = links
            .filter((l) => ids.has(l.source) && ids.has(l.target))
            .map((l) => ({
                source: l.source,
                target: l.target,
                color: persisted
                    ? 'rgba(31,31,31,0.42)'
                    : 'rgba(31,31,31,0.22)',
                width: l.type === 'resonates_with' ? 1 : 1.5,
                dashed: l.type === 'resonates_with',
            }));
        return { fgNodes, fgLinks };
    }, [visibleNodes, links, persisted]);

    const containerRef = useRef<HTMLDivElement | null>(null);
    const [size, setSize] = useState({ width: 600, height: 320 });

    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;
        const update = () => {
            const r = el.getBoundingClientRect();
            setSize({
                width: Math.max(280, Math.floor(r.width)),
                height: Math.max(260, Math.floor(r.height)),
            });
        };
        update();
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    return (
        <div
            style={{
                padding: 16,
                border: persisted ? '2px solid var(--ink)' : '1px dashed #ccc',
                background: persisted ? '#fff' : '#fafafa',
                fontFamily: 'var(--serif)',
                fontSize: 13,
                color: '#555',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    flexWrap: 'wrap',
                    alignItems: 'baseline',
                    marginBottom: 12,
                }}
            >
                <div
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        letterSpacing: '0.2em',
                        textTransform: 'uppercase',
                        color: persisted ? 'var(--red)' : 'var(--mid)',
                    }}
                >
                    {t('live.zep_title')}
                </div>
                <div
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        letterSpacing: '0.08em',
                    }}
                >
                    STATUS ·{' '}
                    {(status ?? t('live.zep_status_idle')).toUpperCase()}
                </div>
            </div>

            <div
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                }}
            >
                {hasGraph && (
                    <ZepGraphLegend
                        usedTypes={Array.from(
                            new Set(
                                nodes.map((n) => (n.type ?? '').toLowerCase()),
                            ),
                        )}
                    />
                )}
                <div
                    ref={containerRef}
                    style={{
                        border: '1px solid var(--ink, #111)',
                        background: '#f8f5ef',
                        minHeight: 420,
                        height: 420,
                        position: 'relative',
                        overflow: 'hidden',
                    }}
                >
                    {hasGraph ? (
                        <ForceGraphSVG
                            nodes={fgNodes}
                            links={fgLinks}
                            width={size.width}
                            height={size.height}
                            background="#f8f5ef"
                            chargeStrength={-260}
                            linkDistance={85}
                        />
                    ) : (
                        <div
                            style={{
                                padding: 18,
                                fontFamily: 'var(--serif)',
                                fontStyle: 'italic',
                                color: '#777',
                            }}
                        >
                            {t('live.zep_empty')}
                        </div>
                    )}
                </div>

                <div
                    style={{
                        border: '1px solid #ddd',
                        background: '#fff',
                        padding: 14,
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, minmax(120px, 1fr))',
                        gap: 12,
                        alignItems: 'start',
                    }}
                >
                    <div>
                        <div style={metricLabelStyle}>
                            {t('live.zep_metric_graph')}
                        </div>
                        <div style={metricValueStyle}>{graphId ?? '—'}</div>
                    </div>
                    <div>
                        <div style={metricLabelStyle}>
                            {t('live.zep_metric_facts')}
                        </div>
                        <div style={metricValueStyle}>{facts}</div>
                    </div>
                    <div>
                        <div style={metricLabelStyle}>
                            {t('live.zep_metric_nodes')}
                        </div>
                        <div style={metricValueStyle}>
                            {nodes.length} / {links.length}
                        </div>
                    </div>
                    <p
                        style={{
                            margin: 0,
                            lineHeight: 1.45,
                            gridColumn: '1 / -1',
                        }}
                    >
                        {persisted
                            ? t('live.zep_persisted')
                            : hasGraph
                              ? t('live.zep_preview')
                              : t('live.zep_waiting')}
                    </p>
                    {reason && !persisted && (
                        <p
                            style={{
                                margin: 0,
                                fontFamily: 'var(--mono)',
                                fontSize: 11,
                                color: 'var(--red)',
                                gridColumn: '1 / -1',
                            }}
                        >
                            {reason}
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Persona card + helpers
// ---------------------------------------------------------------------------

function PersonaCard({
    persona,
    flashSignal = 0,
}: {
    persona: NonNullable<SimulationSummary['profiles_preview']>[number];
    flashSignal?: number;
}) {
    // Step 3: flash animation. We bump a CSS class via key when flashSignal changes.
    const [flashKey, setFlashKey] = useState(0);
    const prevSignalRef = useRef(flashSignal);
    useEffect(() => {
        if (flashSignal !== prevSignalRef.current) {
            prevSignalRef.current = flashSignal;
            setFlashKey((k) => k + 1);
        }
    }, [flashSignal]);

    const bits = [
        persona.age ? `${persona.age}` : null,
        persona.country,
        persona.profession,
    ].filter(Boolean);
    const seed = encodeURIComponent(
        persona.username ?? persona.name ?? String(persona.user_id ?? 'anon'),
    );
    const avatar = `https://api.dicebear.com/9.x/notionists/svg?seed=${seed}&backgroundColor=ffeaa7,fab1a0,a29bfe,74b9ff,55efc4,fdcb6e`;
    return (
        <div
            key={flashKey}
            className="me-persona-card"
            style={{
                background: '#fff',
                border: '1px solid var(--ink, #111)',
                padding: '8px 10px',
                fontFamily: 'var(--sans)',
                display: 'grid',
                gridTemplateColumns: '36px 1fr',
                gap: 8,
                alignItems: 'start',
                animation:
                    flashKey > 0 ? 'me-card-flash 400ms ease-out' : undefined,
            }}
        >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
                src={avatar}
                alt=""
                width={36}
                height={36}
                style={{
                    border: '1px solid var(--ink, #111)',
                    background: '#f4f1ea',
                    display: 'block',
                }}
                loading="lazy"
            />
            <div style={{ minWidth: 0 }}>
                <div
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 9,
                        letterSpacing: '0.18em',
                        color: 'var(--red, #b8332b)',
                        textTransform: 'uppercase',
                    }}
                >
                    AGENTE {persona.user_id ?? ''}
                </div>
                <div
                    style={{
                        fontSize: 12,
                        fontWeight: 600,
                        marginTop: 1,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                    }}
                >
                    {persona.name ?? persona.username ?? '—'}
                </div>
                {bits.length > 0 && (
                    <div
                        style={{
                            fontSize: 10,
                            color: '#666',
                            marginTop: 1,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                        }}
                    >
                        {bits.join(' · ')}
                    </div>
                )}
                {persona.bio && (
                    <div
                        style={{
                            fontFamily: 'var(--serif)',
                            fontStyle: 'italic',
                            fontSize: 11,
                            color: '#444',
                            marginTop: 4,
                            lineHeight: 1.35,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                        }}
                    >
                        «{persona.bio}»
                    </div>
                )}
                {persona.interested_topics &&
                    persona.interested_topics.length > 0 && (
                        <div
                            style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: 3,
                                marginTop: 5,
                            }}
                        >
                            {persona.interested_topics
                                .slice(0, 2)
                                .map((t, i) => (
                                    <span
                                        key={i}
                                        style={{
                                            background: 'var(--ink, #111)',
                                            color: '#fff',
                                            fontFamily: 'var(--mono)',
                                            fontSize: 9,
                                            padding: '1px 5px',
                                            letterSpacing: '0.05em',
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            maxWidth: '100%',
                                        }}
                                    >
                                        #{t}
                                    </span>
                                ))}
                        </div>
                    )}
            </div>
            <style jsx>{`
                @keyframes me-card-flash {
                    0% {
                        box-shadow: 0 0 0 0 rgba(184, 51, 43, 0);
                        border-color: var(--ink, #111);
                    }
                    25% {
                        box-shadow: 0 0 0 3px rgba(184, 51, 43, 0.45);
                        border-color: var(--red, #b8332b);
                    }
                    100% {
                        box-shadow: 0 0 0 0 rgba(184, 51, 43, 0);
                        border-color: var(--ink, #111);
                    }
                }
            `}</style>
        </div>
    );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
    return (
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
            {children}
        </div>
    );
}

function EmptyPanel({ children }: { children: React.ReactNode }) {
    return (
        <div
            style={{
                padding: 14,
                border: '1px dashed #ccc',
                background: '#fafafa',
                fontFamily: 'var(--serif)',
                fontStyle: 'italic',
                color: '#777',
                fontSize: 13,
                lineHeight: 1.5,
            }}
        >
            {children}
        </div>
    );
}

function radiusForNode(node: ZepNode): number {
    const t = (node.type ?? '').toLowerCase();
    const baseByType: Record<string, number> = {
        brand: 30,
        competitor: 22,
        topic: 20,
        risk: 22,
        opportunity: 20,
        segment: 18,
        platform: 17,
        actor: 16,
        sentiment: 15,
    };
    const base = baseByType[t] ?? 15;
    // Optional weight modulation so high-weight nodes stand out a bit more.
    const w = typeof node.weight === 'number' ? node.weight : 50;
    const scale = 0.85 + Math.min(1.2, Math.max(0, w) / 100) * 0.4;
    return Math.round(base * scale);
}

// Palette: brand black, competitor warm grey, topic yellow, risk red,
// opportunity green, segment blue, platform purple, actor amber.
// Tuned to stay readable on the paper background.
export const ZEP_TYPE_PALETTE: Record<string, { fill: string; label: string }> =
    {
        brand: { fill: '#1f1f1f', label: 'Brand' },
        competitor: { fill: '#8c7b6a', label: 'Competitor' },
        topic: { fill: '#f2d27c', label: 'Topic' },
        risk: { fill: '#d96b5e', label: 'Risk' },
        opportunity: { fill: '#7fb38a', label: 'Opportunity' },
        segment: { fill: '#9eb7d6', label: 'Segment' },
        platform: { fill: '#b8a4d8', label: 'Platform' },
        actor: { fill: '#e0a155', label: 'Actor' },
    };

function colorForNode(node: ZepNode, persisted: boolean): string {
    const t = (node.type ?? '').toLowerCase();
    if (t === 'sentiment') {
        const s = node.sentiment ?? 0;
        if (s < -0.15) return '#f0b1aa';
        if (s > 0.15) return '#b9dfc2';
        return '#ddd6c9';
    }
    const hit = ZEP_TYPE_PALETTE[t];
    if (hit) return hit.fill;
    // When the run is still bootstrapping (no Zep facts persisted yet),
    // wash everything out to communicate “pending”.
    return persisted ? '#cfc8b9' : '#e3ded0';
}

/** Border colour derived from node sentiment: green/red/grey ring. */
export function strokeForSentiment(s?: number): string {
    if (typeof s !== 'number') return '#111';
    if (s < -0.15) return '#b8332b';
    if (s > 0.15) return '#2f7a48';
    return '#111';
}

function ZepGraphLegend({ usedTypes }: { usedTypes: string[] }) {
    const items = usedTypes
        .map((t) => ({ type: t, ...ZEP_TYPE_PALETTE[t] }))
        .filter((x) => x.fill);
    if (items.length === 0) return null;
    return (
        <div
            style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 14,
                alignItems: 'center',
                padding: '8px 10px',
                border: '1px solid #d6d2c5',
                background: '#f4f1e8',
                fontFamily: 'var(--mono)',
                fontSize: 10,
                letterSpacing: '0.08em',
                color: '#333',
            }}
        >
            <span
                style={{
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                    color: '#888',
                }}
            >
                Legenda
            </span>
            {items.map((it) => (
                <span
                    key={it.type}
                    style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                    }}
                >
                    <span
                        aria-hidden
                        style={{
                            display: 'inline-block',
                            width: 11,
                            height: 11,
                            borderRadius: '50%',
                            background: it.fill,
                            border: '1px solid rgba(0,0,0,0.4)',
                        }}
                    />
                    {it.label}
                </span>
            ))}
            <span
                style={{
                    marginLeft: 'auto',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 10,
                    color: '#666',
                }}
            >
                <SentRing color="#2f7a48" /> pos
                <SentRing color="#111" /> neu
                <SentRing color="#b8332b" /> neg
            </span>
        </div>
    );
}

function SentRing({ color }: { color: string }) {
    return (
        <span
            aria-hidden
            style={{
                display: 'inline-block',
                width: 11,
                height: 11,
                borderRadius: '50%',
                background: '#f4f1e8',
                border: `2px solid ${color}`,
            }}
        />
    );
}

function truncate(value: string, max: number): string {
    if (!value) return '—';
    return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
