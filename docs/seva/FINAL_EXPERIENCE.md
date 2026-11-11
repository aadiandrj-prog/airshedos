# Final experience extension — 11 November 2026

Base main 9f9293f; branch codex/final-experience. The owner supplied an AirshedOS
ideation image and an Auralis visual reference and requested a richer final development
pass, following the discussion of optional location-based conditions. The images are
visual/ideation references, not evidence of a sensor network, official partnership,
validated plume model, adoption, regulatory certification or response-time performance.

## Delivered scope

- Colourful lavender/cyan/pink gradient atmosphere, stronger editorial hero, rounded
  controls, readable opaque panels, source ribbon and public feature pathways. Existing
  Geist font, branding and private workspace controls remain. CSS/SVG assets introduce
  no image generator, remote font request, new dependency or paid mapping service.
- A working on-demand environmental explorer embedded in the home page and shared with
  /explore, replacing the old synthetic report-timeline stage. Opening either page does
  not request device location or invoke environmental providers automatically.
- Optional Use my location requests browser permission once, rounds coordinates to a
  0.005 degree grid, and waits for View current conditions before fetching. Clear my
  location clears this view. Permission denial, poor device accuracy, timeouts, stale
  callbacks and subsequent area selection have explicit behaviour; three named areas
  remain available. No background tracking, profile write or report creation occurs.
- An interactive hourly Google AQ forecast for PM2.5, PM10 and CPCB AQI where returned.
  It has keyboard-selectable hour inspection, exact-value table, native units, gaps
  for absent hours and honest unavailable states. Existing 6/12/24-hour peak arithmetic
  and independent forecast caveats are reused unchanged. Lines join actual hourly points,
  not fabricated history or a newly trained AirshedOS model.
- A NASA-only relative-position detection diagram, selected detection details and an
  equivalent list with acquisition times, distance and categorical confidence. North
  is up; positions use spherical initial bearings and returned distance from the query
  centre. This is explicitly a schematic, not a street map, sensor mesh or source
  attribution. No Google content is plotted onto a non-Google map.
- Section jump links, source-status/freshness panel and a public /methodology route
  explaining providers, resolution, privacy, review and actual deployment prerequisites.
  /privacy is updated for voluntary approximate lookup. No fabricated readings, counters,
  affiliations, device installations or dispatch claims are used to fill the interface.

## API and privacy boundary

The existing operator-enabled public-purpose exception now also permits POST
/api/v2/explore/areas/nearby/overview with exactly latitude and longitude. Fixed named
areas still require an empty object and cannot be overridden. The nearby body accepts
finite numeric coordinates in valid global ranges; strings, booleans, unknown fields,
identities, roles, queries and partial points are rejected. Invalid v2 input uses the
existing static 422 projection, not echoed input. The 128-byte API body cap remains.

The browser and same-origin Next proxy coarsen coordinates, and Python enforces rounding
again before provider calls, public cache keys or response models. 0.005 degrees is about
550m north–south; east–west distance varies with latitude. It is a privacy choice, not
an assertion of device accuracy, provider precision or anonymisation. Providers receive
this approximate query point. Browser location requires HTTPS and user permission.
No URL query contains device coordinates; the proxy forwards no identity/cookies.

The proxy allows only four explicit IDs, exact Origin/Fetch Metadata, bounded JSON and a
five-second body read. There is no generic URL forwarding, new identity principal or
production test login. No precise user coordinates enter routine logs, analytics or a
persistent application location history. Approximate query/source content remains only
in the existing bounded volatile caches/response, with original retrieval expiry,
no-store responses, browser clearing and no local storage or automatic paid refresh.
This is minimisation, not a claim that hosting infrastructure or providers see no requests.

Public views and every actual provider attempt (including retries) retain PostgreSQL
shared admission and existing budgets. Arbitrary places cannot create unlimited retained
cache entries (32-entry cache), bypass source budgets or access any case data. Private
ownership/unit permissions, media, review/evidence, recovery, model and export behaviour
are unchanged. No database migration, new environment variable, service, worker, broker,
auth integration or public data collection programme is introduced.

## Existing hosting observation

The owner confirmed Render settings completed and the website working. An independent
/ready check on the pilot host showed public_overview enabled, Google/FIRMS configured,
database/recovery ready. It honestly retained overall 503 for separate missing worker,
cleanup, approved triage unit and optional private media. This configuration probe made
no provider call; it is not full pilot readiness or a live scientific validation.
A normal existing Vercel/API deploy is sufficient for this extension, pending release
checks; no repeated Auth0/Neon setup is required.

## Verification

Local full PostgreSQL backend: 681 passed, 2 existing deprecation warnings, 63.88s.
Three additional non-finite coordinate cases were then added without application changes;
final overview/readiness subset: 40 passed, 9.18s. Signed SDK/BFF/PostgreSQL and both public
proxy checks: 8 passed, zero skips, 2.51s. Production HTTPS browser: 14 public/resident tests
passed in 40.4s and 2 reviewer tests passed in 41.3s. Includes permission grant/denial,
rounding before transmission, no automatic request, clear-location, late GPS callback,
hour/metric/table interaction, missing-hour gaps, fire list and actual private journeys.

Frontend lint/type/build, generated OpenAPI/frontend types and Ruff lint/format pass.
No receiver-contract change. Build-inclusive secret scan: 3,509 files, zero findings.
All 11 protected historical records are byte-identical. Prior-phase screenshots regenerated
by the harness were restored to their original bytes; new captures have a separate folder.
Actual mobile/desktop screens were inspected, including axe, contrast-token, reduced-motion
and 320px reflow checks. Source-based scientific claims are unchanged, not re-evaluated.

Release commit/URLs are appended after GitHub checks finish. Synthetic browser
captures are under screenshots/final; numeric data views are explicitly labelled
synthetic. They are software verification, not participant or field-accuracy evidence.

Official provider references previously consulted in this session:
- https://developers.google.com/maps/documentation/air-quality
- https://developers.google.com/maps/documentation/weather/faq
- https://firms.modaps.eosdis.nasa.gov/alerts/notes.php
- https://developers.google.com/maps/documentation/air-quality/policies
- https://developers.google.com/maps/documentation/weather/policies

Stop boundary: no new forecast research, plume modelling, live sensor mesh, public case
feed, municipal dispatch, notifications, new hosting service or fabricated pilot results.


Initial remote runs 43051640487/43051650428 passed frontend/secrets and Vercel preview,
but browser setup failed before tests ran: azure.archive.ubuntu.com DNS failed while
installing Chromium's Ubuntu font dependencies. The CI prerequisite now rewrites only
Ubuntu mirror URIs to the direct official HTTPS archive/security hosts on disposable
GitHub Linux runners. Suites, components, keyring/signature verification and all actual
Playwright installs/tests remain unchanged; network waits/retries are bounded. No browser
check was removed or treated as passed. Local rewrite checks cover idempotence and
preserved suite/signature text; replacement remote runs are required before release.
The installed locked Playwright is 1.63.0; its official CI setup instructions and the
Geolocation API documentation were consulted. No dependency upgrade was introduced.

The first direct-archive replacement also failed DNS for archive.ubuntu.com. The CI-only
setup now probes bounded HTTPS release-file requests against the primary archive, Linux
Kernel Archives Ubuntu mirror and Princeton mirror, requiring both the release/security
pockets before choosing. Apt still verifies Ubuntu's package signatures with the original
keyring; a PGP header in the availability probe is not treated as cryptographic verification.
Missing mirrors fail closed, without skipping browser dependencies or tests. Fallback and
idempotence were exercised with deterministic subprocess injection. No runtime code changed.


## Release verification

Application source 4f30e7c plus CI-only prerequisites f9487f1/d991df5 merged through
[PR #17](https://github.com/aadiandrj-prog/airshedos/pull/17) as
99c6ed33969d266cab7a52b3d64081b8925aa2d0 at 21:44:37 IST on 11 November 2026.
Final exact-head [push run](https://github.com/aadiandrj-prog/airshedos/actions/runs/43054971388)
and [merge-preview run](https://github.com/aadiandrj-prog/airshedos/actions/runs/43054981461)
passed all four jobs. The latter recorded 684 backend tests (70.60s), 8 signed
identity/proxy checks, 14 public/resident + 2 reviewer browser tests in development and
again in production HTTPS (41.3s + 37.6s), all 62 legacy browser tests (1.5m), generated
contracts, lint/type/build, Ruff and secrets. The CI installer selected the Linux Kernel
Archives mirror; Ubuntu package signature checks remained enabled. Earlier failed setup
runs were superseded by complete successful runs; no substantive check was removed.

A separate local browser probe loaded both / and /explore with synthetic source responses
at a 320px viewport: both document widths were 320px with no overflowing explorer elements.
No real location/provider call was used for that check. The owned preview and disposable
PostgreSQL container were stopped. Hosted deployment and one bounded provider lookup are
recorded below after the normal existing-service release completes.


Vercel reported successful Production deployment of 99c6ed3. The pilot API's live OpenAPI
independently showed the new latitude/longitude request contract. A separate isolated
Chromium run then verified the actual public website: new home styling and location
control, zero automatic overview requests on home/explore, optional synthetic device
permission, one real same-origin nearby lookup, returned coarsened point, chart interaction,
clear-location, methodology and anonymous private-account 401 denial. The lookup used a
synthetic public Gurugram point, not the owner's/device's real location. All four source
states were live: Google AQ, Google weather, NASA FIRMS and Google AQ forecast.

Observed browser lookup latency: 5,217ms, N=1, with the API recently contacted for a
release-contract check. Frontend/function cold/warm state was not separately measured.
This is an observation under those conditions, not capacity, reliability, accuracy,
savings or cost evidence. One browser request was made; multiple underlying provider
attempts remain metered by the existing shared counters. Exactly-once provider billing
is not promised. No actual provider payload, numeric reading, live-result screenshot or
real location was persisted. Only the empty published homepage was captured temporarily
for visual inspection; source-result evidence here is limited to availability/status.

Published pages: https://airshedos.vercel.app/ , /explore and /methodology.
No new settings/service/migration/Auth0 setup or paid hosting was required. Private pilot
reviewer/worker/cleanup/media prerequisites remain separate from this public experience.
Official browser reference: https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition
CI prerequisite references: https://playwright.dev/docs/ci-intro ,
https://ubuntu.com/project/docs/release-team/mirrors/ and https://mirrors.edge.kernel.org/ .
