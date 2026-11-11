# Auth0 preview configuration — setup in progress

11 November 2026. Owner selected preview only; no paid worker/cleanup service is authorised.
This prepares managed identity. It does not activate a complete hosted reporting pilot.
Do not bypass required database, recovery, unit, worker or cleanup readiness checks.

## Application

Use the existing owner-created **AirshedOS Pilot** regular web application. Its domain and
client ID were supplied privately in the setup conversation; no secret was requested.
Use the stable branch origin, not an individual deployment URL:

`https://airshedos-git-codex-seva-phase-7-grease-liquor.vercel.app`

On the application's Settings tab:

| Field | Exact value |
|---|---|
| Allowed Callback URLs | https://airshedos-git-codex-seva-phase-7-grease-liquor.vercel.app/auth/callback |
| Allowed Logout URLs | https://airshedos-git-codex-seva-phase-7-grease-liquor.vercel.app |
| Allowed Web Origins | https://airshedos-git-codex-seva-phase-7-grease-liquor.vercel.app |

Save. Do not use wildcard callbacks or add the old production origin during this preview.
Enable refresh-token rotation for this application and ensure Authorization Code and Refresh
Token grant types are enabled. Keep the token endpoint authenticated as a confidential regular
web application; no SPA/local-storage token flow. Review bounded refresh-token expiry when
activating sign-in; the application also enforces eight-hour absolute/30-minute idle sessions.

References: [application settings](https://auth0.com/docs/get-started/applications/application-settings),
[refresh rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/configure-refresh-token-rotation).

## Custom API

Applications → APIs → Create API:

| Field | Value |
|---|---|
| Name | AirshedOS Pilot API |
| Identifier | urn:airshedos:pilot-api |
| Signing algorithm | RS256 |

Settings → Access Token Settings: set JWT Profile to **RFC 9068**, maximum token lifetime
to **600 seconds**, and enable **Allow Offline Access**. If the dashboard also offers an
implicit/hybrid lifetime, keep it no greater than 600; this app uses authorization code.
Leave JWE off: this backend validates signed RFC 9068 access tokens, not encrypted tokens.
Save. RFC 9068 supplies at+jwt/client_id/jti, which the backend checks; do not weaken the
verifier or substitute an ID token if the profile is wrong.

Permissions tab: add `access:airshedos`, description “Access own AirshedOS workspace”.
Reviewer/unit powers are checked against current application PostgreSQL membership, not
Auth0 roles. Keep Auth0 API RBAC off for this design; enabling it requires a separately
reviewed scope-provisioning arrangement for every resident.

Application Access Policy: use **Per-app authorization** for user-delegated access and
**No apps allowed** for client/machine access. In Application Access, grant only the
AirshedOS Pilot application user-delegated `access:airshedos`. Do not grant Management API
scopes or machine-to-machine access to the web app. Save. If the current tenant UI differs,
inspect the actual labels before changing policy; do not create an admin-token workaround.

References: [API settings](https://auth0.com/docs/get-started/apis/api-settings),
[profile configuration](https://auth0.com/docs/get-started/apis/configure-access-token-profile),
[per-app policy](https://auth0.com/docs/get-started/apis/api-access-policies-for-applications).

## Server configuration still required

Vercel preview needs APP_MODE=pilot, APP_BASE_URL equal to the stable origin above,
AUTH0_DOMAIN and AUTH0_CLIENT_ID from the application, AUTH0_AUDIENCE=urn:airshedos:pilot-api,
its private AUTH0_CLIENT_SECRET, independent random 64-hex AUTH0_SECRET and
SESSION_ENCRYPTION_KEY, SESSION_DATABASE_URL for the restricted session role, and the
chosen BACKEND_API_BASE_URL. See pilot.env.example. These are server variables; none is
NEXT_PUBLIC. Secret values stay in dashboard secret fields/approved private process
configuration. Do not paste them into chat or commit them.

Configure this full group only after the selected database has its reviewed schema,
session role and empty recovery binding. Partial auth configuration must remain honestly
unavailable. A configured Auth0 app alone does not make login or reporting work.
Complete hosted token/refresh/logout verification and scope checks before declaring sign-in
verified. No live login, credential exchange or application database connection is claimed here.
