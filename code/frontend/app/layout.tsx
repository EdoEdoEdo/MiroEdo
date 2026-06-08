import type { Metadata } from 'next';
import { I18nProvider } from '@/lib/i18n';
import Topbar from '@/components/Topbar';
import './globals.css';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

export const metadata: Metadata = {
    title: 'MiroEdo — Brand Intelligence Engine',
    description:
        'Brand intelligence engine: universal ingestion (CSV/XLSX/PDF/MD), editorial AI report, OASIS social simulation and a ReAct chat over a persistent knowledge graph.',
    openGraph: {
        title: 'MiroEdo — Brand Intelligence Engine',
        description:
            'Universal ingestion, editorial AI report, OASIS social simulation, ReAct chat over a persistent knowledge graph.',
        type: 'website',
    },
    authors: [
        { name: 'Edoardo Di Sabatino', url: 'https://www.edoedoedo.it/' },
    ],
    creator: 'Edoardo Di Sabatino',
    icons: {
        icon: `${basePath}/favicon.png`,
    },
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <head>
                <link
                    href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;500&family=DM+Serif+Display:ital@0;1&family=Barlow+Condensed:wght@700;900&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body>
                <I18nProvider>
                    <div className="me-shell">
                        <Topbar />
                        {children}
                    </div>
                </I18nProvider>
            </body>
        </html>
    );
}
