# syntax=docker/dockerfile:1

# --- deps: install with a clean, reproducible lockfile install ---------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- build: `next build` (output: "standalone") ------------------------------
# NOTE: API_PROXY_TARGET is baked into next.config rewrites at BUILD time, so it
# must be passed here as a build arg and matches the runtime value below.
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_PROXY_TARGET=http://localhost:8000
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
ARG NEXT_PUBLIC_AUTH_ENFORCED=false
ENV NEXT_PUBLIC_AUTH_ENFORCED=${NEXT_PUBLIC_AUTH_ENFORCED}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Guarantee a public/ dir exists so the runner COPY below never fails.
RUN mkdir -p public && npm run build

# --- run: minimal image from the standalone bundle ---------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
# Runtime env for server components (lib/api.ts) + the proxied rewrite target.
ARG API_PROXY_TARGET=http://localhost:8000
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
ENV NEXT_PUBLIC_API_BASE=${API_PROXY_TARGET}

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
