# Deploying Meridian to Railway

This deploys three services — **backend** (FastAPI + C++), **Redis**, and
**frontend** (React) — so the terminal runs 24/7 without your machine.

Expected cost: **~$10–15/month.** Set a spending limit (Step 7) to cap risk.

---

## Before you start

1. A [Railway](https://railway.app) account (sign in with GitHub).
2. Your code in a **GitHub repository**. Railway deploys from GitHub.
   - If it's not on GitHub yet: create a repo, then from your project root:
     ```bash
     git init
     git add .
     git commit -m "Meridian terminal"
     git branch -M main
     git remote add origin https://github.com/YOUR_USERNAME/meridian.git
     git push -u origin main
     ```
   - **Confirm `.env` is gitignored** — it should NOT be in the repo. Check:
     ```bash
     git ls-files | grep .env
     ```
     If it returns `.env` (not `.env.example`), remove it:
     ```bash
     git rm --cached .env && git commit -m "remove .env"
     ```

---

## Step 1 — Create the project + Redis

1. Railway dashboard -> **New Project** -> **Deploy from GitHub repo** -> pick your repo.
2. Once it imports, click **+ New** -> **Database** -> **Add Redis**.
   Railway provisions Redis and exposes a `REDIS_URL` variable automatically.

## Step 2 — Configure the backend service

1. Railway may auto-create a service from your repo. Click it -> **Settings**.
2. Set **Root Directory** to `backend`.
   Railway will detect the `Dockerfile` there and build it (this compiles the
   C++ extensions — first build takes ~3–4 min).
3. Under **Settings -> Networking**, click **Generate Domain**. Copy the URL —
   e.g. `https://meridian-backend-production.up.railway.app`. This is your
   **backend URL**.

## Step 3 — Backend environment variables

In the backend service -> **Variables**, add:

| Variable | Value |
|----------|-------|
| `POLYGON_API_KEY` | your Polygon key |
| `FRED_API_KEY` | your FRED key |
| `NEWS_API_KEY` | your NewsAPI key (optional) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` — references the Redis service |
| `CORS_ORIGINS` | *(fill in after Step 5 — your frontend URL)* |
| `ENV` | `production` |

> The `${{Redis.REDIS_URL}}` syntax is Railway's service reference — it wires
> the backend to your Redis automatically. Type it exactly.

## Step 4 — Create the frontend service

1. **+ New** -> **GitHub Repo** -> same repo again.
2. Click the new service -> **Settings** -> set **Root Directory** to `frontend`.
   It'll detect the frontend `Dockerfile`.
3. **Settings -> Networking** -> **Generate Domain**. Copy this — it's your
   **frontend URL** (the one you'll actually visit).

## Step 5 — Frontend environment variable

In the frontend service -> **Variables**, add:

| Variable | Value |
|----------|-------|
| `VITE_API_BASE` | your **backend URL** from Step 2 (e.g. `https://meridian-backend-production.up.railway.app`) |

Then **redeploy** the frontend (Deployments -> ... -> Redeploy) so the build picks
up the variable — it's baked into the static bundle at build time.

## Step 6 — Wire CORS

Go back to the **backend** service -> **Variables** -> set `CORS_ORIGINS` to your
**frontend URL** from Step 4 (no trailing slash). Backend redeploys automatically.

## Step 7 — Set a spending limit (do this!)

Project -> **Settings** -> **Usage** -> set a hard limit (e.g. **$20/month**).
Railway stops services rather than billing past it. This caps your risk.

---

## Verify

1. Visit your **frontend URL**. The terminal should load.
2. Check the backend is alive: visit `<backend-url>/health` — should return
   `{"status":"ok","redis":true,...}`.
3. If panels are empty, open the browser console (F12). A CORS error means
   `CORS_ORIGINS` doesn't exactly match your frontend URL.

---

## How updates work

Push to your `main` branch -> Railway auto-rebuilds and redeploys both services.
No manual steps.

```bash
git add .
git commit -m "tweak strategy"
git push
```

---

## Notes

- **Single backend instance only.** The Polygon WebSocket feeds and scheduler
  must run in exactly one process. Don't scale the backend to multiple replicas —
  Polygon rejects duplicate connections. One always-on instance is correct (and
  cheapest) for this app.
- **Paper trading state** lives in Redis, so it survives redeploys.
- **Market data caches** warm up on boot; the first few seconds after a deploy
  may show empty panels until the scheduler's first run.
