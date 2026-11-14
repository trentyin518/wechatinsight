/** @type {import('next').NextConfig} */
const apiTarget =
  process.env.API_PROXY_TARGET ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
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
