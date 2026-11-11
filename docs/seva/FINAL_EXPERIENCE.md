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
