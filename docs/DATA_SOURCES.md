# Environmental data sources — Phase 1B

Current implementations use backend-only HTTP requests. Test fixtures are synthetic and never imported into production. At delivery, the user chose to proceed without keys: **no provider was genuinely live-verified**. Missing credentials return `not_configured`, never a substitute reading. Configuration alone does not prove enabled APIs, billing, quota, coverage or successful access.

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

Role: nearby active-fire detections, **not confirmed pollution sources**. The [official area CSV API](https://firms.modaps.eosdis.nasa.gov/api/area/) is queried for `VIIRS_SNPP_NRT`, today and the previous UTC day (day range 2). Other FIRMS sensor streams and historical ingestion are outside this implementation. NASA currently announces that Suomi NPP product delivery will cease on 1 November 2026; this single-stream adapter will need a verified NOAA-20/21 transition before then. See the [official product notice](https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data).

A spherical bounding box covers the configured radius; antimeridian queries split into two boxes. Haversine distance filters each candidate to the actual circle. Results are deduplicated by source identifier and sorted nearest first. The small geometry utility handles poles and date-line crossings without heavyweight GIS dependencies.

Fields retained: detection coordinates; acquisition date plus zero-padded acquisition time interpreted as UTC; satellite/instrument; categorical VIIRS confidence (`l`, `n`, `h`); I4 brightness temperature in kelvin; fire radiative power in megawatts; distance in km; dataset-derived identifier; retrieval time and provenance. Confidence categories are not probabilities. See [VIIRS product attributes](https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data).

An HTTP 200 CSV containing only valid headers is a successful zero-detection result (`fires: []`). Invalid headers, including an HTTP 200 key-error message, produce `error` and `fires: null`. No location is changed to force a detection. Thermal detections can reflect different heat sources; clouds, overpass timing and coverage affect availability. Detections do not establish burning type, emissions, transport or causation.

FIRMS embeds its key in the request path. HTTPX/HTTPCore URL logging is suppressed and application logs never include that URL, raw responses or exception strings.

## Availability and time semantics

Every source independently reports `live`, `cached`, `unavailable`, `not_configured`, or `error`. `live` means a fresh successful provider response, not continuous monitoring or an observation made this instant. Observe the source's `observed_at` separately from `retrieved_at`; cached values retain both times. Provider outages and partial results are expected. A failed source does not erase another source's observations.

The optional `at` parameter is timezone-aware reference metadata only. This phase requests current conditions and recent FIRMS detections, not historical conditions for that timestamp. Sources have different observation/update cadences, and AirshedOS does not align them into a causal explanation or calculate a live risk score.

## Manual verification

From `apps/api` with the virtual environment activated:

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --json
```

The concise output reports actual request time, provider states, latency and representative values when available. JSON includes full normalized observations and provenance. No secrets are printed. This command is excluded from CI; automated tests clear credentials and reject real HTTP transport. See [Phase 1B verification](PHASE_1B_VERIFICATION.md) for the actual delivery result.

Earth Engine, satellite atmospheric products, Gemini, Vertex AI, historical storage, custom AQI conversion, evidence fusion scoring and pollution-source attribution remain future work.
