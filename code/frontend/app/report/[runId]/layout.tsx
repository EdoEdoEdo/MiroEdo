import { staticParamsForRunId } from '@/lib/staticParams';

export function generateStaticParams() {
    return staticParamsForRunId();
}

export default function Layout({ children }: { children: React.ReactNode }) {
    return children;
}
