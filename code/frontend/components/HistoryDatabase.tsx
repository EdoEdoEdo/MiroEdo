'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { listReports } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { timeAgo } from '@/lib/format';
import type { RunRecord } from '@/lib/types';
import StatusBadge from './StatusBadge';

export default function HistoryDatabase({ limit = 30 }: { limit?: number }) {
    const { t, locale } = useT();
    const [runs, setRuns] = useState<RunRecord[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const data = await listReports(limit);
                if (alive) setRuns(data);
            } catch (e: unknown) {
                if (alive)
                    setError(e instanceof Error ? e.message : 'unknown error');
            }
        };
        load();
        const id = setInterval(load, 5000);
        return () => {
            alive = false;
            clearInterval(id);
        };
    }, [limit]);

    return (
        <div className="me-history">
            <div className="me-history-header">
                <span>{t('history.title')}</span>
                <span className="me-history-count">
                    {t('history.count')} {runs?.length ?? 0}
                </span>
            </div>
            <div className="me-history-list">
                {error && (
                    <div className="me-history-empty">
                        {t('history.error')} {error}
                    </div>
                )}
                {!error && runs === null && (
                    <div className="me-history-empty">
                        {t('history.loading')}
                    </div>
                )}
                {!error && runs && runs.length === 0 && (
                    <div className="me-history-empty">{t('history.empty')}</div>
                )}
                {runs?.map((r, i) => (
                    <Link
                        key={r.run_id}
                        href={`/process/${r.run_id}`}
                        className="me-history-row"
                    >
                        <span className="me-history-num">
                            {String(i + 1).padStart(2, '0')}
                        </span>
                        <div className="me-history-main">
                            <div className="me-history-brand">{r.brand}</div>
                            <div className="me-history-meta">
                                {r.mode.toUpperCase()} ·{' '}
                                {r.source_type.replace('_', ' ')}
                                {r.source_filename
                                    ? ` · ${r.source_filename}`
                                    : ''}
                            </div>
                        </div>
                        <StatusBadge status={r.status} />
                        <span className="me-history-date">
                            {timeAgo(r.updated_at, locale)}
                        </span>
                    </Link>
                ))}
            </div>
        </div>
    );
}
