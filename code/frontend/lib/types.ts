// Backend run record + result types (mirror of app/api/reports.py).
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type SimulationStatus =
    | 'idle'
    | 'pending'
    | 'running'
    | 'succeeded'
    | 'failed';
export type PipelineMode = 'quick' | 'full';
export type SourceType =
    | 'tabular'
    | 'document'
    | 'manual'
    | 'brandwatch_csv'
    | 'brandwatch_pdf';

export interface Progress {
    step?: string;
    [k: string]: unknown;
}

export interface RunRecord {
    run_id: string;
    status: RunStatus;
    mode: PipelineMode;
    brand: string;
    source_type: SourceType;
    source_filename?: string | null;
    enable_simulation: boolean;
    created_at: string;
    updated_at: string;
    progress: Progress;
    result?: PipelineResult | null;
    error?: string | null;
    scenario_brief?: string | null;
    simulation_status?: SimulationStatus;
    simulation_error?: string | null;
    simulation_progress?: Progress;
}

export interface SegmentKPI {
    name: string;
    weight?: number;
    sentiment_baseline?: string;
}

export interface ReportKPI {
    percentages_found?: { value: number; context: string }[];
    timeframes_found?: { timeframe: string; text: string }[];
    segments_mentioned?: string[];
    chapter_count?: number;
    predictive_conclusion_count?: number;
    blockquote_count?: number;
    word_count?: number;
    quantitative_density_score?: number;
}

export interface ExecutiveSummary {
    summary_it: string;
    highlights?: string[];
    warnings?: string[];
}

export interface ActionItem {
    // Legacy fields (kept for back-compat with older saved runs)
    title?: string;
    description?: string;
    due_in?: string;
    // Current backend fields
    action?: string;
    owner?: string;
    timeframe_h?: number;
    rationale?: string;
    kpi_target?: string;
    priority?: 'low' | 'medium' | 'high' | string;
    targets_drivers?: string[];
    expected_impact?: string;
}

export interface ActionPlan {
    actions: ActionItem[];
    horizon_hours?: number;
}

export type DriverStrength = 'high' | 'medium' | 'low';

export interface ScenarioDriver {
    label: string;
    evidence_topic?: string;
    mentions: number;
    sentiment: number;
    strength: DriverStrength;
    rationale?: string;
    sample_quotes?: string[];
}

export interface ScenarioDriversSet {
    scenario_focus?: string;
    drivers: ScenarioDriver[];
    model?: string;
    confidence?: number;
    notes?: string;
}

export interface SimulationSummary {
    profiles_count?: number;
    total_actions?: number;
    actions_by_type?: Record<string, number>;
    sample_posts?: {
        content?: string;
        user_id?: string | number;
        post_id?: string | number;
    }[];
    sample_comments?: {
        content?: string;
        user_id?: string | number;
        post_id?: string | number;
    }[];
    profiles_preview?: {
        user_id?: string | number;
        username?: string;
        name?: string;
        age?: number;
        country?: string;
        profession?: string;
        bio?: string;
        interested_topics?: string[];
    }[];
    zep?: {
        status?: string;
        graph_id?: string;
        facts_registered?: number;
        reason?: string;
        graph_preview?: {
            graph_id?: string;
            nodes?: {
                id: string;
                label: string;
                type: string;
                weight?: number;
                sentiment?: number;
            }[];
            links?: {
                source: string;
                target: string;
                type: string;
            }[];
        };
    };
    zep_qa?: {
        status: 'ok' | 'skipped' | 'error';
        reason?: string;
        model?: string | null;
        questions: {
            question: string;
            answer: string;
            facts: string[];
            fact_count: number;
        }[];
    };
    prediction_text?: string;
    [k: string]: unknown;
}

export interface GraphNode {
    id: string;
    type: string;
    label: string;
    weight: number;
    sentiment: number;
}

export interface GraphLink {
    source: string;
    target: string;
    type: string;
    weight: number;
}

export interface KnowledgeGraph {
    nodes: GraphNode[];
    links: GraphLink[];
    stats?: {
        node_count: number;
        link_count: number;
        node_types: string[];
        edge_types: string[];
        inferred?: boolean;
    };
}

export interface BrandSeed {
    brand: string;
    market: string;
    language: string;
    total_mentions: number;
    overall_sentiment: number;
    segments: { name: string; weight: number; description?: string }[];
    topics: { name: string; mentions: number; sentiment_score: number }[];
    sentiment_breakdown?: {
        positive: number;
        neutral: number;
        negative: number;
        mixed?: number;
    };
    platforms?: {
        name: string;
        count: number;
        share: number;
        sentiment: number;
    }[];
    countries?: {
        name: string;
        count: number;
        share: number;
        sentiment: number;
    }[];
    knowledge_graph?: KnowledgeGraph;
}

export interface OntologyEntity {
    name: string;
    description?: string;
    role_in_simulation?: string;
    examples?: string[];
}

export interface OntologyEdge {
    name: string;
    description?: string;
    source_targets: { source: string; target: string }[];
}

export interface Ontology {
    status: 'ok' | 'skipped' | 'error';
    entity_types: OntologyEntity[];
    edge_types: OntologyEdge[];
    analysis_summary?: string;
    model?: string;
    reason?: string;
}

export interface PipelineResult {
    mode: PipelineMode;
    brand_seed: BrandSeed;
    report_markdown: string;
    kpi: ReportKPI;
    executive_summary: ExecutiveSummary;
    scenario_drivers?: ScenarioDriversSet | null;
    action_plan: ActionPlan;
    scenarios?: ScenarioSet | null;
    volume_forecast?: VolumeForecast | null;
    simulation?: SimulationSummary | null;
    ontology?: Ontology | null;
    warnings?: string[];
}

export interface Scenario {
    label: 'best' | 'base' | 'worst';
    title: string;
    narrative: string;
    probability: number;
    drivers: string[];
    early_signals: string[];
}

export interface ScenarioSet {
    horizon_weeks: number;
    scenarios: Scenario[];
    model?: string;
    confidence?: number;
}

export interface ForecastPoint {
    date: string;
    yhat: number;
    yhat_lower: number;
    yhat_upper: number;
}

export interface VolumeForecast {
    method:
        | 'holt_winters'
        | 'linear_trend'
        | 'naive_mean'
        | 'insufficient_data';
    history_weeks: number;
    horizon_weeks: number;
    historical: ForecastPoint[];
    forecast: ForecastPoint[];
    notes?: string;
}
