'use client';

import { useEffect, useRef, useState } from 'react';
import { getReport } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { nowTimeHHMMSS } from '@/lib/format';
import type { RunRecord } from '@/lib/types';

const STEP_ORDER = [
    'ingest',
    'baseline_report',
    'simulation',
    'kpi',
    'executive_summary',
    'action_plan',
];

interface LogLine {
    t: string;
    text: string;
    kind?: 'active' | 'ok' | 'error';
}

export default function ProgressLive({
    runId,
    onDone,
}: {
    runId: string;
    onDone?: (rec: RunRecord) => void;
}) {
    const { t } = useT();
    const [rec, setRec] = useState<RunRecord | null>(null);
    const [log, setLog] = useState<LogLine[]>([]);
    const seenSteps = useRef<Set<string>>(new Set());

    useEffect(() => {
        let alive = true;
        let stopped = false;

        const append = (text: string, kind?: LogLine['kind']) =>
            setLog((prev) => [...prev, { t: nowTimeHHMMSS(), text, kind }]);

        append(`run ${runId.slice(0, 12)}\u2026 connecting`);
        const seenNotes = new Set<string>();

        const tick = async () => {
            try {
                const r = await getReport(runId);
                if (!alive) return;
                setRec(r);
                const step = r.progress?.step;
                if (step && !seenSteps.current.has(step)) {
                    seenSteps.current.add(step);
                    append(`step: ${step}`, 'active');
                }
                const note = r.progress?.note as string | undefined;
                if (note && !seenNotes.has(note)) {
                    seenNotes.add(note);
                    append(note);
                }
                if (r.status === 'succeeded') {
                    append('succeeded', 'ok');
                    stopped = true;
                    onDone?.(r);
                    return;
                }
                if (r.status === 'failed') {
                    append(`failed: ${r.error ?? 'unknown'}`, 'error');
                    stopped = true;
                    onDone?.(r);
                    return;
                }
            } catch (e: unknown) {
                append(e instanceof Error ? e.message : 'fetch error', 'error');
            }
            if (!stopped && alive) setTimeout(tick, 2000);
        };
        tick();
        return () => {
            alive = false;
            stopped = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [runId]);

    const currentIdx = (() => {
        const s = rec?.progress?.step ?? '';
        const idx = STEP_ORDER.indexOf(s);
        return idx >= 0 ? idx + 1 : 0;
    })();

    return (
        <section className="me-progress">
            <div className="me-progress-title">{t('sim.run_title')}</div>
            <div className="me-progress-step-now">
                {rec?.progress?.step
                    ? `\u25B6 ${rec.progress.step.toUpperCase()}`
                    : t('process.loading')}
            </div>

            <div className="loading-bar-wrap" style={{ maxWidth: 720 }}>
                <div className="loading-bar-label">
                    <span>PROGRESS</span>
                    <span>
                        {currentIdx} / {STEP_ORDER.length}
                    </span>
                </div>
                <div className="loading-bar-track">
                    <div
                        className="loading-bar-fill"
                        style={{
                            width: `${(currentIdx / STEP_ORDER.length) * 100}%`,
                        }}
                    />
                </div>
            </div>

            <div className="me-progress-log" style={{ marginTop: 32 }}>
                {log.map((l, i) => (
                    <div key={i} className="me-progress-log-line">
                        <span className="me-progress-log-time">{l.t}</span>
                        <span className={`log-text ${l.kind ?? ''}`}>
                            {l.text}
                        </span>
                    </div>
                ))}
            </div>
        </section>
    );
}
