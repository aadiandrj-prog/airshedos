# Forecasting: operational provider outlook and rejected custom research

## Google operational forecast — current product

AirshedOS uses the official [Google Air Quality forecast endpoint](https://developers.google.com/maps/documentation/air-quality/forecast). The provider supports up to 96 hours; this integration requests only the next **24 hourly valid times** and derives **6, 12 and 24-hour** summaries. It is an external operational outlook, not an AirshedOS-trained prediction, a probability, a causal event forecast, or an independent corroboration source from Google current AQ.

Use “Google Air Quality forecast indicates…” or “Provider forecast outlook…”. Provider identity and source credit remain visible in both the standalone coordinate probe and the Evidence Fusion Card.

### API, configuration and normalization

`GET /api/v1/environment/forecast?lat=28.4595&lng=77.0266&horizon_hours=24`

Coordinates use existing finite/range validation. Allowed horizons are 6, 12 and 24 (default); the response includes hourly rows up to the selected horizon and all supported summaries up to it. Invalid inputs return 422. Provider failures return HTTP 200 with explicit `error`, `unavailable` or `not_configured` states and empty hourly data. `live` means a fresh provider response, **not a live measurement of future air quality**. Cached results use `cached`.

The backend reuses `GOOGLE_MAPS_PLATFORM_API_KEY`; no new key, credential file, frontend SDK or user authentication flow. Enable the Air Quality API and use the existing backend restrictions. `FORECAST_CACHE_TTL_SECONDS=900` is optional (0 disables caching, maximum 1800). Compose forwards this setting.

The official POST `https://airquality.googleapis.com/v1/forecast:lookup` receives the key in `X-Goog-Api-Key`, a location, `period`, `pageSize=24`, `universalAqi=true`, `extraComputations=[LOCAL_AQI, POLLUTANT_CONCENTRATION]` and English language. The [API reference](https://developers.google.com/maps/documentation/air-quality/reference/rest/v1/forecast/lookup) specifies an inclusive end time. Starting with the next whole UTC hour and ending at the current UTC hour plus 24 requests exactly 24 hourly points, not 25. Horizon means those next N hourly forecast points; no interpolation at the current minute is implied.

The adapter retains `hourlyForecasts.dateTime`, index code/value/category/dominant pollutant, pollutant code/names/concentration/native units, and region code. Timestamps are timezone-aware UTC. `forecast_at` is the forecast's valid time; Google does not supply model issuance time in this response, so `issued_at=null`. `retrieved_at` is actual retrieval time and is preserved on cache hits. Provenance names the endpoint, provider, deterministic summary method and limitations. Frontend display uses explicitly labelled IST.

The adapter handles pagination (bounded to four pages), rejects cycles, duplicate hours/products, invalid or out-of-window timestamps, negative/nonfinite values and malformed results. It sorts valid hours and drops empty hour metadata. Missing pollutant values remain missing. It preserves other index systems but **only `ind_cpcb`** participates in AQI comparisons and maxima. See [Google's index list](https://developers.google.com/maps/documentation/air-quality/laqis). If CPCB is absent, show pollutants and “Not supplied”; never silently substitute Universal AQI.

PM2.5 and PM10 retain `MICROGRAMS_PER_CUBIC_METER` (displayed as µg/m³). Other pollutants retain their source units, including `PARTS_PER_BILLION`. No conversions, CPCB calculation from instantaneous PM, or regulatory category derivation are performed. Provider AQI and pollutant peaks can occur at different times and need not track each other numerically.

### Deterministic summaries

For each horizon, take the maximum supplied CPCB AQI and its provider category, maximum PM2.5, and maximum PM10. Ties select the earliest valid time. `peak_at` identifies the PM2.5 maximum (or CPCB maximum when PM2.5 is absent), with explicit `peak_basis`; separate `cpcb_peak_at` and `pm10_peak_at` retain other maxima. Concentrations in mixed units are not ranked together. Return total, PM2.5 and CPCB hourly coverage counts. Partial peaks describe available points, not guaranteed full-horizon maxima.

Current PM2.5 comparison requires matching units, nonnegative current concentration, and a current observation between five minutes in the future (clock tolerance) and two hours old. Otherwise comparison is withheld. Arithmetic `delta_pm25_vs_current = forecast_peak - current`; relative percent is `100 × delta / current` only when current is positive. Zero-current comparisons have no percentage.

The descriptive trend additionally requires complete PM2.5 coverage and µg/m³ units. Using current concentration C and delta D:

| Category | Exact rule, applied in this order |
| --- | --- |
| SHARPLY_WORSENING | D ≥ max(25 µg/m³, 0.50 × C) |
| WORSENING | D ≥ max(5 µg/m³, 0.10 × C) |
| IMPROVING | D ≤ −max(5 µg/m³, 0.10 × C) |
| STABLE | Otherwise |
| UNAVAILABLE | Comparison requirements unmet |

These are transparent product descriptions of a **peak-versus-current** comparison, not a forecast slope, regulatory alert category, incident risk score, confidence or probability. Incomplete data never yields an inferred improving/stable category. Current CPCB is displayed with its observation time; it is compared only with forecast CPCB, not another index system. The UI shows coverage, separate source status and provenance, and explains the rules.

### Separation, cache and failure behavior

```text
Citizen → Gemini interpretation → environmental corroboration → assessment
                                                                  ↓
                                       Google AQ forecast → separate outlook
                                                                  ↓
                                                     officer decision support
```

`CorroborationAssessment.forecast_outlook` is optional and added **after** `assess()` returns. No forecast field is passed to the rules, source aggregation, support level, or recommended-next-step decision. Google current and forecast AQ share a provider/model ecosystem and must not count as two evidence votes. No operational priority or new advisory scoring was introduced. Tests compare every assessment field while changing forecast values and availability.

The default current-context endpoint is unchanged and performs no forecast request. The command center fetches forecast and existing environmental panels separately. The standalone forecast endpoint gathers current AQ and forecast concurrently; corroboration reuses its existing current AQ result and retrieves only the outlook. Forecast failure leaves current AQ, weather, FIRMS, satellite and the already-computed assessment intact.

Reuse the existing bounded in-memory cache (256 shared entries, deep copies, idle expiry). Cache key contains exact validated coordinates, the canonical requested **24-hour upstream horizon**, exact UTC start/end, computations, language and universal-index option. The caller's 6/12/24 selection is applied to that one batch; no redundant upstream requests per summary horizon. TTL is 15 minutes, with UTC-hour changes creating a new window. Current AQ retains its existing cache. Summaries are recomputed against the available current reading when returning a cached forecast. Provider errors and empty results are not cached. Requests coalesce under a bounded lock; HTTP retains existing bounded retries. Service deadline defaults to 17 seconds (2 × 8-second HTTP timeout + 1); it also bounds lock waits. Reported context latency includes any concurrent current-AQ lookup, not just the forecast HTTP round trip.

Attribution follows [Google's Air Quality policies](https://developers.google.com/maps/documentation/air-quality/policies), including Google Maps text attribution and “Source: Includes air quality data from Google”. Retention and deployment remain subject to the project's Maps agreement. No production snapshot database was introduced.

## AirshedOS custom model research — evaluated and rejected

**An internal custom operational model was evaluated and rejected because it underperformed the naive baseline.** Phase 2D concluded **MODEL_NOT_ACCEPTED**. Its artifacts, negative result and predeclared model-selection protocol remain intact. No custom model is deployed, no Vertex job/endpoint was created, no retuning or renewed model selection was performed in Phase 2E, and the locked November–December test set remains unopened by candidate evaluation. [Phase 2D verification](PHASE_2D_VERIFICATION.md) remains the record of that decision.

The external Google forecast does not reverse or replace the custom model's failed acceptance decision. It is an independently maintained provider service used operationally with explicit attribution.

## Verification and limits

Run the manual backend-only gate from the repository root:

```sh
apps/api/.venv/bin/python apps/api/scripts/verify_forecast.py
```

It queries the fixed Gurugram point (28.4595, 77.0266), captures current AQ, every hourly forecast, all three summaries, provenance, latency and cache reuse, and exits nonzero if integration gates fail. It reads the ignored root `.env` without printing credentials. **CI never invokes it**; backend transports prohibit external calls and browser forecast routes are intercepted with synthetic fixtures. See [Phase 2E verification](PHASE_2E_VERIFICATION.md).

One successful query verifies integration only. Forecast accuracy remains unmeasured. Current history responses are not an archive of forecasts issued in the past; they must not be used to manufacture a historical forecast backtest. Prospective, consented logging and later outcome comparison are future work. No persistence, notifications, maps, source attribution, plume modelling, custom model training or Phase 3 work was added.
