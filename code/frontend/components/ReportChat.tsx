'use client';

import Link from 'next/link';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
    chatAgent,
    chatWithReportStream,
    type ChatAgentToolCall,
    type ChatMessage,
    type ChatSection,
} from '@/lib/api';
import { useT } from '@/lib/i18n';

interface Props {
    runId: string;
    brand: string;
    suggestions?: string[];
}

interface AssistantMeta {
    citations: string[];
    confidence: 'low' | 'medium' | 'high';
    out_of_scope: boolean;
}

interface UiMessage extends ChatMessage {
    meta?: AssistantMeta;
    streaming?: boolean;
    tool_calls?: ChatAgentToolCall[];
}

export default function ReportChat({ runId, brand, suggestions }: Props) {
    const { t } = useT();
    const [messages, setMessages] = useState<UiMessage[]>([]);
    const [sections, setSections] = useState<Record<string, ChatSection>>({});
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [agentMode, setAgentMode] = useState(false);
    const endRef = useRef<HTMLDivElement | null>(null);
    const inputRef = useRef<HTMLTextAreaElement | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, sending]);

    useEffect(() => () => abortRef.current?.abort(), []);

    const send = async (text: string) => {
        const q = text.trim();
        if (!q || sending) return;
        setError(null);
        const history: ChatMessage[] = messages.map((m) => ({
            role: m.role,
            content: m.content,
        }));
        // Push user + empty assistant placeholder
        setMessages([
            ...messages,
            { role: 'user', content: q },
            { role: 'assistant', content: '', streaming: true },
        ]);
        setInput('');
        setSending(true);

        const controller = new AbortController();
        abortRef.current = controller;

        const updateAssistant = (fn: (prev: UiMessage) => UiMessage) => {
            setMessages((curr) => {
                const idx = curr.length - 1;
                if (idx < 0) return curr;
                const next = curr.slice();
                next[idx] = fn(next[idx]);
                return next;
            });
        };

        // Agent mode: ReAct loop with 6 tools (non-streaming).
        if (agentMode) {
            try {
                const resp = await chatAgent(runId, q, history);
                if (resp.sections?.length) {
                    setSections(
                        Object.fromEntries(
                            resp.sections.map((s) => [s.sid, s]),
                        ),
                    );
                }
                updateAssistant((m) => ({
                    ...m,
                    content: resp.answer || '',
                    streaming: false,
                    tool_calls: resp.tool_calls,
                }));
            } catch (e: unknown) {
                setError(e instanceof Error ? e.message : 'agent error');
                updateAssistant((m) => ({ ...m, streaming: false }));
            } finally {
                setSending(false);
                abortRef.current = null;
                inputRef.current?.focus();
            }
            return;
        }

        try {
            await chatWithReportStream(runId, q, history, {
                signal: controller.signal,
                onToken: (delta) =>
                    updateAssistant((m) => ({
                        ...m,
                        content: (m.content || '') + delta,
                    })),
                onMeta: (meta) => {
                    if (meta.sections?.length) {
                        setSections(
                            Object.fromEntries(
                                meta.sections.map((s) => [s.sid, s]),
                            ),
                        );
                    }
                    updateAssistant((m) => ({
                        ...m,
                        content: meta.answer || m.content,
                        streaming: false,
                        meta: {
                            citations: meta.citations || [],
                            confidence: meta.confidence || 'medium',
                            out_of_scope: !!meta.out_of_scope,
                        },
                    }));
                },
                onError: (detail) => {
                    setError(detail);
                    updateAssistant((m) => ({ ...m, streaming: false }));
                },
            });
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'chat error');
            updateAssistant((m) => ({ ...m, streaming: false }));
        } finally {
            setSending(false);
            abortRef.current = null;
            inputRef.current?.focus();
        }
    };

    const onSubmit = (e: FormEvent) => {
        e.preventDefault();
        void send(input);
    };

    const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            void send(input);
        }
    };

    return (
        <div className="me-chat">
            <div className="me-chat-header">
                <span className="me-chat-header-eyebrow">
                    {t('interaction.eyebrow')}
                </span>
                <span className="me-chat-header-brand">{brand}</span>
            </div>

            <div className="me-chat-thread" role="log" aria-live="polite">
                {messages.length === 0 && (
                    <div className="me-chat-empty">
                        <div className="me-chat-empty-title">
                            {t('interaction.empty_title')}
                        </div>
                        <div className="me-chat-empty-sub">
                            {t('interaction.empty_sub')}
                        </div>
                        {suggestions && suggestions.length > 0 && (
                            <div className="me-chat-suggestions">
                                {suggestions.map((s) => (
                                    <button
                                        type="button"
                                        key={s}
                                        className="hint"
                                        onClick={() => void send(s)}
                                    >
                                        {s}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {messages.map((m, i) => (
                    <div key={i} className={`me-chat-msg ${m.role}`}>
                        <div className="me-chat-msg-role">
                            {m.role === 'user'
                                ? t('interaction.you')
                                : 'MIROEDO'}
                            {m.role === 'assistant' && m.meta && (
                                <span
                                    className={`me-chat-conf conf-${m.meta.confidence}`}
                                    title={t('interaction.confidence')}
                                >
                                    {m.meta.confidence.toUpperCase()}
                                </span>
                            )}
                        </div>
                        {m.role === 'assistant' && m.meta?.out_of_scope && (
                            <div className="me-chat-oos">
                                {t('interaction.out_of_scope')}
                            </div>
                        )}
                        {m.role === 'assistant' &&
                            m.tool_calls &&
                            m.tool_calls.length > 0 && (
                                <div
                                    style={{
                                        margin: '6px 0 8px',
                                        padding: '6px 8px',
                                        background: '#f5f5f5',
                                        border: '1px solid #ddd',
                                        fontFamily: 'var(--mono)',
                                        fontSize: 11,
                                    }}
                                >
                                    <div
                                        style={{
                                            color: 'var(--red)',
                                            letterSpacing: '0.15em',
                                            marginBottom: 4,
                                        }}
                                    >
                                        TOOL CALLS ({m.tool_calls.length})
                                    </div>
                                    {m.tool_calls.map((tc, j) => (
                                        <details
                                            key={j}
                                            style={{ marginBottom: 3 }}
                                        >
                                            <summary
                                                style={{ cursor: 'pointer' }}
                                            >
                                                <strong>{tc.name}</strong>(
                                                {Object.entries(tc.parameters)
                                                    .map(
                                                        ([k, v]) =>
                                                            `${k}=${JSON.stringify(v)}`,
                                                    )
                                                    .join(', ')}
                                                )
                                            </summary>
                                            <pre
                                                style={{
                                                    margin: '4px 0 0 12px',
                                                    whiteSpace: 'pre-wrap',
                                                    color: '#444',
                                                    fontSize: 10,
                                                }}
                                            >
                                                {tc.result_excerpt ||
                                                    '(no output)'}
                                            </pre>
                                        </details>
                                    ))}
                                </div>
                            )}
                        <div className="me-chat-msg-body">
                            {m.role === 'assistant' &&
                            m.streaming &&
                            !m.content ? (
                                <span className="me-chat-msg-typing">
                                    {t('interaction.thinking')}
                                </span>
                            ) : (
                                <>
                                    {m.content}
                                    {m.role === 'assistant' && m.streaming && (
                                        <span className="me-chat-cursor" />
                                    )}
                                </>
                            )}
                        </div>
                        {m.role === 'assistant' &&
                            m.meta &&
                            m.meta.citations.length > 0 && (
                                <div className="me-chat-cites">
                                    <span className="me-chat-cites-label">
                                        {t('interaction.sources')}
                                    </span>
                                    {m.meta.citations.map((sid) => {
                                        const sec = sections[sid];
                                        const label = sec
                                            ? `${sid} · ${sec.title}`
                                            : sid;
                                        return (
                                            <Link
                                                key={sid}
                                                href={`/report/${runId}#${sid.toLowerCase()}`}
                                                className="me-chat-cite"
                                                title={sec?.title || sid}
                                            >
                                                {label}
                                            </Link>
                                        );
                                    })}
                                </div>
                            )}
                    </div>
                ))}

                <div ref={endRef} />
            </div>

            {error && <div className="me-chat-error">{error}</div>}

            <form className="me-chat-form" onSubmit={onSubmit}>
                <textarea
                    ref={inputRef}
                    className="me-chat-input"
                    placeholder={t('interaction.placeholder')}
                    rows={2}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={onKeyDown}
                    disabled={sending}
                />
                <div className="me-chat-actions">
                    <button
                        type="submit"
                        className="me-chat-send"
                        disabled={sending || !input.trim()}
                    >
                        {sending ? '…' : t('interaction.send')}
                    </button>
                    <label
                        className={`me-chat-agent${agentMode ? ' active' : ''}`}
                        title="ReAct loop con 6 tool (local + Zep + interview)"
                    >
                        <input
                            type="checkbox"
                            checked={agentMode}
                            onChange={(e) => setAgentMode(e.target.checked)}
                            disabled={sending}
                        />
                        AGENT
                    </label>
                </div>
            </form>

            <details className="me-chat-footnote">
                <summary>
                    <span className="me-chat-footnote-mode">
                        {agentMode ? '◆ AGENT · ReAct loop' : '◇ RAG streaming'}
                    </span>
                    <span className="me-chat-footnote-hint">
                        {agentMode
                            ? t('chat.footnote.mode_agent')
                            : t('chat.footnote.mode_rag')}
                    </span>
                    <span className="me-chat-footnote-toggle">
                        {t('chat.footnote.cta')}
                    </span>
                </summary>
                <div className="me-chat-footnote-body">
                    <div className="me-chat-footnote-col">
                        <strong>◇ RAG streaming</strong>{' '}
                        <em>{t('chat.footnote.rag_default')}</em>
                        <p>{t('chat.footnote.rag_body')}</p>
                    </div>
                    <div className="me-chat-footnote-col">
                        <strong>◆ AGENT · ReAct loop</strong>
                        <p>
                            {t('chat.footnote.agent_body')}{' '}
                            <code>search_report</code>, <code>query_zep</code>,{' '}
                            <code>query_dataset</code>,{' '}
                            <code>interview_persona</code>,{' '}
                            <code>compute_metric</code>,{' '}
                            <code>cite_source</code>.
                        </p>
                    </div>
                </div>
            </details>
        </div>
    );
}
