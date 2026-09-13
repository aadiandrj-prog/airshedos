# Corroboration checklist v1

Phase 2B joins server-owned visual interpretation to normalized environmental context. It is an inspectable operational policy, **not a calibrated scientific classifier**. A support category does not establish event truth, source causality, legal responsibility, emissions, a violation or health impact. No LLM call, probability, score, incident creation or dispatch occurs here.

## Event families

| Family | Visual event types |
| --- | --- |
| COMBUSTION | open_burning, fire_or_combustion, industrial_smoke |
| DUST | construction_dust, road_dust |
| ATMOSPHERIC_HAZE | haze_or_smog |
| TRAFFIC | vehicular_emissions |
| NONE_OR_UNCERTAIN | no_visible_pollution, uncertain, other |

## Rules and source semantics

Every response includes all seven rules, their verdicts, reasons, normalized inputs, source references, observation/retrieval times, observation ages, signed observation-minus-submission offsets and evaluation time. Model and environmental provenance retain their subtype fields. The full normalized environmental context is included once; no raw provider bodies or images are included.

| Rule ID | Exact policy |
| --- | --- |
| `CITIZEN.VISUAL.v1` | For a mapped positive event family, HIGH ordinal interpretation → SUPPORTS; MEDIUM → WEAKLY_SUPPORTS; LOW → NEUTRAL. NONE_OR_UNCERTAIN → NEUTRAL. Citizen text never independently contributes. Unknown photo acquisition time stays null. |
| `AQ.CPCB.v1` | Requires fresh available `ind_cpcb` in [0,500]. Missing index → NEUTRAL; outside range → UNAVAILABLE. No UAQI conversion or concentration-derived AQI. DUST requires dominant `pm10`; COMBUSTION/HAZE/TRAFFIC allow `pm10` or `pm25`. Missing/non-particulate dominant code → NEUTRAL. NONE_OR_UNCERTAIN stays NEUTRAL even with poor regional AQ. Within an applicable particulate context: <=100 NEUTRAL; >100 and <=200 WEAKLY_SUPPORTS; >200 SUPPORTS (regional context only). |
| `FIRMS.PROXIMITY.v1` | COMBUSTION only; other families NOT_APPLICABLE. Recompute spherical distance from detection coordinates to report. Only VIIRS nominal/high (`n`/`h`) and age <=24h are eligible. <=5km and age <=6h SUPPORTS; otherwise <=15km and <=24h WEAKLY_SUPPORTS. >15–25km regional-only NEUTRAL; >25km too distant NEUTRAL. Low/missing confidence NEUTRAL. Zero detections NEUTRAL. All detections stale → STALE. Failed provider → UNAVAILABLE. Each candidate's distance, age, confidence and exclusion reason is exposed. Select the nearest strong candidate, or nearest eligible weak candidate. |
| `WEATHER.WIND.v1` | Fresh weather alone adds no pollution support. For COMBUSTION, use the nearest eligible nominal/high fire <=15km and <=6h old; never choose a farther candidate merely because it aligns. Fire/weather timestamps must be <=1h apart. Wind speed must be known and >=1m/s; separation >=0.1km. Compare transport direction `(wind_from_degrees+180)%360` with initial great-circle bearing fire→report. Shortest circular angular difference <=45° → WEAKLY_SUPPORTS, conditional consistency only. Otherwise NEUTRAL. Other families NOT_APPLICABLE after weather availability/age checks. Missing weather UNAVAILABLE; missing fire means neutral wind context. |
| `SATELLITE.NO2.v1` | Fresh usable observation NEUTRAL/context only; retain `mol/m²`, timestamp, image, band, collection and QA. Never score as a ground concentration. |
| `SATELLITE.CO.v1` | Same context-only policy and native `mol/m²`. |
| `SATELLITE.AEROSOL_INDEX.v1` | Same context-only policy, dimensionless. No arbitrary UVAI cutoff or support points. |

The [official Google index table](https://developers.google.com/maps/documentation/air-quality/laqis) identifies `ind_cpcb`, the 0–500 range and the 100/200 category boundaries. The application uses those boundaries for **current particulate context**, never a historical anomaly or source label. Requiring a particulate dominant code is an intentionally conservative MVP choice; non-dominant particulate elevations do not score.

[NASA FIRMS documents VIIRS confidence categories](https://www.earthdata.nasa.gov/data/tools/firms/faq) as quality indicators with limitations, not incident probabilities. The selected distance and age bands are **AirshedOS operational heuristics**, not NASA-recommended attribution distances or validated sensitivity thresholds. Small, obscured, short-lived or off-overpass fires can be missed. A hotspot need not correspond to the photographed event.

[Google Weather defines direction as where wind comes from](https://developers.google.com/maps/documentation/weather/reference/rest/v1/Wind). The provider's km/h or mph speed is converted to m/s only for the calm-wind guard; the original value and unit remain exposed. The engine also accepts an already normalized m/s measurement. Unknown units cannot pass the guard. Bearings use spherical geometry, with angular difference `abs((transport-bearing+180)%360-180)`. These are directional checks, not travel-time estimates or plume models. One local current wind observation cannot establish historical transport or source causality.

The [official AER_AI catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_AER_AI) describes positive values as UV-absorbing aerosol context that can include dust and smoke. That does not provide a calibrated local incident threshold or distinguish their sources. **All three satellite products remain context-only in this phase.** Existing collection selection, native units and scientific QA are unchanged; see [DATA_SOURCES](DATA_SOURCES.md#earth-engine--sentinel-5p).

## Time and staleness

`temporal_basis=submission_time_proxy`. Photo capture time is unknown. AQ/weather/FIRMS preserve current-service lookup, including when an older submission time is supplied. Satellite queries the existing 72-hour window ending at the exact submission timestamp, with the unchanged 10km neighborhood. No historical Google lookup, EXIF timestamp inference or interpolation is introduced.

Age is recomputed from each observation timestamp to the environmental context's generation timestamp; cached age fields are not trusted. AQ max age: 2h. Weather: 1h. FIRMS: 24h (strong support/eligible wind candidate <=6h). Satellite: 24h for corroboration context; 24–72h observations remain in the response but are STALE. Exact age limits are inclusive. Missing/failed/QA-filtered satellite products are UNAVAILABLE, not zero. More than 300 seconds in the future is invalid evidence; small clock skew is explicitly exposed as a signed age and never used to infer capture time. FIRMS future candidates are excluded individually.

A source can report LIVE/CACHED transport while its rule is STALE or NEUTRAL. Those are different questions. `source_summary` keeps both. Unsupported and missing sources stay visible.

## Aggregation, in order

1. **CONFLICTING / REVIEW** only for an actual structured visual inconsistency: the explicit observation “No clear smoke, flame or dust-like feature visible” together with a positive smoke/flame/dust flag. This is an internal interpretation review guard, **not cross-provider evidence of a physical contradiction**. Regional pollution versus a clean-looking photo is not a conflict. Phase 2B has no defensible cross-provider contradiction predicate given unknown photo time and spatial footprints.
2. **INSUFFICIENT** when the family is NONE_OR_UNCERTAIN or visual support is not positive. Next step REVIEW, except no_visible_pollution → NO_ACTION_FROM_CURRENT_EVIDENCE. Poor regional AQ does not prove an event in that image.
3. **INSUFFICIENT / REVIEW** when every environmental rule is UNAVAILABLE, STALE or NOT_APPLICABLE. A visual interpretation alone with all environmental providers failed is not corroboration.
4. **STRONG / FIELD_VERIFICATION** only for HIGH visual support AND the strong FIRMS rule. This is stricter than allowing poor regional AQ alone to produce STRONG.
5. **MODERATE / FIELD_VERIFICATION** for positive HIGH/MEDIUM visual support and positive AQ or FIRMS support.
6. **WEAK / MONITOR** for positive visual support with available fresh context but no independent AQ/FIRMS support.

Wind is conditional on FIRMS and cannot count as an additional independent pollution stream. Satellite never raises a category. Neither alone can elevate the aggregate. `contributing_rule_ids` lists positive checklist rules, including conditional wind when present; `aggregation_explanation` explains the actual category. There are no hidden numeric weights.

The pure engine uses the context generation time rather than reading a wall clock. Identical normalized records, context and settings yield identical output, including a stable content-derived assessment ID. Repeating a network lookup can change generated time/cache metadata and therefore the ID while leaving rule verdicts unchanged. Human text changes do not change the assessment.

## Configuration

All fields below are under `app/corroboration/settings.py`. Environment names use prefix `CORROBORATION_` and the uppercase field name. `.env.example` and Compose expose all defaults. Invalid ranges or unordered bands fail configuration validation rather than silently changing scientific policy.

| Field | Default | Meaning |
| --- | --- | --- |
| report_ttl_seconds | 1800 | 30 minutes from successful interpretation storage; maximum 3600 |
| report_max_entries | 256 | LRU bound; maximum 1024 |
| aq_max_age_hours | 2 | AQ age limit |
| weather_max_age_hours | 1 | Weather age limit |
| fires_max_age_hours | 24 | Recent fire limit |
| fires_strong_age_hours | 6 | Strong fire / wind candidate age limit |
| satellite_max_age_hours | 24 | Satellite context staleness, not a retrieval/QA change |
| fire_very_near_km | 5 | Strong-distance band |
| fire_near_km | 15 | Weak-distance / wind candidate band |
| fire_regional_km | 25 | Regional-only band, matches default provider search radius |
| wind_tolerance_degrees | 45 | Alignment tolerance |
| wind_min_speed_mps | 1 | Calm-wind exclusion |
| wind_fire_max_time_gap_hours | 1 | Weather/fire temporal comparison limit |
| future_tolerance_seconds | 300 | Maximum accepted small timestamp skew |

AQ boundaries, particulate applicability, accepted VIIRS categories and aggregation are versioned code policy, not end-user tuning knobs. Increasing corroboration distances cannot retrieve detections beyond the independently configured provider search radius.

## Storage and limitations

The server keeps only CitizenReport metadata (including submitted description), GeminiEvidenceAnalysis and CitizenVisualSignal/provenance. The in-memory repository deep-copies records, enforces a fixed TTL and LRU capacity, removes expired records on timers even without later traffic, and clears on application shutdown/restart. Lookups do not extend TTL. It runs on the application's single event loop/worker. No images, media references, analyses received from the browser, disk database, assessment cache or second environmental cache are used.

The endpoint validates existence/expiry before beginning the lookup; an accepted in-flight lookup may finish after its report expires. Missing/expired/evicted/restarted reports all return the same clear 404 and never trigger Gemini automatically. The browser's Clear action removes its local presentation; retained server metadata still expires by TTL. No accounts, access control or durable multi-worker history are added. Existing loopback-only prototype deployment remains appropriate; public operation requires a separate access and quota design.

These rules need future domain review and a properly labeled, time/location-verified dataset before any scientific performance claim. The synthetic live test proves transport and transparent joining only, not precision, recall, accuracy or event truth.
