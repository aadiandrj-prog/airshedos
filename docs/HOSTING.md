# Vercel, Render and Neon

Requested hosting arrangement:

| Service | Role | Current status |
| --- | --- | --- |
| Vercel | Next.js website | Project exists; public application verification pending |
| Render | FastAPI backend | [Backend](https://airshedos-api.onrender.com) `/health` and `/ready` verified; external-provider verification pending |
| Neon | Empty PostgreSQL database reserved for later | Provisioning pending; deliberately not connected to the app |

This is a supervised demo prototype. There are no accounts, private case spaces or rate limits. Use only synthetic demonstration material. Provider calls consume the configured Google/FIRMS quota. Free hosting can pause when idle; restarting the backend clears temporary workflow records. The empty Neon database does not change that.

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

## Empty Neon database

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
