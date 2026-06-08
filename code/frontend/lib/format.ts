export function formatDateTime(iso: string, locale = 'it-IT'): string {
    try {
        const d = new Date(iso);
        return new Intl.DateTimeFormat(locale, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        }).format(d);
    } catch {
        return iso;
    }
}

export function timeAgo(iso: string, locale = 'it'): string {
    try {
        const diffMs = Date.now() - new Date(iso).getTime();
        const sec = Math.round(diffMs / 1000);
        if (sec < 60) return locale === 'it' ? `${sec}s fa` : `${sec}s ago`;
        const min = Math.round(sec / 60);
        if (min < 60) return locale === 'it' ? `${min}m fa` : `${min}m ago`;
        const hr = Math.round(min / 60);
        if (hr < 24) return locale === 'it' ? `${hr}h fa` : `${hr}h ago`;
        const d = Math.round(hr / 24);
        return locale === 'it' ? `${d}g fa` : `${d}d ago`;
    } catch {
        return iso;
    }
}

export function pct(n: number, digits = 0): string {
    return `${(n * 100).toFixed(digits)}%`;
}

export function nowTimeHHMMSS(): string {
    return new Date().toLocaleTimeString('it-IT', { hour12: false });
}
