'use client';

import { useT } from '@/lib/i18n';
import type { PipelineResult } from '@/lib/types';

export default function KpiGrid({ result }: { result: PipelineResult }) {
    const { t } = useT();
    const k = result.kpi;
    const sim = result.simulation;

    const cards: { label: string; value: string | number }[] = [
        { label: t('report.kpi.chapters'), value: k.chapter_count ?? 0 },
        { label: t('report.kpi.words'), value: k.word_count ?? 0 },
        {
            label: t('report.kpi.density'),
            value: `${k.quantitative_density_score ?? 0}%`,
        },
        {
            label: t('report.kpi.predictions'),
            value: k.predictive_conclusion_count ?? 0,
        },
    ];
    if (sim?.total_actions !== undefined) {
        cards.push({
            label: t('report.kpi.simulation'),
            value: sim.total_actions,
        });
    }
    if (sim?.profiles_count !== undefined) {
        cards.push({
            label: t('report.kpi.profiles'),
            value: sim.profiles_count,
        });
    }

    return (
        <div
            className="me-kpi-grid"
            style={{ gridTemplateColumns: `repeat(${cards.length}, 1fr)` }}
        >
            {cards.map((c) => (
                <div key={c.label} className="me-kpi-card">
                    <div className="me-kpi-label">{c.label}</div>
                    <div className="me-kpi-value">{c.value}</div>
                </div>
            ))}
        </div>
    );
}
