'use client';

import { useEffect, useRef, useState } from 'react';

/** Tracks container size with a ResizeObserver. SSR-safe. */
export function useElementSize<T extends HTMLElement>(
    defaultSize: { width: number; height: number } = {
        width: 600,
        height: 320,
    },
) {
    const ref = useRef<T | null>(null);
    const [size, setSize] = useState(defaultSize);
    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        const update = () => {
            const r = el.getBoundingClientRect();
            setSize({
                width: Math.max(120, Math.floor(r.width)),
                height: Math.max(120, Math.floor(r.height)),
            });
        };
        update();
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => ro.disconnect();
    }, []);
    return { ref, size };
}

export function sentColor(s: number): string {
    if (s <= -0.2) return '#b8332b';
    if (s < -0.05) return '#d97f78';
    if (s <= 0.05) return '#a8a8a8';
    if (s <= 0.2) return '#7fb98b';
    return '#137b3a';
}
