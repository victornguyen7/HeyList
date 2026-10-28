import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    agentFeedback: true,
    agentUpgrade: "security",
    // A free Render backend sleeps after 15 idle minutes and can take over a minute to wake; at the default
    // 30 s the first request after a break failed.
    proxyTimeout: 120_000,
  },
  // Supabase Auth in the browser (app/auth.ts). The publishable key is meant to be public; the secret key stays in the backend.
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.SUPABASE_PUBLISHABLE_KEY,
  },
  cacheComponents: true,
  partialPrefetching: true,
  // The FastAPI backend (backend/main.py); proxied so the browser stays same-origin.
  rewrites: async () => [
    { source: "/api/:path*", destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*` },
  ],
  // List pages used to live at /?list=<id>; old shared links and PayPal orders created before the move still
  // return there. The query (PayPal's token and PayerID) is passed through, so the capture still happens.
  redirects: async () => [
    { source: "/", has: [{ type: "query", key: "list", value: "(?<list>[0-9a-fA-F-]+)" }], destination: "/lists/:list", permanent: true },
  ],
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
