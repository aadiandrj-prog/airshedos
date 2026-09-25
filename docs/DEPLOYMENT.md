# Earlier Cloud Run deployment proposal

> The current requested hosting target is Vercel + Render, with an empty Neon database. See [HOSTING.md](HOSTING.md) for the current deployment status. The proposal below records the earlier Cloud Run option; it is not the active deployment plan.

**Current status: locally verified prototype, not publicly deployed by this work.** Repository configuration uses localhost API/web origins and the existing browser key allows local origins only. Read-only inventory on 22 September 2026 found Cloud Run, Artifact Registry and Secret Manager APIs disabled in the configured Google Cloud project. No APIs were enabled, resources created, keys changed or public URL invented.

The containers and preparation below support a separately authorized, supervised prototype deployment. They do **not** make this a production or unrestricted public service. Deployment remains gated on approval of resources/cost, runtime identity, origin/key restrictions and the operational limitations below.

## Readiness review

| Area | Result |
|---|---|
| API/web containers | Single Uvicorn worker; non-root runtime users; Next standalone build; locally verified |
| Health | `/health` means process responsive; `/ready` means fictional repository initialized. External provider success is not a readiness prerequisite |
| Credentials | Server API credentials remain backend-only; Maps key is separate and intentionally browser-visible |
| Origins | Exact CORS origins supported; public API URL is a frontend build-time value. No wildcard production origin proposed |
| Public deployment | Not provisioned; authorization required before the commands below |
| State | Process-local, shared by users, lost on restart/eviction/TTL; no durable delivery or audit |
| Public abuse/privacy | No authentication, per-user isolation or application rate limit. Public visitors could consume paid provider quota, see prototype cases and change review/handoff state. CORS is not access control |

Use only synthetic demo material. An unrestricted, unattended public launch is **not recommended** within this scope. Agree a supervised demo window, provider quota limits and monitoring/stop procedure before exposure. Budgets and instance caps are not guaranteed hard spending caps. Authentication, persistence and a production abuse-control design remain outside Phase 3C.

## Environment separation

| Backend only | Purpose |
|---|---|
| `GOOGLE_MAPS_PLATFORM_API_KEY` | Existing Google current AQ/Weather/forecast server API key; restrict required APIs and quotas |
| `NASA_FIRMS_MAP_KEY` | FIRMS credential |
| `GOOGLE_CLOUD_PROJECT`, `EARTH_ENGINE_PROJECT` | Explicit backend cloud/quota and registered EE projects |
| `GOOGLE_CLOUD_LOCATION`, `GEMINI_MODEL` | Existing Gemini configuration, currently global / gemini-3.1-flash-lite |
| `CORS_ORIGINS` | Exact HTTPS frontend origin, no path/trailing slash; comma-separated only if deliberately allowing more than one |
| Timeouts/cache policy | Existing defaults remain unchanged; see root `.env.example` |

`OPENAQ_API_KEY` belongs only to offline developer research tooling and is **not required or passed to the runtime app**. No prediction/model artifacts belong in runtime images.

Frontend build-time variables: `NEXT_PUBLIC_API_BASE_URL` must be the actual browser-reachable HTTPS API URL; `NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY` must be a dedicated restricted browser credential; optional `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` identifies a configured style. Never put backend credentials in `NEXT_PUBLIC_*`. Rebuild the web image after changing public variables. Do not place server secrets into Docker build arguments.

Cloud Run should use an attached runtime service identity and ADC, not a downloaded service-account JSON or `GOOGLE_APPLICATION_CREDENTIALS`. See [Cloud Run service identity](https://docs.cloud.google.com/run/docs/securing/service-identity) and [secret configuration](https://docs.cloud.google.com/run/docs/configuring/services/secrets). Grant the runtime only Vertex AI User, Earth Engine Resource Viewer and Service Usage Consumer as required on the appropriate projects, plus Secret Accessor on the two selected secrets. Validate current organization policy and the [Earth Engine service-account requirements](https://developers.google.com/earth-engine/guides/service_account). The deployer needs separate deployment permissions; do not grant Owner/Editor to the runtime.

## Exact proposed deployment sequence — do not execute without separate authorization

Proposed resources in the existing project: one regional Docker Artifact Registry repository (`airshedos`), two Cloud Run services (`airshedos-api`, `airshedos-web`), one dedicated backend runtime service account and two Secret Manager secrets. Suggested region: `asia-south1`, subject to user approval and availability. These can incur costs. No custom domain, database, Cloud Build service or authentication product is required by this proposal.

1. Approve project, region, resources, public exposure, quota/budget controls and demo window. Enable Cloud Run, Artifact Registry and Secret Manager only after approval. Keep existing Vertex/EE/AQ/Weather/Maps enablement; register the EE project if needed.
2. Create the approved repository and runtime identity. Add API/FIRMS credentials through Secret Manager's secure interface, not shell history; pin their version numbers. Grant only the runtime permissions described above. Do not generate a service-account key.
3. Authenticate Docker for the approved registry. Build Linux/amd64 images locally and push them; local building avoids adding Cloud Build infrastructure. Define these shell variables with approved values (they are IDs/URLs, not backend secrets):

```sh
DEPLOY_PROJECT=REPLACE_PROJECT_ID
DEPLOY_REGION=asia-south1
DEPLOY_REGISTRY="$DEPLOY_REGION-docker.pkg.dev/$DEPLOY_PROJECT/airshedos"
DEPLOY_REVISION=REPLACE_GIT_COMMIT
DEPLOY_RUNTIME="airshedos-runtime@$DEPLOY_PROJECT.iam.gserviceaccount.com"
gcloud auth configure-docker "$DEPLOY_REGION-docker.pkg.dev"
docker buildx build --platform linux/amd64 --push -t "$DEPLOY_REGISTRY/api:$DEPLOY_REVISION" apps/api
```

4. Copy `deploy/backend.env.example.yaml` to ignored `data/deployment/backend.env.yaml`, substitute project and a temporary disallowed placeholder frontend origin, then deploy the API privately first. Existing API listens on 8000; Cloud Run must be configured with that port. Use approved secret names/version numbers:

```sh
gcloud run deploy airshedos-api --project "$DEPLOY_PROJECT" --region "$DEPLOY_REGION" \
  --image "$DEPLOY_REGISTRY/api:$DEPLOY_REVISION" --port 8000 \
  --service-account "$DEPLOY_RUNTIME" --cpu 1 --memory 1Gi \
  --min-instances 0 --max-instances 1 --concurrency 8 --timeout 120 \
  --env-vars-file data/deployment/backend.env.yaml \
  --set-secrets GOOGLE_MAPS_PLATFORM_API_KEY=airshedos-google-server:1,NASA_FIRMS_MAP_KEY=airshedos-firms:1 \
  --no-allow-unauthenticated
```

5. Obtain the actual API URL from `gcloud run services describe airshedos-api --format='value(status.url)'` with the same project/region. Build/push web with that HTTPS URL and the approved **public browser key** supplied through local environment. Do not print the key into verification artifacts:

```sh
docker buildx build --platform linux/amd64 --push -t "$DEPLOY_REGISTRY/web:$DEPLOY_REVISION" \
  --build-arg NEXT_PUBLIC_API_BASE_URL="$DEPLOY_API_URL" \
  --build-arg NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY \
  apps/web
gcloud run deploy airshedos-web --project "$DEPLOY_PROJECT" --region "$DEPLOY_REGION" \
  --image "$DEPLOY_REGISTRY/web:$DEPLOY_REVISION" --port 3000 \
  --cpu 1 --memory 512Mi --min-instances 0 --max-instances 1 --no-allow-unauthenticated
```

6. Read the actual web URL. Update backend `CORS_ORIGINS` to that exact HTTPS origin and deploy the updated env file. Add precisely `https://ACTUAL_WEB_HOST/*` to the approved browser key's website restrictions, restricted to Maps JavaScript API only. Local referrers may be retained deliberately for development; never allow `*`. Use a production map ID if required by the eventual presentation setup; the local default is DEMO_MAP_ID.
7. Only after explicit public-access approval, grant Cloud Run Invoker to `allUsers` on **both** services. The browser calls the API directly, so a public frontend with an IAM-private API will fail; no authenticated proxy or user OAuth flow is being added. Example approved-access command, applied separately to each service:

```sh
gcloud run services add-iam-policy-binding airshedos-api --project "$DEPLOY_PROJECT" \
  --region "$DEPLOY_REGION" --member=allUsers --role=roles/run.invoker
```

8. Verify HTTPS `/health`, `/ready`, web, exact CORS preflight (allowed origin succeeds; unrelated origin is not allowed), browser Maps origin, no server secrets in web output, real provider gates and the complete synthetic rehearsal on the actual origins. Record real URLs/revisions and any failures. Do not describe deployment as complete until this passes. Remove public access after the agreed demo window if that is the approved exposure policy.

## Important hosting limitation

Setting one worker and a maximum of one instance reduces accidental state splitting but **does not guarantee shared/durable state**. Cloud Run can replace instances, scale to zero, and briefly exceed limits during deployment/maintenance; revision changes can overlap. A visitor can lose a case between requests. See [maximum-instance limits](https://docs.cloud.google.com/run/docs/configuring/max-instances-limits). Session affinity is not durability and has not been introduced.

For the current hackathon, the fully verified local single-process deployment is the reliable baseline. A supervised Cloud Run rehearsal would need to demonstrate its actual behavior; it cannot be promised equivalent in-memory continuity. Do not roll revisions during a demo. Runtime startup health probes should target `/ready` without external API calls; [Cloud Run's container contract](https://docs.cloud.google.com/run/docs/container-contract) governs port/listening and lifecycle behavior.

## Rollback and readiness boundary

Locally, return to a verified Git revision and rebuild; restart clears ephemeral workflow and caches. For an approved cloud deployment, retain prior image digests and restore the prior service revision; expect state loss and rerun preflight. Never copy private citizen media or research/model artifacts to the deployment.

This document prepares a reviewable deployment plan. It authorizes and performs **no billable resource creation or public release**.
