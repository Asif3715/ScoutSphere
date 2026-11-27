# Multi-stage image. `dev` is what docker-compose uses locally (next dev). `prod` builds
# the app (type-checked, optimized) and serves it with `next start`.
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# ---- local development -------------------------------------------------------------------
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]

# ---- production build --------------------------------------------------------------------
FROM deps AS build
# Baked into the client bundle at build time, so it must be passed as a build argument.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN pnpm build && pnpm prune --prod

FROM node:22-alpine AS prod
RUN corepack enable && addgroup -S app && adduser -S app -G app
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
COPY --from=build --chown=app:app /app/package.json /app/next.config.ts ./
COPY --from=build --chown=app:app /app/node_modules ./node_modules
COPY --from=build --chown=app:app /app/.next ./.next
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "--hostname", "0.0.0.0"]
