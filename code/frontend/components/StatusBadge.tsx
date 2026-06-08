'use client';

import { useT } from '@/lib/i18n';
import type { RunStatus } from '@/lib/types';

export default function StatusBadge({ status }: { status: RunStatus }) {
    const { t } = useT();
    return (
        <span className={`me-status ${status}`}>{t(`status.${status}`)}</span>
    );
}
