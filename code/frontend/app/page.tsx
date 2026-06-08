'use client';

import Link from 'next/link';
import HistoryDatabase from '@/components/HistoryDatabase';
import { useT } from '@/lib/i18n';

export default function HomePage() {
    const { t } = useT();
    return (
        <main className="me-home">
            <section className="me-home-hero">
                <div className="me-home-eyebrow">{t('home.eyebrow')}</div>
                <h1 className="me-home-logo">MIROEDO</h1>
                <p className="me-home-sub">{t('home.sub')}</p>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <Link href="/process/new" className="me-home-cta">
                        <span>{t('home.cta_new')}</span>
                        <span className="me-home-cta-arrow">→</span>
                    </Link>
                </div>
                <div className="me-home-pills">
                    <span className="me-home-pill">{t('home.pills.csv')}</span>
                    <span className="me-home-pill">
                        {t('home.pills.oasis')}
                    </span>
                    <span className="me-home-pill">
                        {t('home.pills.mistral')}
                    </span>
                    <span className="me-home-pill">{t('home.pills.ita')}</span>
                </div>
            </section>
            <section className="me-home-history-wrap">
                <HistoryDatabase />
            </section>
        </main>
    );
}
