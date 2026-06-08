#!/usr/bin/env node
/**
 * Generate a realistic actions.json for a mock MiroEdo scenario.
 * Reads totals from run.json (simulation.actions_by_type, profiles_count,
 * profiles_preview, sample_posts, sample_comments) and produces ~4k rows
 * shaped like the backend ActionRow stream, so LiveSimulation can replay
 * them through fetchActions() exactly as in a real OASIS run.
 *
 *   node scripts/gen-actions.mjs <scenarioId>
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const scenarioId = process.argv[2] || 'esg-retailer';
const scenarioDir = resolve(here, '..', 'public', 'scenarios', scenarioId);

const run = JSON.parse(readFileSync(join(scenarioDir, 'run.json'), 'utf8'));
const sim = run.result?.simulation;
if (!sim) throw new Error(`No simulation block in ${scenarioId}/run.json`);

const profilesCount = sim.profiles_count ?? 120;
const actionsByType = sim.actions_by_type ?? {};
const samplePosts = sim.sample_posts ?? [];
const sampleComments = sim.sample_comments ?? [];
const topics = (run.result?.brand_seed?.topics ?? []).map((t) => t.name);
const rounds = 10;

// Deterministic RNG so the demo is reproducible.
let seed = 4127;
const rand = () => {
    seed = (seed * 1664525 + 1013904223) % 0xffffffff;
    return seed / 0xffffffff;
};

const pick = (arr) => arr[Math.floor(rand() * arr.length)];

const ACTION_INFO = {
    refresh: () => '',
    do_nothing: () => '',
    sign_up: () => `joined as agent_${Math.floor(rand() * profilesCount)}`,
    like_post: () =>
        `post_${Math.floor(rand() * (samplePosts.length * 40 || 200))}`,
    dislike_post: () =>
        `post_${Math.floor(rand() * (samplePosts.length * 40 || 200))}`,
    create_post: () => {
        const seed = pick(samplePosts);
        const topic = pick(topics);
        return seed?.content
            ? seed.content.slice(0, 90) + (seed.content.length > 90 ? '…' : '')
            : `topic=${topic}`;
    },
    create_comment: () => {
        const seed = pick(sampleComments);
        const topic = pick(topics);
        return seed?.content
            ? seed.content.slice(0, 90) + (seed.content.length > 90 ? '…' : '')
            : `re: ${topic}`;
    },
};

// Build the actual stream.
const startTs = new Date('2026-05-20T09:14:30Z').getTime();
let rowid = 1;
const rows = [];

// 1) initial sign_up wave (one per agent)
const signupCount = Math.min(profilesCount, actionsByType.sign_up ?? 35);
for (let i = 0; i < signupCount; i++) {
    rows.push({
        event: 'action',
        round: 0,
        rowid: rowid++,
        agent_id: i,
        action: 'sign_up',
        info: ACTION_INFO.sign_up(),
        created_at: new Date(startTs + rowid * 35).toISOString(),
    });
}

// 2) distribute the rest of the actions across 10 rounds.
const remaining = { ...actionsByType };
delete remaining.sign_up;

const perRound = {};
for (const [kind, total] of Object.entries(remaining)) {
    perRound[kind] = Math.floor(total / rounds);
}

for (let r = 1; r <= rounds; r++) {
    // Interleave the kinds so the stream looks chaotic (not blocks).
    const queue = [];
    for (const [kind, count] of Object.entries(perRound)) {
        for (let i = 0; i < count; i++) queue.push(kind);
    }
    // Fisher-Yates shuffle with our seeded rand.
    for (let i = queue.length - 1; i > 0; i--) {
        const j = Math.floor(rand() * (i + 1));
        [queue[i], queue[j]] = [queue[j], queue[i]];
    }
    for (const kind of queue) {
        rows.push({
            event: 'action',
            round: r,
            rowid: rowid++,
            agent_id: Math.floor(rand() * profilesCount),
            action: kind,
            info: ACTION_INFO[kind]?.() ?? '',
            created_at: new Date(startTs + rowid * 35).toISOString(),
        });
    }
    // Round delimiter event
    rows.push({
        event: 'round_end',
        round: r,
        rowid: rowid++,
        actions_count: queue.length,
        created_at: new Date(startTs + rowid * 35).toISOString(),
    });
}

// 3) final done event
rows.push({
    event: 'done',
    round: rounds,
    rowid: rowid++,
    actions_count: rows.length,
    profiles: profilesCount,
    rounds,
    seed_posts: samplePosts.length,
    created_at: new Date(startTs + rowid * 35).toISOString(),
});

writeFileSync(join(scenarioDir, 'actions.json'), JSON.stringify(rows));
console.log(`Wrote ${rows.length} rows to ${scenarioId}/actions.json`);
