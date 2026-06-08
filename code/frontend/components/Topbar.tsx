'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useT } from '@/lib/i18n';
import LanguageSwitcher from './LanguageSwitcher';

export default function Topbar() {
    const { t } = useT();
    const path = usePathname() ?? '/';
    const onHome = path === '/';
    return (
        <header className="me-topbar">
            <div className="me-topbar-left">
                <Link href="/" className="me-brand">
                    MiroEdo
                </Link>
                <span className="me-brand-tag">v0.1</span>
            </div>
            <div className="me-topbar-right">
                <Link
                    href="/"
                    className={`me-nav-link ${onHome ? 'active' : ''}`}
                >
                    {t('nav.home')}
                </Link>
                <Link
                    href="/process/new"
                    className={`me-nav-link ${path.startsWith('/process/new') ? 'active' : ''}`}
                >
                    {t('nav.new_report')}
                </Link>
                <Link
                    href="/about"
                    className={`me-nav-link ${path.startsWith('/about') ? 'active' : ''}`}
                >
                    {t('nav.info')}
                </Link>
                <LanguageSwitcher />
            </div>
        </header>
    );
}
