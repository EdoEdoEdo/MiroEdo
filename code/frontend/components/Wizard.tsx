'use client';

import Link from 'next/link';
import { useT } from '@/lib/i18n';

interface WizardProps {
    runId: string;
    current: 1 | 2 | 3 | 4 | 5;
    done: number; // index up to which step is done
}

export default function Wizard({ runId, current, done }: WizardProps) {
    const { t } = useT();
    const steps = [
        { n: 1, label: t('wizard.step1'), href: `/process/${runId}` },
        { n: 2, label: t('wizard.step2'), href: `/process/${runId}` },
        {
            n: 3,
            label: t('wizard.step3'),
            href: `/simulation/${runId}`,
        },
        { n: 4, label: t('wizard.step4'), href: `/report/${runId}` },
        {
            n: 5,
            label: t('wizard.step5'),
            href: `/interaction/${runId}`,
        },
    ];
    return (
        <nav className="me-wizard-steps" aria-label="wizard">
            {steps.map((s) => {
                const enabled = s.n <= done || s.n === current;
                const cls = [
                    'me-wizard-step',
                    s.n === current ? 'active' : '',
                    s.n <= done && s.n !== current ? 'done' : '',
                    !enabled ? 'disabled' : '',
                ]
                    .filter(Boolean)
                    .join(' ');
                if (!enabled) {
                    return (
                        <span key={s.n} className={cls} aria-disabled="true">
                            <div className="me-wizard-step-num">
                                {String(s.n).padStart(2, '0')} / 05
                            </div>
                            <div className="me-wizard-step-title">
                                {s.label}
                            </div>
                        </span>
                    );
                }
                return (
                    <Link key={s.n} href={s.href} className={cls}>
                        <div className="me-wizard-step-num">
                            {String(s.n).padStart(2, '0')} / 05
                        </div>
                        <div className="me-wizard-step-title">{s.label}</div>
                    </Link>
                );
            })}
        </nav>
    );
}
