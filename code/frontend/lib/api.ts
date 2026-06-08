import type {
    PipelineMode,
    RunRecord,
    RunStatus,
    SimulationStatus,
    SourceType,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

/**
 * Data source switch.
 * - `api` (default): hit the FastAPI backend at API_BASE.
 * - `mock`: read static JSON snapshots from /public/scenarios/<id>/*.json.
 *
 * Set via `NEXT_PUBLIC_DATA_SOURCE=mock npm run build` for the static demo
 * (GitHub Pages / Aruba). Each `runId` becomes a scenario directory under
 * /public/scenarios. See [public/scenarios/README.md] for layout.
 */
export const DATA_SOURCE: 'api' | 'mock' =
    process.env.NEXT_PUBLIC_DATA_SOURCE === 'mock' ? 'mock' : 'api';

/**
 * Base path prefix for static assets under public/ when the app is
 * deployed under a sub-path (e.g. /experiments/miroedo/ on Aruba).
 * Mirrors NEXT_PUBLIC_BASE_PATH from next.config.ts.
 */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

/** Base path for static scenario JSONs (relative to public/). */
const SCENARIOS_BASE =
    process.env.NEXT_PUBLIC_SCENARIOS_BASE ?? `${BASE_PATH}/scenarios`;

/** List of scenario IDs exposed by the static demo. Read by ScenarioCards. */
export const MOCK_SCENARIO_IDS = (
    process.env.NEXT_PUBLIC_MOCK_SCENARIOS ?? 'esg-retailer,nordalatte'
)
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

export class ApiError extends Error {
    constructor(
        public status: number,
        message: string,
    ) {
        super(message);
        this.name = 'ApiError';
    }
}

/** Fetch a static JSON file shipped with the build. */
async function fetchStatic<T>(path: string): Promise<T> {
    const res = await fetch(path, { cache: 'no-store' });
    if (!res.ok) {
        throw new ApiError(
            res.status,
            `${res.status} ${res.statusText} — ${path}`,
        );
    }
    return (await res.json()) as T;
}

async function handle<T>(res: Response): Promise<T> {
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const data = await res.json();
            detail =
                typeof data?.detail === 'string'
                    ? data.detail
                    : JSON.stringify(data);
        } catch {
            // ignore
        }
        throw new ApiError(res.status, `${res.status} ${detail}`);
    }
    return (await res.json()) as T;
}

export async function getHealth(): Promise<{
    status: string;
    service: string;
    version: string;
}> {
    if (DATA_SOURCE === 'mock') {
        return { status: 'ok', service: 'miroedo-demo', version: 'static' };
    }
    const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
    return handle(res);
}

export async function listReports(limit = 50): Promise<RunRecord[]> {
    if (DATA_SOURCE === 'mock') {
        const recs = await Promise.all(
            MOCK_SCENARIO_IDS.slice(0, limit).map((id) =>
                fetchStatic<RunRecord>(`${SCENARIOS_BASE}/${id}/run.json`),
            ),
        );
        return recs;
    }
    const res = await fetch(`${API_BASE}/reports?limit=${limit}`, {
        cache: 'no-store',
    });
    return handle(res);
}

export async function getReport(runId: string): Promise<RunRecord> {
    if (DATA_SOURCE === 'mock') {
        const rec = await fetchStatic<RunRecord>(
            `${SCENARIOS_BASE}/${encodeURIComponent(runId)}/run.json`,
        );
        return applyMockProgress(rec);
    }
    const res = await fetch(
        `${API_BASE}/reports/${encodeURIComponent(runId)}`,
        {
            cache: 'no-store',
        },
    );
    return handle(res);
}

// ── Fake progressive run (mock mode only) ───────────────────────────────
//
// When the user clicks “Avvia analisi” in the static demo we stamp a
// per-run timestamp in sessionStorage; subsequent getReport polls return
// a progressively-built RunRecord until the synthetic timeline ends, then
// fall back to the canonical snapshot. Lets visitors watch the wizard
// stream through ingest → KPI → simulation just like the real backend.

const MOCK_TIMELINE: Array<{
    untilMs: number;
    status: RunStatus;
    step: string;
    pct: number;
    note: string;
    sim?: SimulationStatus;
    simStep?: string;
    simPct?: number;
}> = [
    {
        untilMs: 1_200,
        status: 'running',
        step: 'ingest',
        pct: 4,
        note: 'Reading file · detect encoding (UTF-8)',
    },
    {
        untilMs: 2_500,
        status: 'running',
        step: 'ingest',
        pct: 8,
        note: 'Parsing 8.742 rows · 9 columns · schema=brandwatch_csv',
    },
    {
        untilMs: 4_000,
        status: 'running',
        step: 'ingest',
        pct: 14,
        note: 'Normalizing language (it/en) · dedup 312 duplicates',
    },
    {
        untilMs: 5_500,
        status: 'running',
        step: 'ingest',
        pct: 22,
        note: 'Embedding 8.430 mentions (bge-m3) · batch 8/27',
    },
    {
        untilMs: 7_000,
        status: 'running',
        step: 'baseline_report',
        pct: 30,
        note: 'Clustering topics (HDBSCAN) · 10 clusters detected',
    },
    {
        untilMs: 8_500,
        status: 'running',
        step: 'baseline_report',
        pct: 38,
        note: 'Scoring sentiment per topic (gpt-4o)',
    },
    {
        untilMs: 10_000,
        status: 'running',
        step: 'kpi',
        pct: 46,
        note: 'Aggregating segments · 5 segments · 6 platforms',
    },
    {
        untilMs: 11_500,
        status: 'running',
        step: 'kpi',
        pct: 54,
        note: 'Computing share-of-voice · building treemap',
    },
    {
        untilMs: 13_000,
        status: 'running',
        step: 'executive_summary',
        pct: 62,
        note: 'Drafting executive summary (gpt-4o · stream)',
    },
    {
        untilMs: 14_800,
        status: 'running',
        step: 'executive_summary',
        pct: 70,
        note: 'Extracting 5 highlights · 1 warning',
    },
    {
        untilMs: 16_300,
        status: 'running',
        step: 'action_plan',
        pct: 78,
        note: 'Scoring drivers · 4 drivers ranked',
    },
    {
        untilMs: 17_700,
        status: 'running',
        step: 'action_plan',
        pct: 86,
        note: 'Building 72h action plan · 5 actions',
    },
    {
        untilMs: 19_000,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'Baseline report ready (5 capitoli, 2.840 parole)',
        sim: 'pending',
        simStep: 'queued',
        simPct: 0,
    },
    {
        untilMs: 20_500,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'OASIS bootstrap · generating personas 30/120',
        sim: 'running',
        simStep: 'profiles',
        simPct: 12,
    },
    {
        untilMs: 22_000,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'OASIS bootstrap · personas 120/120 · seeding feed',
        sim: 'running',
        simStep: 'profiles',
        simPct: 22,
    },
    {
        untilMs: 24_000,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'Round 3/10 · streaming actions · 1.024 events',
        sim: 'running',
        simStep: 'rounds',
        simPct: 45,
    },
    {
        untilMs: 26_000,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'Round 7/10 · streaming actions · 2.840 events',
        sim: 'running',
        simStep: 'rounds',
        simPct: 68,
    },
    {
        untilMs: 28_000,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'Round 10/10 · finalizing · 4.127 events total',
        sim: 'running',
        simStep: 'rounds',
        simPct: 82,
    },
    {
        untilMs: 30_000,
        status: 'succeeded',
        step: 'completed',
        pct: 100,
        note: 'Building Zep knowledge graph · 247 facts',
        sim: 'running',
        simStep: 'zep',
        simPct: 95,
    },
];

const MOCK_TOTAL_MS = 32_000;

function mockStartKey(runId: string) {
    return `miroedo_mock_started_${runId}`;
}

export function startMockRun(runId: string) {
    if (typeof window === 'undefined') return;
    try {
        window.sessionStorage.setItem(mockStartKey(runId), String(Date.now()));
    } catch {
        // sessionStorage disabled — fall through and snapshot will render instantly
    }
}

function applyMockProgress(rec: RunRecord): RunRecord {
    if (typeof window === 'undefined') return rec;
    let startedAt: number | null = null;
    try {
        const raw = window.sessionStorage.getItem(mockStartKey(rec.run_id));
        startedAt = raw ? Number(raw) : null;
    } catch {
        startedAt = null;
    }
    if (!startedAt || Number.isNaN(startedAt)) return rec;
    const elapsed = Date.now() - startedAt;
    if (elapsed >= MOCK_TOTAL_MS) return rec;
    const stage =
        MOCK_TIMELINE.find((s) => elapsed < s.untilMs) ??
        MOCK_TIMELINE[MOCK_TIMELINE.length - 1];
    return {
        ...rec,
        status: stage.status,
        progress: {
            step: stage.step,
            percent: stage.pct,
            note: stage.note,
        },
        simulation_status: stage.sim ?? 'idle',
        simulation_progress: stage.sim
            ? { step: stage.simStep, percent: stage.simPct }
            : { step: 'idle' },
        // While the run is still “computing” we hide the final result so the
        // process page renders the live progress UI rather than the success CTAs.
        result:
            stage.status === 'succeeded' && stage.sim === undefined
                ? rec.result
                : null,
    };
}

export interface CreateReportInput {
    file: File;
    brand: string;
    source_type?: SourceType;
    mode?: PipelineMode;
    enable_simulation?: boolean;
    scenario_brief?: string;
    llm_model?: string;
    /**
     * Mock-only override. When DATA_SOURCE === 'mock', forces the wizard to
     * route to this specific pre-built scenario instead of the first one in
     * MOCK_SCENARIO_IDS. Ignored in API mode.
     */
    mock_scenario_id?: string;
}

export interface CreateReportResponse {
    run_id: string;
    status: string;
    mode: string;
    brand: string;
}

export async function createReport(
    input: CreateReportInput,
): Promise<CreateReportResponse> {
    if (DATA_SOURCE === 'mock') {
        // Static demo: no upload pipeline. Redirect the caller to the requested
        // pre-built scenario (or the first one if none specified) so the wizard
        // flow ends gracefully.
        const requested = input.mock_scenario_id?.trim();
        const runId =
            requested && MOCK_SCENARIO_IDS.includes(requested)
                ? requested
                : (MOCK_SCENARIO_IDS[0] ?? 'esg-retailer');
        // Stamp the start time so subsequent getReport calls replay the
        // fake progressive pipeline before exposing the snapshot.
        startMockRun(runId);
        return {
            run_id: runId,
            status: 'queued',
            mode: input.mode ?? 'quick',
            brand: input.brand,
        };
    }
    const fd = new FormData();
    fd.append('file', input.file);
    fd.append('brand', input.brand);
    if (input.source_type) {
        fd.append('source_type', input.source_type);
    }
    fd.append('mode', input.mode ?? 'quick');
    if (input.enable_simulation !== undefined) {
        fd.append('enable_simulation', String(input.enable_simulation));
    }
    if (input.scenario_brief && input.scenario_brief.trim()) {
        fd.append('scenario_brief', input.scenario_brief.trim());
    }
    if (input.llm_model && input.llm_model.trim()) {
        fd.append('llm_model', input.llm_model.trim());
    }
    const res = await fetch(`${API_BASE}/reports`, {
        method: 'POST',
        body: fd,
    });
    return handle(res);
}

/** Poll a run until it reaches a terminal status or timeout. */
export async function pollRun(
    runId: string,
    opts: {
        intervalMs?: number;
        timeoutMs?: number;
        onUpdate?: (rec: RunRecord) => void;
        signal?: AbortSignal;
    } = {},
): Promise<RunRecord> {
    const interval = opts.intervalMs ?? 2000;
    const timeout = opts.timeoutMs ?? 5 * 60_000;
    const start = Date.now();
    while (true) {
        if (opts.signal?.aborted) throw new Error('aborted');
        const rec = await getReport(runId);
        opts.onUpdate?.(rec);
        if (rec.status === 'succeeded' || rec.status === 'failed') return rec;
        if (Date.now() - start > timeout) throw new Error('poll timeout');
        await new Promise((r) => setTimeout(r, interval));
    }
}

// === Simulation (on-demand OASIS run) ===

export interface SimulationRequest {
    profiles: number;
    rounds: number;
    model?: string;
}

export async function runSimulation(
    runId: string,
    body: SimulationRequest,
): Promise<RunRecord> {
    if (DATA_SOURCE === 'mock') {
        // In mock mode the simulation already lives in the static snapshot.
        return getReport(runId);
    }
    const res = await fetch(`${API_BASE}/reports/${runId}/simulation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return handle(res);
}

// === Per-action stream (live terminal feed) ===

export interface ActionRow {
    event: string;
    round?: number;
    rowid?: number;
    agent_id?: number | null;
    action?: string;
    info?: string | null;
    created_at?: string;
    actions_count?: number;
    profiles?: number;
    rounds?: number;
    seed_posts?: number;
    kind?: string;
}

export interface ActionsResponse {
    run_id: string;
    cursor: number;
    rows: ActionRow[];
    done: boolean;
}

export async function fetchActions(
    runId: string,
    cursor: number,
    limit = 500,
): Promise<ActionsResponse> {
    if (DATA_SOURCE === 'mock') {
        // Static scenarios ship the full actions log up-front. We slice it
        // client-side so the LiveSimulation tail UI keeps working unchanged.
        const all = await fetchStatic<ActionRow[]>(
            `${SCENARIOS_BASE}/${encodeURIComponent(runId)}/actions.json`,
        ).catch(() => [] as ActionRow[]);
        const slice = all.slice(cursor, cursor + limit);
        return {
            run_id: runId,
            cursor: cursor + slice.length,
            rows: slice,
            done: cursor + slice.length >= all.length,
        };
    }
    const res = await fetch(
        `${API_BASE}/reports/${encodeURIComponent(runId)}/actions?cursor=${cursor}&limit=${limit}`,
        { cache: 'no-store' },
    );
    return handle(res);
}

/** Poll until simulation_status reaches a terminal state. */
export async function pollSimulation(
    runId: string,
    opts: {
        intervalMs?: number;
        timeoutMs?: number;
        onUpdate?: (rec: RunRecord) => void;
        signal?: AbortSignal;
    } = {},
): Promise<RunRecord> {
    const interval = opts.intervalMs ?? 3000;
    const timeout = opts.timeoutMs ?? 20 * 60_000;
    const start = Date.now();
    while (true) {
        if (opts.signal?.aborted) throw new Error('aborted');
        const rec = await getReport(runId);
        opts.onUpdate?.(rec);
        const s = rec.simulation_status;
        if (s === 'succeeded' || s === 'failed') return rec;
        if (Date.now() - start > timeout)
            throw new Error('simulation poll timeout');
        await new Promise((r) => setTimeout(r, interval));
    }
}

// === Chat ===

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
    role: ChatRole;
    content: string;
}

export interface ChatSection {
    sid: string;
    title: string;
    level: number;
}

export interface ChatResponse {
    run_id: string;
    answer: string;
    citations: string[];
    confidence: 'low' | 'medium' | 'high';
    out_of_scope: boolean;
    sections: ChatSection[];
}

export async function chatWithReport(
    runId: string,
    question: string,
    history: ChatMessage[] = [],
): Promise<ChatResponse> {
    if (DATA_SOURCE === 'mock') {
        return mockChatAnswer(runId, question);
    }
    const res = await fetch(
        `${API_BASE}/reports/${encodeURIComponent(runId)}/chat`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, history }),
        },
    );
    return handle(res);
}

// === Streaming chat (SSE) ===

export interface ChatStreamMeta {
    answer: string;
    citations: string[];
    confidence: 'low' | 'medium' | 'high';
    out_of_scope: boolean;
    sections: ChatSection[];
}

export interface ChatStreamCallbacks {
    onToken?: (delta: string) => void;
    onMeta?: (meta: ChatStreamMeta) => void;
    onError?: (detail: string) => void;
    onDone?: () => void;
    signal?: AbortSignal;
}

/**
 * Open an SSE stream to /chat/stream. Returns a promise that resolves when
 * the stream is fully consumed (or aborted).
 */
export async function chatWithReportStream(
    runId: string,
    question: string,
    history: ChatMessage[],
    cb: ChatStreamCallbacks,
): Promise<void> {
    if (DATA_SOURCE === 'mock') {
        const reply = await mockChatAnswer(runId, question);
        // Simulate token-by-token streaming for the demo UI.
        for (const tok of reply.answer.match(/.{1,4}/g) ?? []) {
            if (cb.signal?.aborted) return;
            cb.onToken?.(tok);
            await new Promise((r) => setTimeout(r, 12));
        }
        cb.onMeta?.({
            answer: reply.answer,
            citations: reply.citations,
            confidence: reply.confidence,
            out_of_scope: reply.out_of_scope,
            sections: reply.sections,
        });
        cb.onDone?.();
        return;
    }
    const res = await fetch(
        `${API_BASE}/reports/${encodeURIComponent(runId)}/chat/stream`,
        {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'text/event-stream',
            },
            body: JSON.stringify({ question, history }),
            signal: cb.signal,
        },
    );
    if (!res.ok || !res.body) {
        const text = await res.text().catch(() => '');
        throw new Error(
            `chat/stream HTTP ${res.status}: ${text || res.statusText}`,
        );
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    const flushEvents = () => {
        // Split on blank line (\n\n)
        let idx = buf.indexOf('\n\n');
        while (idx >= 0) {
            const raw = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            handleEvent(raw, cb);
            idx = buf.indexOf('\n\n');
        }
    };

    try {
        for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            flushEvents();
        }
        // Flush any tail
        if (buf.trim()) handleEvent(buf, cb);
        cb.onDone?.();
    } catch (e: unknown) {
        if ((e as { name?: string })?.name !== 'AbortError') {
            cb.onError?.(e instanceof Error ? e.message : 'stream error');
        }
    }
}

function handleEvent(raw: string, cb: ChatStreamCallbacks) {
    const lines = raw.split('\n');
    let event = 'message';
    let data = '';
    for (const line of lines) {
        if (line.startsWith('event: ')) {
            event = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
            data += line.slice(6);
        }
    }
    if (!data) return;
    try {
        const parsed = JSON.parse(data);
        if (event === 'token' && typeof parsed === 'string') {
            cb.onToken?.(parsed);
        } else if (event === 'meta') {
            cb.onMeta?.(parsed as ChatStreamMeta);
        } else if (event === 'error') {
            cb.onError?.(parsed?.detail || 'stream error');
        }
    } catch {
        // ignore malformed event
    }
}

// === ReAct chat agent (tool-using) ===

export interface ChatAgentToolCall {
    name: string;
    parameters: Record<string, unknown>;
    result_excerpt: string;
    error?: string | null;
}

export interface ChatAgentResponse {
    run_id: string;
    answer: string;
    tool_calls: ChatAgentToolCall[];
    sections: ChatSection[];
}

export async function chatAgent(
    runId: string,
    question: string,
    history: ChatMessage[] = [],
): Promise<ChatAgentResponse> {
    if (DATA_SOURCE === 'mock') {
        const reply = await mockChatAnswer(runId, question);
        return {
            run_id: runId,
            answer: reply.answer,
            tool_calls: [],
            sections: reply.sections,
        };
    }
    const res = await fetch(
        `${API_BASE}/reports/${encodeURIComponent(runId)}/chat/agent`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, history }),
        },
    );
    return handle(res);
}

// === LLM model catalog ===

export interface LLMModelInfo {
    id: string;
    label: string;
    provider: string;
    model: string;
    available: boolean;
    notes?: string;
}

export async function listLLMModels(): Promise<LLMModelInfo[]> {
    if (DATA_SOURCE === 'mock') {
        return [
            {
                id: 'gpt-4o',
                label: 'GPT-4o (demo)',
                provider: 'openai',
                model: 'gpt-4o',
                available: true,
                notes: 'Static demo — outputs are pre-computed',
            },
        ];
    }
    const res = await fetch(`${API_BASE}/llm/models`, { cache: 'no-store' });
    const data = await handle<{ models: LLMModelInfo[] }>(res);
    return data.models || [];
}

// === Mock helpers ===

interface MockChatEntry {
    match: string; // case-insensitive substring; '' = fallback
    answer: string;
    citations?: string[];
    confidence?: 'low' | 'medium' | 'high';
    sections?: ChatSection[];
}

/**
 * Pick the first matching Q&A from `scenarios/<id>/chat.json`, otherwise
 * return a generic placeholder. Lets the demo answer common questions
 * without an LLM round-trip.
 */
async function mockChatAnswer(
    runId: string,
    question: string,
): Promise<ChatResponse> {
    const q = question.toLowerCase();
    let entries: MockChatEntry[] = [];
    try {
        entries = await fetchStatic<MockChatEntry[]>(
            `${SCENARIOS_BASE}/${encodeURIComponent(runId)}/chat.json`,
        );
    } catch {
        // no chat.json shipped for this scenario — fall through to placeholder
    }
    const hit =
        entries.find((e) => e.match && q.includes(e.match.toLowerCase())) ??
        entries.find((e) => !e.match);
    if (hit) {
        return {
            run_id: runId,
            answer: hit.answer,
            citations: hit.citations ?? [],
            confidence: hit.confidence ?? 'medium',
            out_of_scope: false,
            sections: hit.sections ?? [],
        };
    }
    return {
        run_id: runId,
        answer: 'This is a static demo. The full chat interface is available when running the backend locally — see the README.',
        citations: [],
        confidence: 'low',
        out_of_scope: true,
        sections: [],
    };
}
