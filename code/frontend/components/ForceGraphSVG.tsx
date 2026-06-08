'use client';

import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import ChartTooltip, { useChartTooltip } from './ChartTooltip';

export interface FGNode {
    id: string;
    label?: string;
    color?: string;
    radius?: number;
    /** Border colour. Defaults to #111. */
    stroke?: string;
    /** Border width. Defaults to 1. */
    strokeWidth?: number;
    /** Optional text colour. Defaults to #111. */
    textColor?: string;
    /** Optional weight for label boldness. */
    bold?: boolean;
}

export interface FGLink {
    source: string;
    target: string;
    color?: string;
    width?: number;
    dashed?: boolean;
}

interface SimNode extends FGNode, d3.SimulationNodeDatum {}
interface SimLink
    extends
        Omit<FGLink, 'source' | 'target'>,
        d3.SimulationLinkDatum<SimNode> {}

interface ForceGraphSVGProps {
    nodes: FGNode[];
    links: FGLink[];
    width: number;
    height: number;
    background?: string;
    showLabels?: boolean;
    /** Charge strength (more negative = more repulsion). Default -260. */
    chargeStrength?: number;
    /** Link distance. Default 90. */
    linkDistance?: number;
}

/**
 * Generic D3 force-directed graph rendered into an SVG.
 * Supports drag + zoom, with declarative React-driven data.
 */
export default function ForceGraphSVG({
    nodes,
    links,
    width,
    height,
    background = '#f8f5ef',
    showLabels = true,
    chargeStrength = -260,
    linkDistance = 90,
}: ForceGraphSVGProps) {
    const svgRef = useRef<SVGSVGElement | null>(null);
    const wrapRef = useRef<HTMLDivElement | null>(null);
    const { tip, show, hide } = useChartTooltip();
    const [, force] = useState(0);

    useEffect(() => {
        const svgEl = svgRef.current;
        if (!svgEl) return;
        const svg = d3.select(svgEl);
        svg.selectAll('*').remove();

        // Clone data so the simulation can mutate it without re-renders.
        const simNodes: SimNode[] = nodes.map((n) => ({ ...n }));
        const idToNode = new Map(simNodes.map((n) => [n.id, n]));
        const simLinks: SimLink[] = links
            .filter((l) => idToNode.has(l.source) && idToNode.has(l.target))
            .map((l) => ({ ...l, source: l.source, target: l.target }));

        const root = svg.append('g');

        const zoom = d3
            .zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.2, 6])
            .on('zoom', (event) => {
                root.attr('transform', event.transform.toString());
            });
        svg.call(zoom);

        const linkSel = root
            .append('g')
            .attr('stroke-linecap', 'round')
            .selectAll<SVGLineElement, SimLink>('line')
            .data(simLinks)
            .join('line')
            .attr('stroke', (d) => d.color ?? 'rgba(31,31,31,0.32)')
            .attr('stroke-width', (d) => d.width ?? 1.2)
            .attr('stroke-dasharray', (d) => (d.dashed ? '4 4' : null));

        const nodeG = root
            .append('g')
            .selectAll<SVGGElement, SimNode>('g')
            .data(simNodes)
            .join('g')
            .style('cursor', 'grab');

        nodeG
            .append('circle')
            .attr('r', (d) => d.radius ?? 8)
            .attr('fill', (d) => d.color ?? '#888')
            .attr('stroke', (d) => d.stroke ?? '#111')
            .attr('stroke-width', (d) => d.strokeWidth ?? 1);

        if (showLabels) {
            nodeG
                .append('text')
                .text((d) => d.label ?? d.id)
                .attr('text-anchor', 'middle')
                .attr('dy', (d) => (d.radius ?? 8) + 11)
                .attr('font-size', (d) => (d.bold ? 11 : 9))
                .attr('font-family', 'var(--mono, monospace)')
                .attr('font-weight', (d) => (d.bold ? 700 : 500))
                .attr('fill', (d) => d.textColor ?? '#111')
                .style('pointer-events', 'none');
        }

        nodeG.append('title').text((d) => d.label ?? d.id);

        // Build neighbour index for hover highlighting.
        const neighbours = new Map<string, Set<string>>();
        simNodes.forEach((n) => neighbours.set(n.id, new Set([n.id])));
        simLinks.forEach((l) => {
            const s =
                typeof l.source === 'string'
                    ? l.source
                    : (l.source as SimNode).id;
            const t =
                typeof l.target === 'string'
                    ? l.target
                    : (l.target as SimNode).id;
            neighbours.get(s)?.add(t);
            neighbours.get(t)?.add(s);
        });

        nodeG
            .on('mouseenter', (event: MouseEvent, d) => {
                const focus = neighbours.get(d.id) ?? new Set([d.id]);
                nodeG
                    .select('circle')
                    .attr('opacity', (nn) => (focus.has(nn.id) ? 1 : 0.18));
                linkSel.attr('opacity', (ll) => {
                    const s =
                        typeof ll.source === 'string'
                            ? ll.source
                            : (ll.source as SimNode).id;
                    const t =
                        typeof ll.target === 'string'
                            ? ll.target
                            : (ll.target as SimNode).id;
                    return s === d.id || t === d.id ? 1 : 0.08;
                });
                show(
                    event as unknown as React.MouseEvent,
                    `${d.label ?? d.id}`,
                );
            })
            .on('mousemove', (event: MouseEvent, d) => {
                show(
                    event as unknown as React.MouseEvent,
                    `${d.label ?? d.id}`,
                );
            })
            .on('mouseleave', () => {
                nodeG.select('circle').attr('opacity', 1);
                linkSel.attr('opacity', 1);
                hide();
            });

        const simulation = d3
            .forceSimulation<SimNode>(simNodes)
            .force(
                'link',
                d3
                    .forceLink<SimNode, SimLink>(simLinks)
                    .id((d) => d.id)
                    .distance(linkDistance)
                    .strength(0.7),
            )
            .force('charge', d3.forceManyBody().strength(chargeStrength))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force(
                'collide',
                d3.forceCollide<SimNode>().radius((d) => (d.radius ?? 8) + 4),
            )
            .on('tick', () => {
                linkSel
                    .attr('x1', (d) => (d.source as SimNode).x ?? 0)
                    .attr('y1', (d) => (d.source as SimNode).y ?? 0)
                    .attr('x2', (d) => (d.target as SimNode).x ?? 0)
                    .attr('y2', (d) => (d.target as SimNode).y ?? 0);
                nodeG.attr(
                    'transform',
                    (d) => `translate(${d.x ?? 0},${d.y ?? 0})`,
                );
            });

        // Auto-fit after layout settles.
        simulation.on('end', () => {
            const padding = 30;
            const xs = simNodes.map((n) => n.x ?? 0);
            const ys = simNodes.map((n) => n.y ?? 0);
            if (xs.length === 0) return;
            const minX = Math.min(...xs);
            const maxX = Math.max(...xs);
            const minY = Math.min(...ys);
            const maxY = Math.max(...ys);
            const dx = maxX - minX || 1;
            const dy = maxY - minY || 1;
            const scale = Math.min(
                6,
                Math.max(
                    0.3,
                    0.95 /
                        Math.max(
                            dx / (width - 2 * padding),
                            dy / (height - 2 * padding),
                        ),
                ),
            );
            const tx = width / 2 - scale * (minX + dx / 2);
            const ty = height / 2 - scale * (minY + dy / 2);
            svg.transition()
                .duration(450)
                .call(
                    zoom.transform,
                    d3.zoomIdentity.translate(tx, ty).scale(scale),
                );
        });

        const drag = d3
            .drag<SVGGElement, SimNode>()
            .on('start', (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
        nodeG.call(drag);

        return () => {
            simulation.stop();
        };
    }, [
        nodes,
        links,
        width,
        height,
        showLabels,
        chargeStrength,
        linkDistance,
        show,
        hide,
    ]);

    // The tooltip lives outside the SVG (HTML overlay positioned relative to
    // wrapRef) so SVG event coordinates need to be re-mapped. Use a small
    // wrapper instead of returning the bare svg.
    return (
        <div ref={wrapRef} style={{ position: 'relative', display: 'block' }}>
            <svg
                ref={svgRef}
                width={width}
                height={height}
                viewBox={`0 0 ${width} ${height}`}
                preserveAspectRatio="xMidYMid meet"
                style={{ background, display: 'block', maxWidth: '100%' }}
                onMouseLeave={() => {
                    hide();
                    force((v) => v + 1);
                }}
            />
            <ChartTooltip tip={tip} />
        </div>
    );
}
