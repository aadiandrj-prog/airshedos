# Graph-led explorer, Google Map and Gaussian scenario

11 November 2026. Base main 42dae3a; branch codex/plume-explorer. The owner explicitly
requested the graph and Gaussian plume mapping in local-air exploration, then made an
interactive Google Map a release requirement. This follow-up supersedes the previous
no-plume stop boundary only for an explicit educational, assumption-driven browser scenario.
It does not authorise a validated source-attribution system, custom forecast deployment,
new ML training, official dispatch or fabricated scientific/pilot claims.

## Delivered behaviour

The real Google hourly AQ forecast graph moves to the top of every loaded home/explore
briefing. Its hourly points, gaps, units, provider attribution, table and 6/12/24-hour
window peaks are unchanged. No measured-history graph is invented to match an ideation image.

A Google Maps JavaScript basemap follows the graph. It supports pan/zoom, normal Google
map controls, recentering, the rounded query point and up to the existing 50 returned
NASA FIRMS points. Detection markers have plain-text acquisition/distance information;
the existing equivalent list remains. Panning does not fetch new air readings or change
the query location. Google attribution/controls are retained, no tiles are copied or
persisted, no Map ID or deprecated Marker API is required (Data.Point is used).

The illustrative plume layer is explicitly toggled and visibly distinguished from NASA
and provider data. Its source is hypothetical, unrelated to any FIRMS point/report.
Controls set assumed continuous emission (g/s), constant wind speed/direction, effective
release height, linear horizontal/vertical mixing and local source offsets. A six-km
local grid and crosswind graph/table provide an accessible equivalent when the basemap
is unavailable. A reset returns to disclosed example inputs. Calm wind below 1m/s,
invalid inputs and the excluded first 50m downwind produce no fabricated concentration.

Source-rate/height/mixing defaults are examples, not estimated parameters. An optional
explicit action copies retrieved Google Weather surface wind, converted/rounded to 0.1m/s
for this constant-wind scenario; it does not establish release-height wind/stability.
Manual wind edits clear its provider provenance. Existing volatile content expiry removes
the entire map/scenario including copied wind. No local storage, new evidence version,
case/export record or provider refresh is created by scenario controls.

## Calculation and limits

For downwind x>=50m, ground level z=0 with ground reflection:

C = Q / (pi * u * sigma_y * sigma_z) * exp(-y^2/(2*sigma_y^2) - H^2/(2*sigma_z^2))

Q is g/s, wind u is m/s, all distances are metres; multiply g/m^3 by 1,000,000 for ug/m^3.
Sigma_y/z grow linearly using explicitly assumed spread at 1km. These linear parameters
are not inferred Pasquill classes or locally calibrated dispersion coefficients.
Meteorological FROM direction is reversed to the transport direction; north winds move
south and west winds east. The map overlay is generated only from these numerical pixels,
never from map imagery. A fixed logarithmic colour scale is labelled hypothetical increment,
not ambient PM2.5, AQI, probability or a safety boundary. The square is a viewport cutoff,
not a travel distance or arrival-time estimate. Upwind zero is a model assumption.

The equation assumes a continuous inert release, constant wind and flat ground. Buildings,
terrain, changing meteorology, chemistry, deposition, validated plume rise and actual source
emissions are not available. The model is not AERMOD or an operational/validated pollution
forecast, and its output does not enter corroboration rules, case decisions or Google AQ.
MODEL_NOT_ACCEPTED and the isolated forecasting research remain untouched.

Geographic placement uses spherical local offsets around the rounded query centre. The
small ground-overlay rectangle is an approximate local projection. Geographic scenario
overlays are disabled above 80 degrees latitude; the local numerical grid is still usable.
No actual source is identified or inferred. No health/enforcement finding is produced.

Primary references consulted for the equation, assumptions and maintained browser SDK:
- https://www.epa.gov/sites/default/files/2015-05/documents/pepcourse-equations1-2.pdf
- https://www.ready.noaa.gov/READYtransp.php
- https://developers.google.com/maps/documentation/javascript/load-maps-js-api
- https://developers.google.com/maps/documentation/javascript/datalayer
- https://developers.google.com/maps/documentation/javascript/groundoverlays
- https://developers.google.com/maps/documentation/javascript/policies
- https://developers.google.com/maps/documentation/javascript/get-api-key
- https://cloud.google.com/maps-platform/terms/maps-service-terms
No agency endorsement or regulatory model acceptance is claimed by referencing them.

## Configuration, privacy and usage

Only the public explorer is enabled by NEXT_PUBLIC_EXPLORE_MAPS_ENABLED=1 plus the existing
dedicated NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY. Private resident/reviewer map approval remains
controlled independently by NEXT_PUBLIC_PILOT_MAPS_APPROVED; this change does not enable it.
The browser key is distinct from the server provider key. An owner-only Git-ignored file
.secrets/maps-web-settings.env contains only the two selected web settings. No server key,
ADC, service account or entire environment file was copied. No new paid service/key/project,
backend route, migration, worker or authentication integration is introduced.

Map loads communicate directly from the browser to Google, including the rounded initial
centre, viewport and ordinary connection metadata; /privacy explains this. Server-side
PostgreSQL AQ/provider limits do not meter Google Maps JavaScript usage. Website/API key
restrictions and Google Cloud quotas govern map use under the owner's existing Google
account; map usage is not asserted to be free or bounded by the analysis-job budget.
The owner requested this integration and is saving the two public Vercel entries. Build-time
settings require a frontend deployment. Map SDK failures are visible; they do not remove
source readings or the equivalent list. No precise device location, private case point,
report/identity/note or role field is passed to the public map.

## Actual verification

Five deterministic calculation tests passed: closed-form ground reflection/units,
emission/wind scaling, crosswind symmetry and one-sigma ratio, meteorological wind rotation,
calm/invalid/near-field states, opacity monotonicity and geographic date-line wrapping.
These verify calculation implementation, not atmospheric predictive accuracy.

The production HTTPS browser rehearsal uses actual PostgreSQL/signed synthetic identities,
fake environmental fixtures and a browser-injected SDK-shaped Google test double. The
runtime application has no fake map endpoint or test-login route. Tests exercise map
initialisation, layers/markers, recenter, single map instance through slider changes,
provider-wind provenance, calm state, source expiry and no additional air/provider request.
All substantive existing resident/reviewer/legacy checks are preserved. A real secondary
button hover-contrast defect found by axe was fixed with an ink-colour rule; no audit was
weakened. Initial failed runs are not counted as passes. Final results are appended below.

Separate live SDK rehearsal: one real Google Map was created on the production website
origin using the existing dedicated browser key and a public Gurugram centre. Tiles loaded,
gm_authFailure stayed false, no Google key/billing/referrer error or map-error UI appeared.
No imagery, live source payload, actual device location or key value was persisted/printed.
This establishes the key/SDK rehearsal, not yet successful activation of the new deployed
component. Owner confirmation of the two Vercel entries and final component verification
remain external release dependencies until evidenced below.


Final local gates: signed identity/proxies 8 passed (2.74s), Gaussian calculation tests
5 passed (0.23s), production HTTPS public/resident browser 16 passed (50.7s), reviewer
browser 2 passed (44.7s). Lint, typecheck and production build pass. Source API models,
OpenAPI/frontend types and receiver contract are unchanged. Build-inclusive secret scan
passed across 3,564 files with zero findings. All 11 protected records remain identical;
prior-phase captures regenerated by the test harness were restored to original bytes.
The new desktop/mobile scenario captures were visually inspected and are explicitly
synthetic/SDK-test-double labelled. No actual Google imagery was captured to the repo.
Remote checks and actual deployed-component status are appended at release.
