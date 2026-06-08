'use client';

import { useRouter } from 'next/navigation';
import {
    useCallback,
    useEffect,
    useRef,
    useState,
    type FormEvent,
} from 'react';
import {
    BASE_PATH,
    createReport,
    DATA_SOURCE,
    listLLMModels,
    type LLMModelInfo,
} from '@/lib/api';
import { useT } from '@/lib/i18n';
import type { PipelineMode } from '@/lib/types';

/**
 * Demo seeds used when DATA_SOURCE === 'mock'. One entry per pre-built
 * scenario in /public/scenarios/. The visitor picks one of the two examples
 * before the pre-filled wizard, then submits — the create call routes to the
 * matching static run via `mock_scenario_id`.
 */
type ExampleId = 'verdaia' | 'nordalatte';

type MockExample = {
    id: ExampleId;
    /** Must match the scenario folder name under public/scenarios/. */
    scenarioId: string;
    brand: string;
    fileName: string;
    /** Tiny metadata string shown under the dropzone, locked-mode only. */
    attachedMeta: string;
    mode: PipelineMode;
    scenario: string;
};

const MOCK_EXAMPLES: Record<ExampleId, MockExample> = {
    verdaia: {
        id: 'verdaia',
        scenarioId: 'esg-retailer',
        brand: 'Verdaia Foods',
        fileName: 'verdaia_esg_mentions_2026Q1.csv',
        attachedMeta: '184 KB · CSV · 8.742 mention · 2026-Q1',
        mode: 'full',
        scenario:
            'New ESG policy launch: 100% traceable supply chain + 4% premium-line price cut. Measure social reaction (IT/EN) in the 14 days after the announcement.',
    },
    nordalatte: {
        id: 'nordalatte',
        scenarioId: 'nordalatte',
        brand: 'NordaLatte',
        fileName: 'nordalatte_recall_brief.pdf',
        attachedMeta: '16 KB · PDF · 1.247 mention · 22 giorni · crisis-recall',
        mode: 'full',
        scenario:
            "Brief crisis-recall NordaLatte: misura il danno reputazionale residuo al 24 marzo, identifica i driver narrativi che continuano a vivere oltre la crisi acuta, e proponi un piano d'azione 72h focalizzato su recupero fiducia segmento famiglie con bambini.",
    },
};

const EXAMPLE_ORDER: ExampleId[] = ['verdaia', 'nordalatte'];

export default function UploadForm() {
    const { t } = useT();
    const router = useRouter();
    const locked = DATA_SOURCE === 'mock';
    const inputRef = useRef<HTMLInputElement | null>(null);
    const [selectedExample, setSelectedExample] =
        useState<ExampleId>('verdaia');
    const activeExample = MOCK_EXAMPLES[selectedExample];
    const [file, setFile] = useState<File | null>(null);
    const [brand, setBrand] = useState(locked ? activeExample.brand : '');
    const [mode, setMode] = useState<PipelineMode>(
        locked ? activeExample.mode : 'quick',
    );
    const [scenario, setScenario] = useState(
        locked ? activeExample.scenario : '',
    );
    const [llmModel, setLlmModel] = useState<string>('');
    const [models, setModels] = useState<LLMModelInfo[]>([]);
    const [dragOver, setDragOver] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const pickFile = useCallback(() => inputRef.current?.click(), []);

    // Re-sync locked fields when the visitor switches example.
    useEffect(() => {
        if (!locked) return;
        setBrand(activeExample.brand);
        setMode(activeExample.mode);
        setScenario(activeExample.scenario);
    }, [locked, activeExample]);

    useEffect(() => {
        listLLMModels()
            .then((m) => {
                setModels(m);
                const firstAvail = m.find((x) => x.available);
                if (firstAvail) setLlmModel(firstAvail.id);
            })
            .catch(() => {
                // ignore: dropdown will be empty and submit will use server default
            });
    }, []);

    const onDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) setFile(f);
    }, []);

    const onSubmit = useCallback(
        async (e: FormEvent) => {
            e.preventDefault();
            setError(null);
            if (locked) {
                // Demo mode: skip file/brand validation, route straight to the
                // pre-built scenario matching the visitor's selection.
                setSubmitting(true);
                try {
                    const res = await createReport({
                        // file is required by the type but ignored by the mock branch
                        file: new File([''], activeExample.fileName),
                        brand: activeExample.brand,
                        mode: activeExample.mode,
                        enable_simulation: true,
                        scenario_brief: activeExample.scenario,
                        mock_scenario_id: activeExample.scenarioId,
                    });
                    router.push(`/process/${res.run_id}`);
                } catch (err: unknown) {
                    setError(
                        (err instanceof Error ? err.message : String(err)) ??
                            'error',
                    );
                    setSubmitting(false);
                }
                return;
            }
            if (!file) {
                setError(t('upload.missing_file'));
                return;
            }
            if (!brand.trim()) {
                setError(t('upload.missing_brand'));
                return;
            }
            setSubmitting(true);
            try {
                const res = await createReport({
                    file,
                    brand: brand.trim(),
                    mode,
                    enable_simulation: mode === 'full',
                    scenario_brief: scenario.trim() || undefined,
                    llm_model: llmModel || undefined,
                });
                router.push(`/process/${res.run_id}`);
            } catch (err: unknown) {
                setError(
                    (err instanceof Error ? err.message : String(err)) ??
                        'error',
                );
                setSubmitting(false);
            }
        },
        [
            file,
            brand,
            mode,
            scenario,
            llmModel,
            router,
            t,
            locked,
            activeExample,
        ],
    );

    return (
        <form className="me-upload" onSubmit={onSubmit}>
            {locked && (
                <div className="me-demo-banner">
                    <strong>{t('upload.demo_banner_label')}</strong> ·{' '}
                    {t('upload.demo_banner_intro')}{' '}
                    <em>{t('upload.submit')}</em>{' '}
                    {t('upload.demo_banner_outro')}
                </div>
            )}
            {locked && (
                <fieldset className="me-example-picker">
                    <legend className="me-example-picker-legend">
                        {t('upload.example_picker_label')}
                    </legend>
                    <div className="me-example-picker-grid">
                        {EXAMPLE_ORDER.map((id) => {
                            const ex = MOCK_EXAMPLES[id];
                            const isActive = id === selectedExample;
                            return (
                                <button
                                    key={id}
                                    type="button"
                                    className={`me-example-card${isActive ? ' active' : ''}`}
                                    onClick={() => setSelectedExample(id)}
                                    aria-pressed={isActive}
                                >
                                    <span className="me-example-card-tag">
                                        {t(`upload.example_${id}_tag`)}
                                    </span>
                                    <span className="me-example-card-title">
                                        {t(`upload.example_${id}_title`)}
                                    </span>
                                    <span className="me-example-card-desc">
                                        {t(`upload.example_${id}_desc`)}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                </fieldset>
            )}
            <div
                className={`me-dropzone ${dragOver ? 'dragover' : ''}${locked ? ' locked' : ''}`}
                onClick={locked ? undefined : pickFile}
                onDragOver={(e) => {
                    if (locked) return;
                    e.preventDefault();
                    setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={locked ? undefined : onDrop}
                role={locked ? undefined : 'button'}
                tabIndex={locked ? -1 : 0}
                aria-disabled={locked}
            >
                <div className="me-dropzone-label">
                    {t('upload.dropzone_label')}
                </div>
                <div className="me-dropzone-title">
                    {locked
                        ? t('upload.attached_file')
                        : t('upload.dropzone_title')}
                </div>
                <div className="me-dropzone-hint">
                    {locked
                        ? activeExample.attachedMeta
                        : t('upload.dropzone_hint')}
                </div>
                {(file || locked) && (
                    <div className="me-dropzone-file">
                        {locked ? activeExample.fileName : file!.name}
                    </div>
                )}
                {!locked && (
                    <input
                        ref={inputRef}
                        type="file"
                        accept=".csv,.tsv,.xlsx,.xls,.pdf,.md,.markdown,.txt"
                        style={{ display: 'none' }}
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                )}
            </div>

            <div className="me-sample-link">
                <span>{t('upload.sample_label')}</span>
                <a
                    href={`${BASE_PATH}/sample-datasets/verdaia_esg_mentions_2026Q1.csv`}
                    download
                    onClick={(e) => e.stopPropagation()}
                >
                    ↓ verdaia_esg_mentions_2026Q1.csv
                </a>
                <span className="me-sample-meta">
                    {t('upload.sample_meta')}
                </span>
                <span className="me-sample-sep" aria-hidden>
                    ·
                </span>
                <a
                    href={`${BASE_PATH}/sample-datasets/nordalatte_recall_brief.pdf`}
                    download
                    onClick={(e) => e.stopPropagation()}
                >
                    ↓ nordalatte_recall_brief.pdf
                </a>
                <span className="me-sample-meta">
                    {t('upload.sample_meta_nordalatte')}
                </span>
            </div>

            <div className="me-form-grid" style={{ marginTop: 32 }}>
                <label className="me-field">
                    <span className="me-field-label">
                        {t('upload.brand_label')}
                    </span>
                    <input
                        className="me-field-input"
                        type="text"
                        value={brand}
                        onChange={(e) => setBrand(e.target.value)}
                        placeholder={t('upload.brand_placeholder')}
                        readOnly={locked}
                        disabled={locked}
                    />
                    <span className="me-field-hint">
                        {t('upload.brand_hint')}
                    </span>
                </label>
                <label className="me-field">
                    <span className="me-field-label">
                        {t('upload.mode_label')}
                    </span>
                    <select
                        className="me-field-select"
                        value={mode}
                        onChange={(e) =>
                            setMode(e.target.value as PipelineMode)
                        }
                        disabled={locked}
                    >
                        <option value="quick">{t('upload.mode_quick')}</option>
                        <option value="full">{t('upload.mode_full')}</option>
                    </select>
                    <span className="me-field-hint">
                        {mode === 'full'
                            ? t('upload.mode_full_hint')
                            : t('upload.mode_quick_hint')}
                    </span>
                </label>
                {models.length > 0 && (
                    <label className="me-field">
                        <span className="me-field-label">
                            {t('upload.llm_label')}
                        </span>
                        <select
                            className="me-field-select"
                            value={llmModel}
                            onChange={(e) => setLlmModel(e.target.value)}
                            disabled={locked}
                        >
                            {models.map((m) => (
                                <option
                                    key={m.id}
                                    value={m.id}
                                    disabled={!m.available}
                                >
                                    {m.label}
                                    {m.available
                                        ? ''
                                        : ` — ${t('upload.llm_missing_key')}`}
                                </option>
                            ))}
                        </select>
                        <span className="me-field-hint">
                            {models.find((m) => m.id === llmModel)?.notes ||
                                t('upload.llm_hint_default')}
                        </span>
                    </label>
                )}
            </div>

            {mode === 'full' && (
                <p
                    className="me-field-hint"
                    style={{ marginTop: 16, opacity: 0.75 }}
                >
                    {t('upload.sim_hint')}
                </p>
            )}

            <label className="me-field" style={{ marginTop: 24 }}>
                <span className="me-field-label">
                    {t('upload.scenario_label')}
                </span>
                <textarea
                    className="me-field-input"
                    rows={8}
                    value={scenario}
                    onChange={(e) => setScenario(e.target.value)}
                    placeholder={t('upload.scenario_placeholder')}
                    style={{
                        resize: 'vertical',
                        fontFamily: 'var(--mono)',
                        fontSize: 13,
                        lineHeight: 1.5,
                        minHeight: 160,
                    }}
                    maxLength={4000}
                    readOnly={locked}
                    disabled={locked}
                />
                <span className="me-field-hint">
                    {t('upload.scenario_hint')} — {scenario.length}/4000
                </span>
            </label>

            <div
                style={{
                    marginTop: 32,
                    display: 'flex',
                    gap: 12,
                    alignItems: 'center',
                }}
            >
                <button className="me-btn" type="submit" disabled={submitting}>
                    {submitting ? t('upload.submitting') : t('upload.submit')}
                    <span
                        style={{ fontFamily: 'var(--display)', fontSize: 14 }}
                    >
                        →
                    </span>
                </button>
                {error && (
                    <span
                        style={{
                            color: 'var(--red)',
                            fontFamily: 'var(--mono)',
                            fontSize: 11,
                            letterSpacing: '0.1em',
                            textTransform: 'uppercase',
                        }}
                    >
                        {t('upload.error')} {error}
                    </span>
                )}
            </div>
        </form>
    );
}
