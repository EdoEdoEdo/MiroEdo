import type { NextConfig } from 'next';

const isMock = process.env.NEXT_PUBLIC_DATA_SOURCE === 'mock';

const nextConfig: NextConfig = {
    reactStrictMode: true,
    // When DATA_SOURCE=mock the frontend is fully static and can be exported
    // to any plain web host (GitHub Pages, Aruba, S3, etc.).
    ...(isMock
        ? {
              output: 'export' as const,
              images: { unoptimized: true },
              trailingSlash: true,
              ...(process.env.NEXT_PUBLIC_BASE_PATH
                  ? {
                        basePath: process.env.NEXT_PUBLIC_BASE_PATH,
                        assetPrefix: process.env.NEXT_PUBLIC_BASE_PATH,
                    }
                  : {}),
          }
        : {}),
    env: {
        NEXT_PUBLIC_API_BASE:
            process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000',
        NEXT_PUBLIC_DATA_SOURCE: process.env.NEXT_PUBLIC_DATA_SOURCE ?? 'api',
        NEXT_PUBLIC_BASE_PATH: process.env.NEXT_PUBLIC_BASE_PATH ?? '',
        NEXT_PUBLIC_SCENARIOS_BASE:
            process.env.NEXT_PUBLIC_SCENARIOS_BASE ??
            `${process.env.NEXT_PUBLIC_BASE_PATH ?? ''}/scenarios`,
        NEXT_PUBLIC_MOCK_SCENARIOS:
            process.env.NEXT_PUBLIC_MOCK_SCENARIOS ?? 'esg-retailer,nordalatte',
    },
};

export default nextConfig;
