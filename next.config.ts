import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    agentFeedback: true,
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
