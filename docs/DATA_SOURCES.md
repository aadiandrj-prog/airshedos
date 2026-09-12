# Environmental data sources — Phase 1C

Current implementations use backend-only HTTP requests and the official Earth Engine Python SDK. Test fixtures are synthetic and never imported into production. **Live verification passed on 11 September 2026** for Google Air Quality, Google Weather and NOAA-20 FIRMS at the fixed NCR probe; see [the timestamped gate report](PHASE_1B_VERIFICATION.md). Missing credentials return `not_configured`, never a substitute reading. Configuration alone does not prove enabled APIs, billing, quota, coverage or successful access.

## Configuration

Copy root `.env.example` to root `.env` (ignored by Git). For local Uvicorn, use `--env-file ../../.env` from `apps/api`; Compose and the manual verification script load root `.env`. Google Air Quality and Weather must be enabled in the key's Google Maps Platform project, with applicable billing and API restrictions. Obtain a FIRMS MAP_KEY from [NASA FIRMS API access](https://firms.modaps.eosdis.nasa.gov/api/). Keep both keys backend-only. The frontend environment example contains only the public backend URL.

| Variable | Default / meaning |
| --- | --- |
| `GOOGLE_MAPS_PLATFORM_API_KEY` | Empty; shared by Google AQ and Weather adapters |
| `NASA_FIRMS_MAP_KEY` | Empty; FIRMS area requests |
| `ENVIRONMENT_HTTP_TIMEOUT_SECONDS` | 8; per-attempt deadline/read timeout, range 1–30 |
| `ENVIRONMENT_CACHE_TTL_SECONDS` | 600 seconds for Google AQ and Weather, 0–3600 |
| `FIRMS_CACHE_TTL_SECONDS` | 900 seconds, 0–3600 |
| `FIRMS_SEARCH_RADIUS_KM` | 25 km, configurable from 1–100 |
| `FIRMS_DATASET` | `VIIRS_NOAA20_NRT`; also accepts `VIIRS_NOAA21_NRT` and legacy `VIIRS_SNPP_NRT` |

## Google Air Quality

Role: current air-quality context for the exact requested coordinate. The adapter uses [currentConditions lookup](https://developers.google.com/maps/documentation/air-quality/reference/rest/v1/currentConditions/lookup), requesting universal AQI, local AQI and pollutant concentrations. It retains index code/name/value/category/dominant pollutant, pollutant code/name/full name/concentration, region code, `dateTime`, query coordinates, retrieval time and provenance.

[Pollutant source units](https://developers.google.com/maps/documentation/air-quality/reference/rest/v1/Pollutant) remain intact, including µg/m³ and ppb. The UI changes unit labels only; it does not convert concentrations, calculate AQI, or treat universal and Indian indexes as interchangeable. Missing values stay null.

Estimated/modelled AQ is not equivalent to a newly installed regulatory monitoring station. Availability and update time depend on provider coverage. A successful HTTP response without useful indexes or pollutants is unavailable, not zero AQI.

When data is displayed, the card includes Google Maps attribution and “Source: Includes air quality data from Google”, following the [Air Quality display policies](https://developers.google.com/maps/documentation/air-quality/policies). The separate demo schematic does not display Google data. The [service-specific terms](https://cloud.google.com/maps-platform/terms/maps-service-terms) permit temporary caching of current conditions for up to one hour; the cache defaults to ten minutes and configuration is capped at one hour.

## Google Weather

Role: current meteorological context for a later, explicitly separate forecasting phase. The [current conditions endpoint](https://developers.google.com/maps/documentation/weather/current-conditions) is queried with metric units. Fields retained: temperature; relative humidity; wind speed, cardinal direction and degrees; mean sea-level pressure; precipitation probability and quantitative precipitation estimate; cloud cover; `currentTime`; coordinates; retrieval time and provenance.

[Wind direction](https://developers.google.com/maps/documentation/weather/reference/rest/v1/Wind) is the direction **from which** wind originates, clockwise from north: 0° north, 90° east, 180° south, 270° west. Source 360° is normalized to 0°. It is not an inferred plume destination. Pressure uses millibars; quantities preserve their source units. Precipitation estimates are not an AirshedOS forecast.

Unavailable variables remain null. Provider coverage, outages and cadence can differ from AQ. Google Maps attribution appears alongside returned readings under the [Weather policies](https://developers.google.com/maps/documentation/weather/policies). Current conditions caching follows the one-hour limit in the [service-specific terms](https://cloud.google.com/maps-platform/terms/maps-service-terms); the default here is ten minutes.

## NASA FIRMS

Role: nearby active-fire detections, **not confirmed pollution sources**. The [official area CSV API](https://firms.modaps.eosdis.nasa.gov/api/area/) is queried for a single configured VIIRS product, defaulting to `VIIRS_NOAA20_NRT`, today and the previous UTC day (day range 2). NOAA-21 and legacy S-NPP are selectable; multi-sensor fusion and historical ingestion are outside this implementation. NASA announces that Suomi NPP product delivery will cease on 1 November 2026, so S-NPP is no longer the default or sole supported product. See the [official product notice](https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data).

A spherical bounding box covers the configured radius; antimeridian queries split into two boxes. Haversine distance filters each candidate to the actual circle. Results are deduplicated by source identifier and sorted nearest first. The small geometry utility handles poles and date-line crossings without heavyweight GIS dependencies.

The normalized context exposes `fire_dataset` even when no detections are returned, and the frontend labels that product dynamically. Fields retained: detection coordinates; acquisition date plus zero-padded acquisition time interpreted as UTC; satellite/instrument; categorical VIIRS confidence (`l`, `n`, `h`); I4 brightness temperature in kelvin; fire radiative power in megawatts; distance in km; dataset-derived identifier; retrieval time and provenance. Confidence categories are not probabilities. See [VIIRS product attributes](https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data).

An HTTP 200 CSV containing only valid headers is a successful zero-detection result (`fires: []`). Invalid headers, including an HTTP 200 key-error message, produce `error` and `fires: null`. No location is changed to force a detection. Thermal detections can reflect different heat sources; clouds, overpass timing and coverage affect availability. Detections do not establish burning type, emissions, transport or causation.

FIRMS embeds its key in the request path. HTTPX/HTTPCore URL logging is suppressed and application logs never include that URL, raw responses or exception strings.

## Availability and time semantics

Every source independently reports `live`, `cached`, `unavailable`, `not_configured`, or `error`. `live` means a fresh successful provider response, not continuous monitoring or an observation made this instant. Observe the source's `observed_at` separately from `retrieved_at`; cached values retain both times. Provider outages and partial results are expected. A failed source does not erase another source's observations.

For AQ, Weather and FIRMS, the optional `at` parameter remains timezone-aware reference metadata only: they request current conditions and recent detections. Satellite alone uses `at` as its search-window end. Sources have different observation/update cadences, and AirshedOS does not align them into a causal explanation or calculate a live risk score.

## Manual verification

From `apps/api` with the virtual environment activated:

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --gate --json
```

The concise output reports actual request time, provider states, latency and representative values when available. JSON includes full normalized observations and provenance. The optional `--gate` makes a second identical request, verifies no additional outbound responses and unchanged observation/provenance data, then disables Weather only in that local service instance to check partial success. It prints a PASS/FAIL result (nonzero exit on gate failure) without altering `.env` or provider services. No secrets are printed. This command is excluded from CI; automated tests clear credentials and reject real HTTP transport. See [Phase 1B verification](PHASE_1B_VERIFICATION.md) for the actual delivery result.

Gemini, Vertex AI prediction, historical storage, custom AQI conversion, evidence fusion scoring, Google Maps, jurisdiction interoperability and pollution-source attribution remain future work.

## Earth Engine / Sentinel-5P

Satellite atmospheric evidence is implemented in Phase 1C. Authentication and live coverage results are tracked in [Phase 1C verification](PHASE_1C_VERIFICATION.md); Phase 1B’s live success is not evidence that Earth Engine works.

### Backend authentication

1. Choose a Google Cloud project, preferably the existing Maps project. Enable the Earth Engine API and [register the project for Earth Engine use](https://developers.google.com/earth-engine/guides/access). Registration/eligibility is a project-owner action.
2. Install the official Google Cloud CLI and configure local [Application Default Credentials](https://developers.google.com/earth-engine/guides/auth). For local development:

   ```sh
   gcloud auth application-default login --scopes=https://www.googleapis.com/auth/earthengine,https://www.googleapis.com/auth/cloud-platform
   gcloud auth application-default set-quota-project YOUR_PROJECT_ID
   ```

3. Set `EARTH_ENGINE_PROJECT=YOUR_PROJECT_ID` in the ignored root `.env`; `GOOGLE_CLOUD_PROJECT` is the fallback, so setting both is unnecessary. The SDK uses `google.auth.default` and `ee.Initialize(credentials=..., project=...)`. An existing Maps API key is not sufficient. No frontend OAuth flow is introduced.
4. The principal needs Earth Engine read/compute access and service-usage permission on that project. Prefer the least privileges appropriate to project policy ([Earth Engine Resource Viewer plus Service Usage Consumer](https://developers.google.com/earth-engine/guides/access_control) for read-only computations); do not grant Owner or create long-lived service-account keys for this workflow. No service account or IAM changes are created by this implementation.

The normal local backend uses ADC from the standard Cloud SDK location or `GOOGLE_APPLICATION_CREDENTIALS`. Never paste credentials into chat or `.env`; the latter variable is a **path**, not JSON. Never commit ADC caches, access/refresh tokens or service-account JSON. Startup performs no authentication and remains healthy when configuration is missing. `provider_status.configured` means project presence, not verified ADC; product status/messages distinguish missing credentials, authentication rejection and project setup errors.

For Docker, credentials are not copied into images. Optionally bind-mount an existing ADC file read-only:

```sh
EARTH_ENGINE_ADC_FILE=/absolute/path/to/application_default_credentials.json \
  docker compose -f docker-compose.yml -f docker-compose.earth-engine.yml up --build -d --wait
```

Ensure the container's non-root user can read the mounted file without making credentials broadly readable. The default Compose file has no credential mount and will report missing ADC even if the host has ADC. Prefer a local backend if host/container file permissions cannot be safely aligned. This optional mount cannot be live-verified without actual ADC.

### Exact products and quality rules

| Product | Earth Engine collection | Selected band | Native unit | Upstream catalog ingestion QA |
| --- | --- | --- | --- | --- |
| Tropospheric NO₂ column | `COPERNICUS/S5P/NRTI/L3_NO2` | `tropospheric_NO2_column_number_density` | `mol/m²` | Tropospheric NO₂ QA ≥ 0.75 |
| CO column | `COPERNICUS/S5P/NRTI/L3_CO` | `CO_column_number_density` | `mol/m²` | CO QA ≥ 0.50 |
| UV Aerosol Index, 354/388 nm | `COPERNICUS/S5P/NRTI/L3_AER_AI` | `absorbing_aerosol_index` | dimensionless | AER_AI QA ≥ 0.80 |

Sources: [official NO₂ catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_NO2), [CO catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_CO), [UV Aerosol Index catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_AER_AI).

The catalog’s older example HARP commands use validity >50 even for NO₂/AER_AI; the table above follows its explicit current ingestion-threshold description. Because the L3 QA band is absent, AirshedOS cannot independently audit each upstream QA value. This limitation is retained rather than claiming a newly verified pixel threshold.

These Earth Engine L3 assets have **already been quality-filtered during ingestion**. The original L2 pixel `qa_value` band is not exposed. AirshedOS preserves the existing valid-pixel mask; it does not pretend to apply a nonexistent QA band or infer a confidence percentage. It additionally requires `PRODUCT_QUALITY` in `{Nominal, NOMINAL}`. Accepted `PROCESSING_STATUS` is `{Nominal, NRTI-processing product}` for NO₂ only, and `{Nominal}` for CO and Aerosol Index. Missing, unknown, degraded and OFFL backup values are rejected. Raw accepted metadata is preserved in observation quality. For column bands only, it masks values below −0.001 mol/m² following the catalog’s negative-outlier guidance, while retaining other negative retrievals. Negative aerosol-index values remain valid. No arbitrary cloud mask or extra product is added. `usable` means these filters passed, not calibrated confidence or source attribution.

### Geometry, timing, and selection

Defaults: 10 km buffered point, 72-hour lookback, current UTC hour as the exclusive window end. Coordinates are rounded to four decimals for a shared query/cache center (about 11 m latitude, negligible relative to the footprint); the original coordinates are also retained. An explicit timezone-aware `at` supplies the exact end instead. Both boundaries are returned. Lookback accepts 1–168 hours; radius accepts 1–25 km.

For each product the query filters collection by geometry and time, retains nominal scenes, preserves upstream masks and applies the column outlier mask, then computes the **mean** and count of valid cells within the neighborhood for every candidate. It discards reductions with no value/valid cells, sorts usable reductions by original `system:time_start` descending, and returns the latest one. The latest image is not assumed usable. No interpolation or across-scene averaging is performed. Source `system:index` forms the full collection/image ID; acquisition time, product ID and `SPATIAL_RESOLUTION` metadata are retained.

The reduction grid scale is **1,113.2 m**, the catalog's resampled L3 grid. This is **not native spatial resolution**: TROPOMI footprints span several kilometers and vary by product/time. The 10 km radius supplies regional context across multiple footprints without implying street-level precision. Counted cells are resampled grid cells, not independent sensor measurements. No `bestEffort` scale changes are allowed.

The latest NO₂, CO and aerosol observations may have different acquisition times, which are individually visible. The UI shows age as of response generation, date/time in UTC, quality and native value. Retrieval may be fresh (`live` enum / “Fresh retrieval” label), but observations are not presented as real-time.

### Availability, cache and performance

- `available`: usable observation selected.
- `no_scene`: no candidate intersects the neighborhood/time window.
- `quality_filtered`: candidates exist, none have accepted product quality and product-specific processing metadata.
- `no_usable_pixels`: nominal candidates exist, no valid local cells survive; L3 cannot distinguish all QA losses from missing coverage.
- `not_configured`, `authentication_error`, `configuration_error`, `provider_error`, `timeout`, `busy`: operational states, not scientific absence.

Overall `availability` is `complete`, `partial` or `none`; overall provider `live` means a fresh successful query even if all products are scientifically absent. One product's failure does not remove the others. A malformed observation produces a safe error without leaking provider text.

| Setting | Default / range |
| --- | --- |
| `SATELLITE_LOOKBACK_HOURS` | 72 / 1–168 |
| `SATELLITE_RADIUS_KM` | 10 / 1–25 km |
| `SATELLITE_CACHE_TTL_SECONDS` | 3,600 / 0–7,200 seconds |
| `SATELLITE_TIMEOUT_SECONDS` | 25 / 1–60 seconds per batch |

The shared bounded cache includes rounded location, exact window, radius and product set. Valid empty results are cached; batches containing operational failures are not. Cached responses retain source retrieval/acquisition times. SDK RPC/socket timeout is 10 seconds, compute retries are disabled, and the service includes a one-second allowance above the batch deadline. A single timed-out RPC may continue briefly in its reserved thread; no additional batch is queued behind it. Ground cards load separately. Latencies are measured, not estimated; the authenticated latency remains unknown until the live gate runs.

### Scientific limits and manual gate

Satellite atmospheric columns are regional context and are not equivalent to ground-level pollutant concentrations. Aerosol Index is dimensionless and is not particulate mass concentration or AQI. No conversion to µg/m³, no numeric comparison with ground NO₂, no source attribution and no forecasting are performed. Clouds, orbit/revisit gaps, partial footprints, ingestion delays, quality masks and uncertain near-surface sensitivity constrain interpretation. Absence does not establish clean air.

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --satellite-only --gate --json
```

This reports query/configuration status, each product's native value/unit, acquisition time/age, QA, provenance, latency and cache result. Genuine missing coverage passes the query gate; auth/config failures do not. Exit 2 means the satellite gate remains unmet. Debug `--lookback-hours 168` or `--at` must be recorded separately; default coordinates/windows must not be changed to manufacture positive results. CI never runs this tool and blocks SDK/HTTP network transports in unit tests.


### Verified metadata semantics (12 September 2026)

The [authenticated scene inspection](verification/phase1c-metadata-diagnostic.json) found uppercase `NOMINAL` for all 11 Gurugram NRTI candidates. NO₂ processing metadata was `NRTI-processing product`; CO/Aerosol Index processing metadata was `Nominal`. No consulted property was missing. The catalog's generic title-case Nominal/Degraded descriptions do not enumerate those actual source strings correctly.

The [official NO₂ Product User Manual v4.5.0](https://sentiwiki.copernicus.eu/__attachments/1673595/S5P-KNMI-L2-0021-MA%20-%20Sentinel-5P%20Level%202%20Product%20User%20Manual%20Nitrogendioxide%202025-4.5.0.pdf?inst-v=48f4e5b4-21dc-4a3c-b262-15dde094f6bd), pp. 37 and 143, defines the NRTI processing label as a production mode and the uppercase nominal quality enum. The predicate therefore accepts these exact source strings, retaining the catalog-described Nominal forms for compatibility. It does not treat arbitrary processing strings as usable or admit the NO₂ processing mode for other products. Pixel masks, QA thresholds, outlier cutoff, geometry, time window and reducer are unchanged. See [the final diagnostic](PHASE_1C_VERIFICATION.md#final-metadata-diagnostic--12-september-2026).
