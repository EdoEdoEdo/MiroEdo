'use client';

import UploadForm from '@/components/UploadForm';
import { useT } from '@/lib/i18n';

export default function NewProcessPage() {
    const { t } = useT();
    return (
        <main className="me-wizard">
            <nav className="me-wizard-steps" aria-label="wizard">
                <div className="me-wizard-step active">
                    <div className="me-wizard-step-num">01 / 05</div>
                    <div className="me-wizard-step-title">
                        {t('wizard.step1')}
                    </div>
                </div>
                {[2, 3, 4, 5].map((n) => (
                    <div key={n} className="me-wizard-step">
                        <div className="me-wizard-step-num">
                            {String(n).padStart(2, '0')} / 05
                        </div>
                        <div className="me-wizard-step-title">
                            {t(
                                `wizard.step${n}` as `wizard.step${1 | 2 | 3 | 4 | 5}`,
                            )}
                        </div>
                    </div>
                ))}
            </nav>
            <section className="me-wizard-body">
                <div style={{ marginBottom: 28 }}>
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
                        STEP 01 · UPLOAD
                    </div>
                    <h1
                        style={{
                            fontFamily: 'var(--display)',
                            fontSize: 'clamp(40px, 6vw, 84px)',
                            lineHeight: 0.95,
                            marginBottom: 12,
                        }}
                    >
                        {t('upload.title')}
                    </h1>
                    <p
                        style={{
                            fontFamily: 'var(--serif)',
                            fontStyle: 'italic',
                            color: '#333',
                            maxWidth: 620,
                            fontSize: 17,
                        }}
                    >
                        {t('upload.sub')}
                    </p>
                </div>
                <UploadForm />
            </section>
        </main>
    );
}
