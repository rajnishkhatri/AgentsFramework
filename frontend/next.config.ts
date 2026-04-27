import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  productionBrowserSourceMaps: false, // FD3.SEC3
  images: {
    remotePatterns: [], // FD3.SEC4 -- explicit allowlist; widen as needed
  },
  // The ESLint plugin (jsx-a11y) is run via `npm run lint`; we keep the build
  // step from blocking on lint warnings (TS strict + tests are the gate).
  eslint: { ignoreDuringBuilds: true },
};

export default config;
