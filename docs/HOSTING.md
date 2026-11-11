# AirshedOS hosting

Current execution evidence is recorded in [deployment status](seva/DEPLOYMENT_STATUS.md). The [pilot runbook](seva/PILOT_RUNBOOK.md) controls migration, identity, recovery, worker and retention setup. Previous prototype hosting instructions are in the [archive](archive/prototype/HOSTING.md).

## Services

- Vercel project root: `apps/web`; production tracks `main`.
- Separate pilot Render API: `airshedos-pilot-api`, Docker root `apps/api`, port 8000, `/health` liveness path.
- Neon PostgreSQL: application schema `seva_0006`, separate API/session/worker/cleanup logins. Owner credentials are for offline management only.
- Auth0: regular web application and RFC9068 custom API. Backend role/unit authority remains in PostgreSQL.
- A continuous processing worker and minute-based cleanup must run on an approved host or during the controlled laptop demonstration. No paid service has been authorised.

The retired root Blueprint is archived. Do not import the historical provider configuration into the new pilot. Services are being configured manually; no new Blueprint is automatically applied.

## Production promotion

A merge to main can trigger Vercel and existing Render services. Before merging, pause automatic deployment on the retired API, review checks and configure the new frontend's **Production** variables independently of Preview. Use `APP_MODE=pilot` and set `BACKEND_API_BASE_URL` to the pilot API.

Set production `APP_BASE_URL=https://airshedos.vercel.app`. Add exact Auth0 callback `https://airshedos.vercel.app/auth/callback`, logout origin `https://airshedos.vercel.app` and web origin `https://airshedos.vercel.app`. Keep the preview callback while preview testing remains necessary. Never use wildcard callback URLs.

The private Auth0 secret, separate random session keys and restricted session database URL must be present in Production, not only Preview. Rebuild/redeploy after changing variables. A successful build does not verify sign-in or a full resident/reviewer journey.

## Custom .tech domain

The existing clean Vercel address can serve the new app after production promotion. A custom domain is optional. Once the owner has registered the domain, add it under Vercel project Settings → Domains and follow the exact DNS records Vercel displays for that domain. Do not guess DNS records or modify unrelated email records.

After ownership/DNS/TLS verification, choose the canonical HTTPS origin, update APP_BASE_URL and exact Auth0 callback/logout/web origins, then redeploy and test login/logout. Preserve the previously working origins during the transition. Registration/redemption and any future renewal charges are owner decisions; no domain has been purchased or claimed here.

References: [Vercel domains](https://vercel.com/docs/domains/working-with-domains/add-a-domain), [production promotion](https://vercel.com/docs/deployments/promoting-a-deployment).
