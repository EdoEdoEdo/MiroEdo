// Build-time only: enumerate scenario ids for static export.
// In API mode this file is unused (no static export happens).
const raw = process.env.NEXT_PUBLIC_MOCK_SCENARIOS ?? 'esg-retailer,nordalatte';

export function getMockScenarioIds(): string[] {
    return raw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
}

export function staticParamsForRunId() {
    return getMockScenarioIds().map((runId) => ({ runId }));
}
