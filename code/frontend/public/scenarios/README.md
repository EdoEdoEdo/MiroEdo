# Static demo scenarios

Each subdirectory under `public/scenarios/` is a self-contained, pre-computed
demo run that the frontend can load when built with `NEXT_PUBLIC_DATA_SOURCE=mock`.
Used for the public live demo (GitHub Pages / Aruba) where no backend is reachable.

## Layout

```
public/scenarios/
├── README.md                      ← this file
├── <scenario-id>/
│   ├── run.json                   ← RunRecord (required)
│   ├── actions.json               ← ActionRow[] for LiveSimulation (optional)
│   └── chat.json                  ← MockChatEntry[] for ReportChat (optional)
└── ...
```

`<scenario-id>` must be URL-safe (lowercase, dashes). It is used both as the
folder name and as the `run_id` exposed to the UI.

## File contracts

### `run.json` — `RunRecord` (see [frontend/lib/types.ts](../../lib/types.ts))

Must include a fully populated `result: PipelineResult`. Mandatory keys:

- `result.brand_seed` — drives every chart on `/report/[runId]`
- `result.report_markdown` — narrative shown in `<ReportMarkdown>`
- `result.executive_summary`, `result.action_plan`, `result.kpi`
- `result.simulation` — drives `<LiveSimulation>`, `<ForceGraphSVG>` (via
  `simulation.zep.graph_preview`)
- `result.volume_forecast` — drives `<TimelineForecastChart>` with IC bands
- `result.scenarios`, `result.scenario_drivers` — drive `<DriverCards>` / `<ScenarioCards>`
- `result.ontology` — drives `<OntologyPanel>`

### `actions.json` — `ActionRow[]` (optional, for the live console)

Flat JSONL-equivalent array. The mock `fetchActions` slices it by cursor so
the existing tailing UI keeps working unchanged.

### `chat.json` — `MockChatEntry[]` (optional, for `<ReportChat>`)

```ts
type MockChatEntry = {
    match: string; // case-insensitive substring; '' = fallback
    answer: string;
    citations?: string[];
    confidence?: 'low' | 'medium' | 'high';
    sections?: { sid: string; title: string; level: number }[];
};
```

The first entry whose `match` substring appears in the user question wins. An
entry with `match: ''` is used as a fallback when nothing matches.

## Wiring a new scenario into the demo

1. Add the scenario id to the comma-separated env var
   `NEXT_PUBLIC_MOCK_SCENARIOS` (defaults to `esg-retailer`).
2. Build with `NEXT_PUBLIC_DATA_SOURCE=mock npm run build`.
3. Scenario shows up in `<ScenarioCards>` and is reachable at
   `/report/<scenario-id>`.

## Producing a scenario from a real run

When the backend is running locally:

```bash
# 1. Trigger a run end-to-end via the UI or `curl -X POST /reports ...`.
# 2. Snapshot the persisted run JSON into a scenario folder:
RUN_ID=<your-run-id>
SCENARIO_ID=<demo-scenario-id>
mkdir -p code/frontend/public/scenarios/$SCENARIO_ID
cp data/runs/$RUN_ID.json code/frontend/public/scenarios/$SCENARIO_ID/run.json
# 3. Optionally copy actions log (if simulation ran):
cp data/runs/$RUN_ID/actions.jsonl - \
  | jq -s '.' > code/frontend/public/scenarios/$SCENARIO_ID/actions.json
# 4. Hand-author chat.json with 3–10 canned Q&A for the demo.
# 5. Commit. The scenario is now permanently available offline.
```

This is how a single paid run becomes a forever-free demo asset.
