'use client';

import { useCallback, useState, type MouseEvent, type ReactNode } from 'react';

export interface TooltipState {
    x: number;
    y: number;
    content: ReactNode;
}

export function useChartTooltip() {
    const [tip, setTip] = useState<TooltipState | null>(null);

    const show = useCallback((e: MouseEvent, content: ReactNode) => {
        // Coordinates relative to the chart container (offsetParent),
        // so the tooltip sits inside the bordered card.
        const host = (e.currentTarget as SVGElement).ownerSVGElement
            ?.parentElement;
        if (!host) {
            setTip({ x: e.clientX, y: e.clientY, content });
            return;
        }
        const r = host.getBoundingClientRect();
        setTip({
            x: e.clientX - r.left,
            y: e.clientY - r.top,
            content,
        });
    }, []);

    const hide = useCallback(() => setTip(null), []);

    return { tip, show, hide };
}

export default function ChartTooltip({ tip }: { tip: TooltipState | null }) {
    if (!tip) return null;
    return (
        <div
            style={{
                position: 'absolute',
                left: tip.x + 12,
                top: tip.y + 12,
                background: 'rgba(17,17,17,0.92)',
                color: '#fff',
                padding: '6px 9px',
                fontSize: 11,
                fontFamily: 'var(--mono, monospace)',
                lineHeight: 1.35,
                pointerEvents: 'none',
                zIndex: 50,
                borderRadius: 2,
                maxWidth: 280,
                whiteSpace: 'pre-line',
            }}
        >
            {tip.content}
        </div>
    );
}
