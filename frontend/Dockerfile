# ── Meridian frontend — Vite build, served static ────────────────
FROM node:20-slim AS build

WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .

# VITE_API_BASE is injected at build time by Railway (set in dashboard).
# It bakes the backend URL into the static bundle.
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# ── Serve the built static files ─────────────────────────────────
FROM node:20-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist

ENV PORT=4173
EXPOSE 4173
# serve the SPA, routing all paths to index.html
CMD serve -s dist -l ${PORT}
