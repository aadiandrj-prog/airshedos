# Vercel, Render and Neon

Requested hosting arrangement:

| Service | Role | Current status |
| --- | --- | --- |
| Vercel | Next.js website | [Public demo](https://airshedos.vercel.app) loads; Maps and backend connection verified |
| Render | FastAPI backend | [Backend](https://airshedos-api.onrender.com) `/health` and `/ready` verified; Gemini, AQ, Weather, forecast, FIRMS and satellite verified |
| Neon | Empty PostgreSQL database reserved for later | `airshedos` created on Free plan in Singapore; `neondb` public schema has zero tables; not connected to the app |

This is a supervised demo prototype. There are no accounts, private case spaces or rate limits. Use only synthetic demonstration material. Provider calls consume the configured Google/FIRMS quota. Free hosting can pause when idle; restarting the backend clears temporary workflow records. The empty Neon database does not change that.

## Deployment repair — 25 September 2026

PR #12 was merged at `e54ac04` after its current-head checks passed. Vercel previously served `872841f` with a 404; redeploying the older `3f53aa0` repeated a Next.js standalone/adapter packaging error. Deploying the fixed main restored the public site. Main CI passed.

Render's explicit `CORS_ORIGINS` still contained only localhost, overriding the corrected code default. The deployed setting now permits `https://airshedos.vercel.app` and the two local development origins. Production preflight returns 200 with the exact origin; an unrelated origin returns 400 without an allow-origin header. No wildcard is allowed. The frontend's built API URL points to the Render service.

The backend Google key was configured with a browser-referrer restriction, which rejected server AQ, Weather and forecast requests. The correction required explicit approval and was pending during this rehearsal; the approved repair and subsequent verification are recorded below. The separate Maps browser key already allowed the production origin and Maps rendered successfully. Do not solve server authentication by sending a fabricated browser referrer or removing all restrictions.

Real Gemini interpretation of the synthetic fixture completed in 3.4 seconds. NASA FIRMS and all three Sentinel-5P products returned live responses. The affected Google sources remain visibly unavailable; no substitute values are fabricated. Known backend Google/FIRMS/OpenAQ key values were absent from all eight script assets referenced by the public page. Provider health is a point-in-time check, not an uptime promise.

Public browser verification completed synthetic interpretation, corroboration, officer review, frozen packet generation, simulated send, receipt and acceptance with verified integrity. A fresh deployed API rehearsal independently validated the export against the receiver JSON Schema and sender SHA-256: PASS in 20.26 seconds (Gemini 4.96 seconds, corroboration 14.38 seconds, each handoff operation about 0.1 seconds). Frozen evidence and forecast stayed identical throughout transitions. This was a degraded-provider rehearsal: Google AQ/Weather/forecast remained unavailable, with WEAK corroboration shown honestly. Temporary cases from earlier sessions had expired as designed.

Read-only frontend requests now allow 70 seconds for free-host startup; loading copy explains the wait. Workflow writes retain their existing bounded timeouts and are not automatically retried. The new browser regression simulates an 11-second readiness response, exceeding the previous 10-second cutoff. Local frontend lint, typecheck, production build and all 58 browser tests passed; the build-inclusive secret scan passed with zero findings. Earlier phase verification documents and `MODEL_NOT_ACCEPTED` remain unchanged.

## Approved provider-key repair — 26 September 2026

After explicit approval, the existing backend key's browser restriction was replaced with Render Singapore outbound IP ranges `74.220.52.0/24` and `74.220.60.0/24`, verified in the service dashboard. API access was narrowed to `airquality.googleapis.com` and `weather.googleapis.com`. These ranges are shared with other Render services; callers still require the secret key. No key was rotated or exposed, and the separate Maps browser key was unchanged. Local backend calls using this same key will now be rejected outside these ranges; use a separately restricted development credential for local live verification rather than broadening the production key.

Deployed Gurugram verification at approximately 02:55 UTC (08:25 IST), coordinates `28.4595, 77.0266`:

- Google current AQ: LIVE, then CACHED; observation valid at 02:00 UTC, PM2.5 `70.06 µg/m³`, CPCB AQI `80`.
- Google Weather: LIVE, then CACHED; temperature `25.7 °C`.
- Google forecast: LIVE with complete 6/12/24-hour coverage, then CACHED with original retrieval time preserved.
- NASA FIRMS: LIVE, then CACHED. Sentinel-5P: LIVE, all three products usable; acquisition time 25 September 08:46:10 UTC. Scientific filters were unchanged.
- Public browser: API operational, Google map loaded, all three current-context sources available, forecast values and usable satellite observations displayed.
- `/health` and `/ready`: PASS. Warm readiness took 0.28 seconds. First context/forecast requests took 23.94/25.87 seconds, including backend startup; cached repeats took 1.24/3.40 seconds. Satellite request took 11.91 seconds.

| Google forecast horizon | Peak PM2.5 (µg/m³) | Worst CPCB AQI | Arithmetic outlook |
| --- | ---: | ---: | --- |
| 6 hours | 60.75 | 83 | IMPROVING |
| 12 hours | 87.95 | 104 | WORSENING |
| 24 hours | 98.95 | 153 | WORSENING |

These are point-in-time provider results, not a forecast accuracy claim or an AirshedOS-trained prediction. Forecast remains separate from corroboration support. The earlier degraded rehearsal record above is retained as historical evidence. No application code changed for this credential repair. Deployed main `142dfc1` has green [GitHub CI](https://github.com/aadiandrj-prog/airshedos/actions/runs/36167580049); its verified PR head passed 536 backend tests and 58 browser tests, Ruff, frontend lint/typecheck/build and generated-type checks.

## Backend on Render

Import `aadiandrj-prog/airshedos` using the root `render.yaml` Blueprint, or create a Docker web service with these settings:

- Root directory: `apps/api`
- Dockerfile: `./Dockerfile`; Docker context: `.`
- Branch: `main`; automatic deployments only after checks pass
- Health check: `/ready`; port: `8000`
- Free instance, one worker, Singapore region
- No persistent disk or Render database

The existing Docker image starts one Uvicorn worker. `/health` checks process responsiveness; `/ready` checks initialization independently of external providers. See [Render's Blueprint fields](https://render.com/docs/blueprint-spec) and [free-service limitations](https://render.com/docs/free).

Set `CORS_ORIGINS` to the exact deployed HTTPS Vercel origin, without a path or trailing slash. Do not use `*` or a blanket `*.vercel.app` rule. Add a preview origin individually only when needed.

Do not bulk-copy the local `.env` into both hosts: local URLs and browser-only settings are not production backend settings. Render's environment variables override code defaults.

Backend-only secrets: `GOOGLE_MAPS_PLATFORM_API_KEY` and `NASA_FIRMS_MAP_KEY`. Backend-only project settings: `GOOGLE_CLOUD_PROJECT`, `EARTH_ENGINE_PROJECT`, `GOOGLE_CLOUD_LOCATION` and `GEMINI_MODEL`. Do not supply OpenAQ or research/model artifacts to the runtime. Missing credentials retain the existing explicit unavailable/configuration states.

Gemini and Earth Engine require a dedicated server-side Google identity as well as the project settings. Local personal ADC does not automatically follow a Render deployment. Do not upload a personal ADC refresh-token cache or put Google credentials in Git. Production identity must be configured securely and verified before calling those providers live; merely setting a project ID is insufficient.

## Website on Vercel

Import the same repository, selecting root directory **`apps/web`** and the **Next.js** preset. The app's `vercel.json` defines the install/build commands. Use Node 22 or newer.

Vercel builds use its native adapter (`VERCEL=1`); other builds retain standalone output for Docker. This avoids the Next.js 16.3 standalone/adapter packaging conflict without changing the container runtime.

Public build-time variables:

- `NEXT_PUBLIC_API_BASE_URL`: the actual Render HTTPS service URL.
- `NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY`: the separate, restricted Maps browser key.
- `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID`: optional; keep the existing default otherwise.

No backend key or database connection string belongs in the frontend. Add the exact deployed `https://HOST/*` referrer to the browser key's restrictions while retaining only Maps JavaScript API access. Rebuild after changing public environment variables. See [Vercel monorepos](https://vercel.com/docs/monorepos) and [environment variables](https://vercel.com/docs/environment-variables).

Use Vercel's Config visibility for `NEXT_PUBLIC_*` values, which are intentionally browser-visible. A secret visibility label does not make a public-prefixed value private. The existing project contains unnecessary backend-only variables from setup; application code does not reference or expose them, but they should not be included in future frontend configuration.

## Empty Neon database

Provisioned on 25 September 2026: project `withered-glade-58447528`, default branch `production`, database `neondb`, Postgres 18, AWS Singapore, Free plan. The table browser confirms zero tables in the public schema. No connection string was added to Vercel, Render or the repository. Auth, object storage, functions and AI gateway were not enabled.

Provision a separate AirshedOS project using the free plan where available. Create no application tables, run no migrations and import no reports, images, model artifacts or historical datasets. Keep the database connection details in Neon's secure dashboard; the application does not need a `DATABASE_URL` for this task. Do not enable extra integrations or expose database credentials to Vercel's browser bundle.

The app remains process-local until a separately requested persistence change is implemented and tested.

## Deployment verification

Before recording a service as deployed:

1. Verify the actual frontend URL and Render `/health` and `/ready` over HTTPS.
2. Verify the exact frontend origin is accepted by CORS and an unrelated origin is not.
3. Open the deployed app and check API connectivity, map loading or its honest fallback, provider states, mobile layout and the synthetic workflow.
4. Verify no backend credentials are present in frontend assets or committed files.
5. Verify Neon exists and has no application tables; do not publish its connection string.
6. Record the deployed revision, actual URLs and any provider/configuration blockers here.

The older [Cloud Run deployment proposal](DEPLOYMENT.md) is retained for context. Vercel/Render/Neon is the current requested target; no Cloud Run deployment is part of this task.
