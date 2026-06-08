'use client';

import Link from 'next/link';
import { useT } from '@/lib/i18n';

const EDOEDOEDO_URL = 'https://www.edoedoedo.it/';
const GITHUB_URL = 'https://github.com/EdoEdoEdo';

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
    return (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="me-about-link"
        >
            {children}
            <span aria-hidden="true"> ↗</span>
        </a>
    );
}

export default function AboutPage() {
    const { t } = useT();

    return (
        <main className="me-about">
            <article className="me-about-doc">
                {/* HERO */}
                <header className="me-about-hero">
                    <div className="me-about-eyebrow">{t('about.eyebrow')}</div>
                    <h1 className="me-about-title">MIROEDO</h1>
                    <p className="me-about-tagline">{t('about.tagline')}</p>
                    <div className="me-about-by">
                        <span>{t('about.by')}</span>
                        <Ext href={EDOEDOEDO_URL}>
                            <s>
                                <em>
                                    <strong>EDOEDOEDO</strong>
                                </em>
                            </s>
                        </Ext>
                    </div>
                </header>

                {/* 01 — ORIGIN (parent project + flow diff) */}
                <section className="me-about-chapter">
                    <div className="me-about-chapter-num">01</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s0.title')}
                    </h2>
                    <p>{t('about.s0.p1')}</p>
                    <p>{t('about.s0.p2')}</p>
                    <h3 className="me-about-subtitle">
                        {t('about.s0.flow_title')}
                    </h3>
                    <table className="me-about-flowdiff">
                        <thead>
                            <tr>
                                <th>{t('about.s0.col_axis')}</th>
                                <th>{t('about.s0.col_mf')}</th>
                                <th>{t('about.s0.col_me')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <th scope="row">{t('about.s0.row1_label')}</th>
                                <td>{t('about.s0.row1_mf')}</td>
                                <td>{t('about.s0.row1_me')}</td>
                            </tr>
                            <tr>
                                <th scope="row">{t('about.s0.row2_label')}</th>
                                <td>{t('about.s0.row2_mf')}</td>
                                <td>{t('about.s0.row2_me')}</td>
                            </tr>
                            <tr>
                                <th scope="row">{t('about.s0.row3_label')}</th>
                                <td>{t('about.s0.row3_mf')}</td>
                                <td>{t('about.s0.row3_me')}</td>
                            </tr>
                            <tr>
                                <th scope="row">{t('about.s0.row4_label')}</th>
                                <td>{t('about.s0.row4_mf')}</td>
                                <td>{t('about.s0.row4_me')}</td>
                            </tr>
                        </tbody>
                    </table>
                </section>

                {/* 02 — PROBLEM */}
                <section className="me-about-chapter">
                    <div className="me-about-chapter-num">02</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s1.title')}
                    </h2>
                    <p>{t('about.s1.p1')}</p>
                    <p>{t('about.s1.p2')}</p>
                    <ul>
                        <li>{t('about.s1.li1')}</li>
                        <li>{t('about.s1.li2')}</li>
                        <li>{t('about.s1.li3')}</li>
                    </ul>
                </section>

                {/* 03 — METHOD */}
                <section className="me-about-chapter">
                    <div className="me-about-chapter-num">03</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s2.title')}
                    </h2>
                    <p>{t('about.s2.p1')}</p>
                    <pre className="me-about-pre">{`USER
  ↓
[1] Ingestion · CSV / XLSX / PDF / MD
  ↓ universal adapter → BrandSeed (Pydantic)
[2] Pipeline · KPI · drivers · scenarios · forecast · ontology
  ↓
[3] Simulation · OASIS (camel-ai) · LLM agents react
  ↓
[4] Report · markdown + KPIs + D3 charts + force graph
  ↓
[5] Interaction · ReAct chat agent (6 tools)`}</pre>
                </section>

                {/* 04 — FIVE ENGINES */}
                <section className="me-about-chapter">
                    <div className="me-about-chapter-num">04</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s3.title')}
                    </h2>
                    <p>{t('about.s3.p1')}</p>
                    <dl className="me-about-engines">
                        <dt>Ingestion Engine</dt>
                        <dd>{t('about.s3.e1')}</dd>
                        <dt>Insight Engine</dt>
                        <dd>{t('about.s3.e2')}</dd>
                        <dt>Media Engine</dt>
                        <dd>{t('about.s3.e3')}</dd>
                        <dt>Simulation Engine (OASIS)</dt>
                        <dd>{t('about.s3.e4')}</dd>
                        <dt>Report &amp; Query Engine</dt>
                        <dd>{t('about.s3.e5')}</dd>
                    </dl>
                </section>

                {/* 05 — TECH STACK */}
                <section className="me-about-chapter">
                    <div className="me-about-chapter-num">05</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s4.title')}
                    </h2>
                    <div className="me-about-stack">
                        <div>
                            <h4>Frontend</h4>
                            <p>
                                Next.js 15 · React 19 · TypeScript strict · D3
                                v7
                            </p>
                        </div>
                        <div>
                            <h4>Backend</h4>
                            <p>FastAPI · Python 3.11 · Pydantic 2</p>
                        </div>
                        <div>
                            <h4>Simulation</h4>
                            <p>
                                OASIS (camel-ai) · agent-based social simulation
                            </p>
                        </div>
                        <div>
                            <h4>LLM providers</h4>
                            <p>Mistral · Groq · OpenAI-compat</p>
                        </div>
                        <div>
                            <h4>Memory</h4>
                            <p>Zep graph memory (optional)</p>
                        </div>
                        <div>
                            <h4>Deploy</h4>
                            <p>Docker compose · static export (this demo)</p>
                        </div>
                    </div>
                </section>

                {/* 06 — DEMO FLOW */}
                <section className="me-about-chapter">
                    <div className="me-about-chapter-num">06</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s5.title')}
                    </h2>
                    <p>{t('about.s5.intro')}</p>
                    <ol className="me-about-flow">
                        <li>
                            <strong>{t('about.s5.f1t')}</strong>
                            <span>{t('about.s5.f1d')}</span>
                        </li>
                        <li>
                            <strong>{t('about.s5.f2t')}</strong>
                            <span>{t('about.s5.f2d')}</span>
                        </li>
                        <li>
                            <strong>{t('about.s5.f3t')}</strong>
                            <span>{t('about.s5.f3d')}</span>
                        </li>
                        <li>
                            <strong>{t('about.s5.f4t')}</strong>
                            <span>{t('about.s5.f4d')}</span>
                        </li>
                        <li>
                            <strong>{t('about.s5.f5t')}</strong>
                            <span>{t('about.s5.f5d')}</span>
                        </li>
                    </ol>
                </section>

                {/* 07 — AUTHOR */}
                <section className="me-about-chapter me-about-chapter-last">
                    <div className="me-about-chapter-num">07</div>
                    <h2 className="me-about-chapter-title">
                        {t('about.s6.title')}
                    </h2>
                    <p>{t('about.s6.p1')}</p>
                    <div className="me-about-cards">
                        <a
                            href={EDOEDOEDO_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="me-about-card"
                        >
                            <div className="me-about-card-eyebrow">
                                {t('about.s6.site_label')}
                            </div>
                            <div className="me-about-card-title">
                                <s>
                                    <em>
                                        <strong>EDOEDOEDO</strong>
                                    </em>
                                </s>
                            </div>
                            <div className="me-about-card-host">
                                edoedoedo.it ↗
                            </div>
                        </a>
                        <a
                            href={GITHUB_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="me-about-card"
                        >
                            <div className="me-about-card-eyebrow">
                                {t('about.s6.other_projects')}
                            </div>
                            <div className="me-about-card-title">GitHub</div>
                            <div className="me-about-card-host">
                                github.com/EdoEdoEdo ↗
                            </div>
                        </a>
                    </div>
                </section>

                <footer className="me-about-footer">
                    <Link href="/" className="me-btn">
                        ← {t('common.back_home')}
                    </Link>
                    <Link href="/process/new" className="me-btn ghost">
                        {t('about.cta_try')} →
                    </Link>
                </footer>
            </article>
        </main>
    );
}
