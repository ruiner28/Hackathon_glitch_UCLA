import type { NextConfig } from "next";

/** Where FastAPI runs; used by rewrites (server-side proxy, not exposed to the browser). */
const backend =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Dev rewrites proxy to FastAPI; default proxy timeout is 30s and breaks long LLM steps
  // (extract / plan / compile-scenes). See next/dist/server/lib/router-utils/proxy-request.js
  experimental: {
    proxyTimeout: 600_000, // 10 minutes (ms)
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
