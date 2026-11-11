# Bounded public environmental overview

11 November 2026. Source base: main 4ad7de9. Implementation branch:
codex/environment-overview. The owner requested an environmental-information experience
alongside reporting, explicitly agreed to a public area-level overview, and authorised
checking the existing credentials and building the bounded version within the existing
frontend/hosting arrangement. No new paid service, database migration or auth system.

## Behaviour

/explore provides a manual-load overview for fixed representative points in New Delhi,
Gurugram and Noida. The same light UI, typography, navigation and report links are reused.
AQI/index identity, pollutants/native units, weather, 25km/two-day FIRMS detections and
separate Google 6/12/24-hour window peaks show source states and retrieval/observation
or valid times. These are point estimates/searches, not city averages, physical sensor
markers, legal findings or proof of a local source. No arbitrary coordinate, device
location, geocoder, case feed, Gemini or satellite request is added. Satellite/advanced
maps and history are outside this bounded release.

The anonymous API is GET /api/v2/explore/areas and POST
/api/v2/explore/areas/{area_id}/overview with an empty JSON object. Unknown areas, query
parameters and supplied identities/coordinates are rejected. Body buffering is capped
at 128 bytes with a bounded read deadline. The Next public proxy accepts only the three
area IDs, exact same-origin requests and an empty bounded body; it forwards no cookies,
access tokens or user headers. All existing private routes retain their independent
session/ownership/unit checks; legacy v1 remains blocked on the pilot API.

## Explicit public-purpose policy

The earlier case-only paid-context admission applies to resident/reviewer context and
processing. The owner's subsequent approval adds this narrow exception: operator-enabled
public environmental requests for the fixed registry, independent of any report. It does
not let anonymous callers access cases or invoke arbitrary locations/providers.
PUBLIC_OVERVIEW_ENABLED must be exactly 1; default off. The existing API PostgreSQL role
already has the needed abuse_windows grants. No role/schema change was made for this feature.

Every actual upstream HTTP attempt, including retries and forecast pages, is admitted
through a task-local context hook in the existing ProviderHTTP implementation. The hook
commits a PostgreSQL counter before network IO. Public HTTP calls share a default global
100/day limit; Google calls additionally debit the existing PAID_ANALYSIS daily budget.
Public views share 120/hour by default, including cache hits. These are pilot settings,
not measured capacity or cost guarantees. Limits work across service instances; no IP,
X-Forwarded-For, role or other spoofable request header grants quota. DB/quota failure
prevents provider invocation. The hook is reset on completion/cancellation and is absent
for existing case requests, whose own admission remains in place. Other independently
hosted legacy services are not governed by this new route's counters.

Provider clients and normalization/forecast arithmetic are reused. Fixed-area caches are
separate from private case caches. Content has no durable/provider-payload, hash, case,
export or backup persistence on this path. Volatile caches expire within 15 minutes;
response expiry uses original retrieval times and is not extended by cached reads.
The browser clears expired results, including on visibility return, uses no local storage
and makes no automatic refresh call. Requests/responses are no-store. No CDN cache is added.
API counters contain only global rule/time/usage metadata and use existing retention cleanup.

## Attribution and policies

Official unmodified Google Maps attribution SVG was downloaded from Google's attribution
asset bundle. It is served locally with 18px height and clear space. AQ and forecast cards
include the requested source credit; NASA attribution remains separate. /privacy and /terms
explain this overview, provider terms/privacy and controlled demonstration limits. They do
not claim actual government arrangements or completed real-data collection approval.

Official references consulted:
- https://developers.google.com/maps/documentation/air-quality/policies
- https://developers.google.com/maps/documentation/weather/policies
- https://cloud.google.com/maps-platform/terms/maps-service-terms
- https://firms.modaps.eosdis.nasa.gov/api/area/

Published current-condition/hourly-forecast caching ceiling is one hour under the cited
non-EEA terms; this implementation retains the stricter existing 15-minute maximum.

## Actual live credential checks

A one-time check used the original credential-configured airshedos-api Render service
at the fixed public Gurugram point. Google current AQ and weather returned live values;
FIRMS returned a live, valid empty detection list. A separate forecast check returned
live Google forecast with complete 6/12/24-hour coverage. No imagery, reports, identities,
Gemini or Earth Engine call was made. Keys/credential-bearing URLs were never displayed.
These results establish this session's original-host availability, not scientific accuracy,
future uptime or successful configuration on the separate new pilot host.

Only the existing local Google Maps Platform and NASA FIRMS key settings were selected
into an owner-only, Git-ignored overview settings file. No personal ADC, service-account
file or entire secret file was copied. The owner is configuring these on the existing
Free pilot API together with the explicit flag/limits and branch main. New-host live
verification remains pending until the tested code and settings are deployed.

## Verification and release

Full actual-PostgreSQL backend: 669 passed, two existing deprecation warnings, 59.66s.
Includes 12 new tests for public projection/privacy, cached expiry preservation, source
failures, unknown geography/identity spoofing, request/body limits, quota-before-calls,
retry metering and concurrent independent service instances sharing one database budget.
Signed SDK/BFF/PostgreSQL identity/proxy: 7 passed, zero skips. Frontend lint/type/build pass.
OpenAPI and frontend types regenerated; legacy receiver schema/protected records unchanged.
HTTPS production-build browser rehearsal: 12 passed (10 resident/public, 2 reviewer);
33.0s and 36.6s respectively, with actual PostgreSQL and synthetic OIDC/providers.
Mobile 390px and desktop 1440px screenshots were inspected; accessibility checks,
manual-only loading, stale-arrival rejection and expiry pass. Captures are explicitly
labelled synthetic. Final readiness/overview rerun: 25 passed, 5.68s.
Ruff: all checks pass, 152 files formatted. Git-visible + production-build secret scan:
3,461 files, zero findings. Final lint/type check and whitespace check pass.
Remote release checks and hosted outcome are recorded below at handoff.
The first final subset command lacked local network permission and produced connection
setup errors; rerunning with the required permission passed all 25 without code changes. The initial browser test locator matched Next's route announcer;
scoping it to the actual alert corrected the test without changing application behaviour.

Release uses the existing Vercel project and pilot Render API, no new broker/worker/host.
The pilot API must track main and have the five settings from the private overview file.
Verify one new-host public response, no-store headers, source status and public page before
claiming live overview. Private reporting still has separate reviewer/worker/cleanup gates.

## Publication and remaining external check

Source commit 934d86ab6cceeb5431c1410ec18c69a07780b025 merged through
[PR #16](https://github.com/aadiandrj-prog/airshedos/pull/16) as
994d0d1a4679524f4625fba95a55952eaf9b6495 on 11 November 2026, 18:49:45 IST.
Both the [source-head run](https://github.com/aadiandrj-prog/airshedos/actions/runs/43026646497)
and [merge-preview run](https://github.com/aadiandrj-prog/airshedos/actions/runs/43026659814)
passed all four jobs. The latter independently recorded 669 backend tests (81.08s),
10 resident/public + 2 reviewer browser tests in development and again in production HTTPS
(40.6s + 44.2s for production), all 62 legacy browser tests (1.5m), signed identity/proxy,
generated contracts, frontend lint/type/build and secret checks. Software-test counts are
not incident-accuracy, participant or capacity evidence.

The owner reported Render dashboard maintenance before installing the five overview
settings or switching the pilot service to main. The separate pilot /ready probe confirmed
database/recovery ready but Google/FIRMS unavailable; no new-host provider availability
is claimed. Overall 503 still reflects the independent reviewer/worker/cleanup dependencies.
Render completion steps remain: add the five private overview entries on airshedos-pilot-api,
select main, keep Free, then save/redeploy. Leave the old airshedos-api unchanged. Do not
repeat schema migration, recovery activation or Auth0 setup. After that, verify one bounded
Gurugram request on the new host before claiming live overview readings.

Vercel production deployment verification is recorded separately below. The disposable local
PostgreSQL container was stopped after verification. No paid hosting, new migration,
reviewer grant, custom model work or outreach occurred.

Vercel reported successful Production deployment for merge 994d0d1. Independent public
HTTPS probes then returned 200 with the expected new content for /, /explore, /privacy
and /terms on https://airshedos.vercel.app. Anonymous /api/app/v2/me remained 401/no-store.
One same-origin public proxy request returned the old pilot API's expected 404 with only
a static detail field and private,no-store, confirming that missing API deployment is
not misrepresented as live source data. No new-host paid provider call was made.
The page is published at https://airshedos.vercel.app/explore; source activation remains
pending the owner-operated Render settings step and subsequent live verification.
