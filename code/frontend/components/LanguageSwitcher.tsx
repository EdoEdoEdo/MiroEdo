'use client';

import { useT, type Locale } from '@/lib/i18n';

export default function LanguageSwitcher() {
    const { locale, setLocale } = useT();
    const opts: Locale[] = ['it', 'en'];
    return (
        <div className="me-lang-switch" role="group" aria-label="language">
            {opts.map((l) => (
                <button
                    key={l}
                    type="button"
                    className={`me-lang-opt ${locale === l ? 'active' : ''}`}
                    onClick={() => setLocale(l)}
                >
                    {l.toUpperCase()}
                </button>
            ))}
        </div>
    );
}
