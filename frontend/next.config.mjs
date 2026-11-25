/** @type {import('next').NextConfig} */
const apiTarget =
  process.env.API_PROXY_TARGET ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

// Loud warning: rewrites() bakes this target in at build time. On Vercel the
// backend is NOT on localhost, so a default here makes every /api/* call 404
// (the request falls through to the Next router). Set API_PROXY_TARGET.
if (
  process.env.NODE_ENV === "production" &&
  /(^https?:\/\/)?(localhost|127\.0\.0\.1)/.test(apiTarget)
) {
  console.warn(
    `[next.config] API 代理目标仍是本机地址：${apiTarget}。` +
      "线上请在 Vercel 设置 API_PROXY_TARGET=https://<你的后端域名>（如 https://api.topsaypan.com）后重新部署，" +
      "否则 /api/* 会 404。",
  );
}

const nextConfig = {
  reactStrictMode: true,
  // Standalone bundle is only needed for the Docker image. Opt-in via NEXT_OUTPUT
  // so bare-metal `next start` (systemd) keeps working.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" } : {}),
  // Allow building even when the API base is only known at deploy time.
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
    // Frontend gate. Keep false to ship the UI first, then flip to true to
    // require login + approved onboarding (pairs with backend AUTH_ENFORCED).
    NEXT_PUBLIC_AUTH_ENFORCED: process.env.NEXT_PUBLIC_AUTH_ENFORCED || "false",
    NEXT_PUBLIC_SESSION_COOKIE_NAME:
      process.env.NEXT_PUBLIC_SESSION_COOKIE_NAME || "wi_session",
  },
  // Proxy /api/* to the backend through the frontend origin. This keeps the
  // HttpOnly session cookie same-origin for the browser while server
  // components still call the backend directly and forward the cookie.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
  },
};

export default nextConfig;
