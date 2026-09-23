# Spatial command center and simulated handoff

AirshedOS helps an officer locate a reported event, inspect evidence, read Google's operational forecast, and record a manual review state. It does not establish source causality or dispatch an authority. No custom prediction model is deployed; Phase 2D remains `MODEL_NOT_ACCEPTED`.

## Officer workflow

The desktop workspace has a case queue, selected-workflow Google map, and case detail. Below 1100 px these stack vertically; all critical map facts remain available as text. Select a case using its queue button. Expand citizen interpretation, corroboration explanations, environmental readings and provenance as needed. Forecast outlook remains separate from corroboration. Review controls modify workflow state only.

A successful citizen corroboration creates an immutable evidence snapshot automatically. It includes the original structured report, Gemini interpretation/provenance, corroboration rules/support, provider context and Google forecast. Selecting a case reads that snapshot; marker clicks never refetch environmental sources. Review updates retain the map viewport and snapshot reference.

Submission time is known; image capture time is unknown. Provider observation time, fire acquisition time, satellite scene acquisition time, forecast-valid time, retrieval time and review action time retain their different meanings. Backend dates retain UTC offsets; the UI labels IST. Expand existing source disclosures for provider/model/prompt/scene details.

## Review states and API

| Current state | Allowed next states |
|---|---|
| NEW | UNDER_REVIEW |
| UNDER_REVIEW | ACKNOWLEDGED, MONITORING, CLOSED_NO_ACTION |
| ACKNOWLEDGED | MONITORING, CLOSED_NO_ACTION |
| MONITORING | UNDER_REVIEW, ACKNOWLEDGED, CLOSED_NO_ACTION |
| CLOSED_NO_ACTION | None |

`GET /api/v1/review/cases` returns summaries sorted NEW, UNDER_REVIEW, ACKNOWLEDGED/MONITORING, CLOSED_NO_ACTION, then newest report submission first, then case ID as a deterministic tie-breaker. Fictional reference incidents and the coordinate probe are separate queue entries without invented citizen corroboration scores.

`GET /api/v1/review/cases/{case_id}` returns snapshot plus review metadata. `POST /api/v1/review/cases/{case_id}/review` accepts only `state` and `expected_revision`. Stale revisions and invalid transitions return 409; unknown/expired cases return 404; extra evidence fields are rejected with 422. There is no evidence-write endpoint. Deep copies isolate callers; a SHA-256 digest identifies the snapshot. It is an integrity aid, not a signed audit trail.

Cases are process-local, bounded to 64, and expire no later than the originating report's remaining TTL (default 30 minutes). Idle timers clear them; restart or oldest-case capacity eviction also removes them. Review never extends expiry. Duplicate insertion never overwrites a snapshot or resets review. Browser copies may remain visible until refreshed; an expired record cannot accept actions. Refresh queue/case to reconcile another tab's review. No database, identities, accounts, notes, enforcement, notification or routing exists. This is a local prototype, not a multi-worker production review service.

## Maps and credential setup

Use a **separate browser API key** in ignored root `.env`:

```ini
NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY=your_dedicated_browser_key
# Optional for a configured map style; local prototype defaults to DEMO_MAP_ID.
NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID=
```

Enable Maps JavaScript API in a billed Google Cloud project. Restrict this key to that API (`maps-backend.googleapis.com`) and website referrers `http://localhost:3000/*` and `http://127.0.0.1:3000/*`. The key is intentionally present in compiled browser code; never reuse the server AQ/Weather key. Next configuration reads only these two public fields from root `.env`; Compose passes them as web build arguments. Rebuild after changes. Existing server credentials remain backend-only. The scanner permits only the exact configured browser key in `.next` output and continues to reject backend keys, unknown keys, source-file keys and artifact leaks.

The SDK loads once per page, with Maps/Advanced Markers. Google's `DEMO_MAP_ID` is for this local prototype; production would need its own map ID, deployment-origin restrictions and billing review. See Google's [loader documentation](https://developers.google.com/maps/documentation/javascript/load-maps-js-api), [Advanced Markers setup](https://developers.google.com/maps/documentation/javascript/advanced-markers/start), and [key security guidance](https://developers.google.com/maps/api-security-best-practices).

| Marker | Meaning |
|---|---|
| R — REPORT | Selected citizen report coordinate, including explicitly synthetic inputs |
| D — INCIDENT | Fictional demo incident coordinate |
| F — ACTIVE FIRE DETECTION | Nearby NASA FIRMS satellite detection, **not a pollution source finding** |
| P — PROBE | Selected Gurugram coordinate; no event inferred |

The case viewport fits its report and at most 50 returned nearby fire detections (existing provider distance order). No fires means center on the report at local scale. Full returned fire coordinates/acquisition times remain in the text panel. Fire selection exposes acquisition time, distance, instrument, confidence, FRP and provenance. Satellite atmospheric products and Google AQ are not plotted as physical street-level sensors. No heatmap, plume, route or imagery overlay exists.

Markers have letter labels and accessible names, keyboard selection, and equivalent text buttons. Queue buttons use selected-state semantics and focus outlines. Google Maps load/auth/network timeout failures produce a bounded unavailable panel; queue, evidence and review remain usable. Raw credential-bearing errors are never copied into UI messages. CI mocks the SDK boundary and blocks Maps networking; it needs no browser key.

## Prototype jurisdiction

The maintained configuration `apps/api/app/review/jurisdiction_areas.json` contains small interior lookup rectangles, **not authoritative state boundaries**:

| Prototype area | Latitude interior | Longitude interior | Displayed state |
|---|---|---|---|
| Gurugram | 28.40–28.53 | 76.97–77.07 | Haryana |
| Central Delhi | 28.58–28.68 | 77.16–77.25 | Delhi |
| Noida | 28.52–28.60 | 77.35–77.41 | Uttar Pradesh |

Outside these interiors, on edges, or in overlapping configuration, jurisdiction is Unknown. Every result is explicitly non-authoritative and informational; verify administrative jurisdiction independently. No LLM city inference, external GIS ingestion or authority integration is implied. Fictional incidents retain their labeled fixture jurisdiction.

## Three-to-five-minute demo

1. Open the command center; select the Gurugram probe and show current provider statuses.
2. In citizen intake choose **Use synthetic sample image**, or select a pollution photo. The sample supplies empty coordinate fields with Gurugram and is explicitly labeled synthetic.
3. Interpret the image with Gemini, then explicitly corroborate. The case enters the queue and becomes selected on the map.
4. Show the report and any returned fire detections, with the causality limitation. Genuine zero detections are valid.
5. Expand corroboration and provenance; show Google's separate 6/12/24-hour outlook.
6. Begin review, then mark monitoring or acknowledge. Support, evidence and forecast remain unchanged.
7. Optionally continue into the Phase 3B simulated handoff below; no authority is contacted.

The synthetic image is the pre-existing Phase 2A evaluation asset, copied with provenance into `apps/web/public/demo`. The input is fictional; Gemini and environmental requests still use configured services with their individual status labels. The original Phase 1A fixture incident and simulated actions remain separately labeled and unchanged.

## Prospective forecast snapshot protocol

From the repository root with the local API running:

```sh
apps/api/.venv/bin/python apps/api/scripts/forecast_snapshot.py record --lat 28.4595 --lng 77.0266
apps/api/.venv/bin/python apps/api/scripts/forecast_snapshot.py match --snapshot data/forecast-evaluation/record-TIMESTAMP.json
```

Outputs are one-shot, gitignored local JSON under `data/forecast-evaluation`. A `prospective_google_forecast_v1` snapshot records coordinate, record/retrieval time, unknown issuance time (`null`), hourly forecast-valid times, native PM2.5 units, CPCB index if returned and provenance. A separate `prospective_google_observation_match_v1` file pairs later observed Google AQ only after both retrieval and snapshot recording, at an exactly matching coordinate and valid timestamp, preserving observation/retrieval time, units and provider identity. No interpolation, historical forecast reconstruction, scores, polling or database is added. Unavailable or unmatched data produces no result file. Matching may require a later manual run and is not a phase-completion dependency. Google observations and forecasts share an ecosystem; these pairs are not independent ground truth and make no accuracy claim.


## Phase 3B simulated cross-jurisdiction workflow

Use **Use synthetic cross-jurisdiction demo** in citizen intake for the fictional border-area coordinate 28.52, 77.08, interpret, corroborate and begin review. The point has Unknown jurisdiction in the narrow prototype lookup; boundary ownership is unverified. Its synthetic label does not relabel configured provider responses as synthetic.

In **Hand off case**, explicitly choose source control room, a different destination (Delhi/Haryana/Uttar Pradesh), and a controlled reason. Generate a frozen PollutionEvent packet, inspect its assessment/Google outlook/provenance, mark ready and send the **simulated handoff**. Switch **Source cases → Incoming handoffs**, select the demo recipient and open the packet. Opening is read-only. Receive, inspect integrity, then accept, reject or return for review. Both views share consistent state and append-only ephemeral audit. Returned packets can be readied/resend by the source without modifying their frozen evidence. To reflect a later case review state, generate a new version instead.

Incoming selection shows the frozen report coordinate on the existing map and in text. Keyboard controls, stacked mobile layout and map-failure fallback all apply. No boundary overlay, route animation or automatic destination selection is added. Expand frozen evidence/provenance, audit history or JSON preview; **Export PollutionEvent JSON** downloads the exact SHA-256-verified bytes.

Handoff is independent from case review: ACCEPTED does not acknowledge the case, change support or refresh providers. The store holds 128 packets for one hour independently of source-case TTL and is lost on restart/eviction. Each audit is bounded to 128 entries; its actors are generic labels, not authenticated officers. All views explicitly say simulated/prototype. See [the complete contract and limitations](INTEROPERABILITY.md) and [verification](PHASE_3B_VERIFICATION.md). Import, authoritative boundaries and real authority integration are deferred; no Phase 3C work is included.


## Finalization navigation and preparation (Phase 3C)

The first-load guide links provider context → synthetic image/interpretation → officer review and simulated handoff. After successful corroboration, an explicit link returns to the selected officer case. Gemini interpretation and deterministic analysis are labelled at their own panels; the legacy fictional forecast carries its own illustrative badge. Provider, uncertainty and provenance disclosures remain available.

Follow the single [demo checklist](DEMO_CHECKLIST.md) for preparation, clean restart, live rehearsal, failure narration and independent export verification. No new seed/reset endpoint, saved fake interpretation or alternate live workflow was added. Exact provider states are never replaced for presentation. See [final verification](PHASE_3C_VERIFICATION.md) for measured latency and failure drills.
