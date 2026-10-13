import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    agentFeedback: true,
    // The rewrite proxy gives up after 30s by default. The backend can take up to 95s
    // (token, order call, one 429 retry), and a capture cut off here may still complete.
    proxyTimeout: 100_000,
  },
  cacheComponents: true,
  partialPrefetching: true,
  // The sample checkout page is replaced by real lists; old links land on the home page.
  async redirects() {
    return [{ source: "/checkout", destination: "/", permanent: false }];
  },
  // All server-side logic lives in the FastAPI service in backend/.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
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
