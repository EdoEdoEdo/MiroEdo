'use client';

import { useMemo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders the report markdown. The OASIS chapter ("## 05 Simulazione OASIS")
 * is detected and wrapped in a highlighted red-bordered section.
 *
 * Headings get stable ids (s1, s1.1, s2 …) so the chat citations can deep-link
 * into the matching section via `/report/{id}#s1`.
 */
export default function ReportMarkdown({ md }: { md: string }) {
    const { before, oasis, after } = useMemo(() => splitOnOasis(md), [md]);
    // Counters must reset on every render to avoid drift under StrictMode /
    // re-renders, so build fresh components each call.
    const components = buildHeadingComponents();

    return (
        <div className="me-report">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {before}
            </ReactMarkdown>
            {oasis && (
                <div className="me-oasis-chapter">
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={components}
                    >
                        {oasis}
                    </ReactMarkdown>
                </div>
            )}
            {after && (
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={components}
                >
                    {after}
                </ReactMarkdown>
            )}
        </div>
    );
}

function buildHeadingComponents(): Components {
    // Counters reset per page render (one component instance per render call).
    let h2 = 0;
    let h3 = 0;
    return {
        h2: ({ children, ...props }) => {
            h2 += 1;
            h3 = 0;
            const sid = `s${h2}`;
            return (
                <h2 id={sid} {...props}>
                    {children}
                </h2>
            );
        },
        h3: ({ children, ...props }) => {
            h3 += 1;
            const sid = h2 > 0 ? `s${h2}.${h3}` : `h3-${h3}`;
            return (
                <h3 id={sid} {...props}>
                    {children}
                </h3>
            );
        },
    };
}

function splitOnOasis(md: string): {
    before: string;
    oasis: string | null;
    after: string;
} {
    const re = /^##\s+0?5\s+Simulazione\s+OASIS\b/im;
    const match = md.match(re);
    if (!match || match.index === undefined) {
        return { before: md, oasis: null, after: '' };
    }
    const start = match.index;
    // find next H2 after the OASIS heading
    const tail = md.slice(start + match[0].length);
    const nextH2 = tail.match(/^##\s+/m);
    const end =
        nextH2 && nextH2.index !== undefined
            ? start + match[0].length + nextH2.index
            : md.length;
    return {
        before: md.slice(0, start),
        oasis: md.slice(start, end),
        after: md.slice(end),
    };
}
