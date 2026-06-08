'use client';

import { useEffect, useMemo, useState } from 'react';
import { useT } from '../lib/i18n';
import type { KnowledgeGraph as KG, GraphNode } from '../lib/types';
import ForceGraphSVG, { type FGNode, type FGLink } from './ForceGraphSVG';
import { useElementSize } from '../lib/d3Hooks';

const TYPE_COLORS: Record<string, string> = {
    Brand: '#b8332b',
    Topic: '#f2d27c',
    Country: '#c7d7f0',
    Platform: '#d8c7ef',
    Author: '#b9dfc2',
    MediaOutlet: '#f0b1aa',
    Hashtag: '#ddd6c9',
};

function colorForType(type: string): string {
    return TYPE_COLORS[type] ?? '#cccccc';
}

function radiusForNode(n: GraphNode): number {
    const w = Math.max(1, n.weight ?? 1);
    return 6 + Math.min(22, Math.log2(w + 1) * 3);
}

export default function KnowledgeGraph({ graph }: { graph: KG }) {
    const { t } = useT();
    const nodes = useMemo(() => graph?.nodes ?? [], [graph]);
    const links = useMemo(() => graph?.links ?? [], [graph]);
    const allTypes = useMemo(
        () =>
            graph?.stats?.node_types ??
            Array.from(new Set(nodes.map((n) => n.type))),
        [graph, nodes],
    );
    const [active, setActive] = useState<Set<string>>(() => new Set(allTypes));
    const [showLabels, setShowLabels] = useState(true);

    // Keep `active` in sync when graph data arrives or types change.
    useEffect(() => {
        setActive((prev) => {
            const next = new Set(prev);
            let mutated = false;
            for (const t of allTypes) {
                if (!next.has(t)) {
                    next.add(t);
                    mutated = true;
                }
            }
            return mutated ? next : prev;
        });
    }, [allTypes]);

    const { fgNodes, fgLinks } = useMemo(() => {
        const keep = new Set<string>();
        const fgNodes: FGNode[] = [];
        for (const n of nodes) {
            if (!active.has(n.type)) continue;
            keep.add(n.id);
            fgNodes.push({
                id: n.id,
                label: n.label,
                color: colorForType(n.type),
                radius: radiusForNode(n),
                stroke: n.type === 'Brand' ? '#111' : '#444',
                strokeWidth: n.type === 'Brand' ? 2 : 1,
                bold: n.type === 'Brand',
            });
        }
        const fgLinks: FGLink[] = [];
        for (const l of links) {
            if (!keep.has(l.source) || !keep.has(l.target)) continue;
            fgLinks.push({
                source: l.source,
                target: l.target,
                color: 'rgba(31,31,31,0.30)',
                width: 0.8 + Math.min(2.5, Math.log2((l.weight ?? 1) + 1)),
            });
        }
        return { fgNodes, fgLinks };
    }, [nodes, links, active]);

    const { ref, size } = useElementSize<HTMLDivElement>({
        width: 800,
        height: 520,
    });
    const height = 520;

    const toggle = (t: string) => {
        setActive((prev) => {
            const next = new Set(prev);
            if (next.has(t)) next.delete(t);
            else next.add(t);
            return next;
        });
    };

    return (
        <div style={{ marginTop: 16 }}>
            <div
                style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: 12,
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    color: '#555',
                    marginBottom: 8,
                }}
            >
                {allTypes.map((t) => (
                    <label
                        key={t}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            cursor: 'pointer',
                        }}
                    >
                        <input
                            type="checkbox"
                            checked={active.has(t)}
                            onChange={() => toggle(t)}
                        />
                        <span
                            style={{
                                width: 10,
                                height: 10,
                                background: colorForType(t),
                                display: 'inline-block',
                                border: '1px solid #444',
                            }}
                        />
                        {t}
                    </label>
                ))}
                <label
                    style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        cursor: 'pointer',
                        marginLeft: 'auto',
                    }}
                >
                    <input
                        type="checkbox"
                        checked={showLabels}
                        onChange={(e) => setShowLabels(e.target.checked)}
                    />
                    {t('kg.show_labels')}
                </label>
            </div>
            <div
                ref={ref}
                style={{
                    border: '1px solid var(--ink, #111)',
                    background: '#f8f5ef',
                    height,
                    overflow: 'hidden',
                }}
            >
                {fgNodes.length > 0 ? (
                    <ForceGraphSVG
                        nodes={fgNodes}
                        links={fgLinks}
                        width={size.width}
                        height={height}
                        showLabels={showLabels}
                        chargeStrength={-320}
                        linkDistance={90}
                    />
                ) : (
                    <div
                        style={{
                            padding: 20,
                            color: '#888',
                            fontStyle: 'italic',
                        }}
                    >
                        {t('kg.no_nodes')}
                    </div>
                )}
            </div>
            {graph.stats && (
                <div
                    style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        color: '#888',
                        marginTop: 6,
                    }}
                >
                    {graph.stats.node_count} {t('kg.stats_nodes')} ·{' '}
                    {graph.stats.link_count} {t('kg.stats_edges')} ·{' '}
                    {t('kg.stats_suffix')}
                </div>
            )}
        </div>
    );
}
