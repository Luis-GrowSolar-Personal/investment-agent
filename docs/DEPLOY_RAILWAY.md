# Deploying the Investment Agent to Railway

Single-service deployment: one Railway service hosts both the Express API and the React SPA. The server static-serves `client/dist` at `/`, with `/api/*` routes handled by Express. One URL like `your-app.up.railway.app`. No CORS to manage.

## Pre-flight (one-time setup)

These changes are already committed. No action needed unless you're re-creating from scratch:

- `nixpacks.toml` at repo root — tells Railway how to build (install both dirs, `prisma generate`, `vite build`) and start (`node server/index.js`).
- `server/index.js` — listens on `process.env.PORT`, static-serves `client/dist` in production, falls through to `index.html` for SPA routes.
- `client/.env.development` and `client/.env.production` — toggle `VITE_API_URL` between `localhost:3001` (dev) and same-origin (prod).
- All client API calls use `${API_URL}/api/...` instead of hardcoded localhost.

## Step 1 — Push the deployment changes to GitHub

If the repo isn't already on GitHub, create a new private repo and push. If it is, just commit and push the deployment changes:

```bash
git add nixpacks.toml server/index.js client/.env.development \
        client/.env.production client/src/pages/*.jsx \
        server/routes/radar.js .gitignore docs/DEPLOY_RAILWAY.md
git commit -m "Deployment config: Railway nixpacks + parameterized API URL"
git push
```

## Step 2 — Create the Railway web service

Open the Railway dashboard for the project that already hosts your Postgres.

1. Click **New** → **GitHub Repo** → select the investment-agent repo.
2. Railway auto-detects the `nixpacks.toml` and starts the first build.
3. The first build will fail because env vars aren't set yet — that's expected. Configure them in step 3, then redeploy.

## Step 3 — Set environment variables on the new service

Railway dashboard → the new service → Variables tab. Add:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference the Postgres service variable, not a hardcoded string |
| `ANTHROPIC_API_KEY` | (your key) | Same as your local `.env` |
| `CLERK_SECRET_KEY` | (your key) | Same as local `.env` |
| `CLERK_PUBLISHABLE_KEY` | (your key) | Same as local `.env` |
| `VITE_CLERK_PUBLISHABLE_KEY` | (your key) | Same as `client/.env`. Read at build time by Vite |
| `NODE_ENV` | `production` | Already set by `nixpacks.toml` but harmless to repeat |

`PORT` is set automatically by Railway — don't override.

After saving variables, click **Redeploy**. The build should succeed this time.

## Step 4 — Configure Clerk for the production domain

Once the Railway service is live, it gets a domain like `investment-agent-production.up.railway.app`.

1. Open the Clerk dashboard → your application → **Domains** (or **Configure** → **Domains**).
2. Add the Railway domain as an allowed origin.
3. If you want a custom domain (e.g. `agent.yourname.com`), add it now in Clerk *and* in Railway (Settings → Networking → Custom Domain).

Without this step, Clerk auth will fail in production with a CORS or origin error.

## Step 5 — Verify

Open the Railway URL in a fresh browser tab (or incognito to bypass any local cookies):

1. Sign in with Clerk → should work.
2. Stock Radar loads with all tickers → confirms DB connectivity.
3. Click a ticker → expands history → trend chips render → confirms Trend layer integration.
4. Stock Analyst → paste a transcript → click Analyze → confirms Anthropic API integration.
5. Advisory Feed → loads → confirms full stack.

If any step fails, check Railway service logs (Deployments tab → click the latest deploy → View Logs) for the error.

## Ongoing deploys

- **Code changes:** push to GitHub. Railway auto-redeploys on push to the configured branch (usually `main`).
- **Schema migrations:** when you run `npx prisma migrate dev` locally and commit the migration file, the deploy will *not* automatically apply it. Run `npx prisma migrate deploy` against the Railway DATABASE_URL after pushing, or add it as a `[phases.deploy]` step in `nixpacks.toml`.
- **Trend verdicts:** until Stage 3 (trigger-on-evaluate via Python subprocess) ships, you still need to run `python3 sync_trend_to_db.py` on your laptop after evaluating new transcripts.

## Cost estimate

Hobby plan ($5/mo + usage credit). One Postgres + one Express service for one user fits comfortably in the included credit. Watch the Railway billing dashboard the first month to confirm.

## Things to know about this deployment

- **Cold starts.** Railway may put inactive services to sleep. First request after sleep wakes the server (~5-10s). Acceptable for personal use; not for shared production.
- **Trend layer is still manual.** New transcript evaluations write to the DB, but trend verdicts only update when you run `sync_trend_to_db.py` on your laptop. Stage 3 (trigger-on-evaluate) closes that loop.
- **yfinance and DB scripts run only on your laptop.** None of `fetch_prices`, `fetch_fundamentals`, `sync_trend_to_db`, `inspect_trend_db`, `onboard_new_tickers` run on Railway. They use yfinance (blocked from most cloud egress) and direct DB writes.
- **Single point of failure.** One Railway service + one Postgres. No backups configured by default — set up Railway's automated daily Postgres backups in the database service settings.
