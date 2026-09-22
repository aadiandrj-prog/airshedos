# Simulated jurisdiction interoperability — Phase 3B

A reviewed case can be packaged, manually sent to a prototype jurisdiction inbox, received and accepted/rejected/returned without changing its scientific assessment. Everything happens inside one AirshedOS process. **No government system receives a packet.** No official agency integration, authenticated officer identity or durable/compliance-grade audit is claimed.

## PollutionEvent v1

The strict Pydantic `PollutionEvent` in `apps/api/app/handoff/models.py` is published as `components.schemas.PollutionEvent` in `apps/api/openapi.json`. Frontend types are generated from OpenAPI. `schema_version` is required and must be `pollution_event_v1`; missing/future versions, extra fields and malformed structures are rejected. This is a typed export contract, not a schema registry or generic integration framework.

| Fields | Meaning |
|---|---|
| `schema_version`, `event_id`, `case_id`, `event_version` | Contract identity, stable `PE-<case_id>` identity, source assessment/case and frozen packet version |
| `created_at`, `updated_at`, `handoff_created_at` | Equal UTC creation times; frozen payload is never updated in place |
| `origin_jurisdiction`, `origin_system`, `origin_case_id`, `origin_basis` | Explicit manual prototype control room, AirshedOS system and source case; not a verified ownership claim |
| `destination_jurisdiction`, `handoff_reason`, `simulated` | Explicit enum destination, officer-selected rationale and required `true` simulation marker |
| `location` | Report coordinate, unknown coordinate accuracy, existing non-authoritative jurisdiction lookup result |
| `possible_event_type`, `event_family`, `corroboration_support`, `advisory_next_step` | Original tentative interpretation and deterministic assessment; no new scientific score |
| `review_state`, `source_review_revision` | Source workflow state at packet creation; independent of subsequent case/handoff changes |
| `temporal` | Report submission, unknown image capture time, submission-proxy environmental reference and context-generation time |
| `evidence` | Structured Gemini interpretation/confidence, report/synthetic flag, source states, rule summaries/references, normalized AQ/weather/FIRMS/satellite and source snapshot hash |
| `forecast` | Nullable Google provider outlook, state, 6/12/24-hour summaries, actual hourly forecast-valid times, retrieval time and provenance; issuance time remains unknown (`null`) |
| `limitations`, `handoff_id` | Assessment and interoperability limitations, unique packet/handoff association |

Gemini model/version/prompt provenance, evidence source IDs, observation/retrieval times, satellite collection/band/image identities and native units survive the snapshot. FIRMS means satellite fire detection, not a pollution-source finding. Satellite atmospheric columns remain distinct from ground concentrations. Google forecast is still provider context, never an independent corroboration vote or an AirshedOS-trained prediction.

The allowlisted packet omits image bytes/base64/URLs, citizen free-text description, raw provider responses, arbitrary rule debug-input dictionaries, configuration flags and latency diagnostics. Unavailable sources retain their status and null/empty semantics; missing providers do not prevent handoff. All backend times retain timezone-aware UTC; UI times are labelled IST. No image capture time is invented.

### Versions and immutable bytes

Each generation creates a new handoff ID and frozen event version. Versions use a process-wide monotonically increasing integer: versions for a case increase but can have gaps when other cases generate packets. This prevents reuse after capacity eviction without an unbounded per-case index. Restart discards the process-local cases/packets and version counter. Event IDs are stable for a case; handoff IDs identify individual generated packets.

A source review change cannot update an existing packet. To reflect a later review state, refresh the source case and generate another packet. Retrying a returned packet resends the same version and bytes, with new audit entries. Payload `updated_at` remains its creation time; handoff action times belong to the envelope/audit.

Canonical v1 encoding is precisely:

```python
json.dumps(event.model_dump(mode="json"), sort_keys=True,
           separators=(",", ":"), ensure_ascii=False,
           allow_nan=False).encode("utf-8")
```

All keys are recursively sorted; array order is preserved, whitespace separators are removed, Unicode is UTF-8, non-finite numbers are rejected and there is no trailing newline. Datetime strings and finite numeric representations use the validated Pydantic/Python JSON representation. This is **not a claim of RFC 8785/JCS compliance**. Receivers should hash the exact exported bytes; parsing and reserializing in another runtime can change float/date/string representations and therefore the digest.

SHA-256 is stored as lowercase hex in the handoff envelope (`payload_hash`), alongside mutable `revision`, lifecycle state and append-only audit. The hash is deliberately outside the payload to avoid self-referential hashing. Reads recompute and compare normalized packet bytes, stored canonical bytes and digest. Any mismatch blocks every transition and export, including acceptance. The browser independently hashes downloaded bytes before offering the JSON download. The preview is pretty-printed for reading and is not the exported serialization.

Hash equality demonstrates unchanged bytes relative to the expected hash. It provides **no identity, authenticity, signatures, non-repudiation or protection against an attacker replacing both bytes and expected hash**. There is no PKI or authenticated delivery.

## Jurisdictions and fictional boundary-area scenario

Supported control-room enums are `DELHI`, `HARYANA`, `UTTAR_PRADESH`. Source and destination are explicitly chosen and must differ. No agency recipient is inferred. A manually selected source control room is distinct from `jurisdiction_at_location`; Unknown location ownership remains Unknown.

The existing maintained interior rectangles in `apps/api/app/review/jurisdiction_areas.json` are retained and explicitly **non-authoritative**. They are not state polygons. Points outside them, on edges or in overlapping lookup areas are Unknown. Phase 3B does not infer boundary distances or automatically suggest/select a destination.

The [official South West Delhi district description](https://dmsouthwest.delhi.gov.in/about-district/) confirms regional adjacency to Haryana/Gurgaon. It does not establish exact point ownership or provide a verified machine-readable boundary used by this implementation. No authoritative polygon dataset was verified and integrated within this narrow phase; retaining honestly limited prototype coverage is preferable to fabricated precision.

**Use synthetic cross-jurisdiction demo** loads the existing synthetic image at **28.52, 77.08**, a fictional Delhi–Haryana border-area scenario. The exact boundary/ownership is explicitly unverified; the prototype lookup returns Unknown. No real company or alleged real incident is named. Gemini/environmental services may be live/cached while the citizen input remains synthetic. The illustrative legacy demo incident remains separate.

Controlled reasons: `CROSS_BORDER_EVENT`, `DOWNWIND_IMPACT`, `JURISDICTION_MISMATCH`, `SHARED_CORRIDOR_CONTEXT`, `MANUAL_OFFICER_HANDOFF`. These are officer-selected workflow rationales, not model findings, plume evidence or proof of cross-border impact. No freeform officer note is added.

## Lifecycle and API

A source case must be UNDER_REVIEW, ACKNOWLEDGED or MONITORING, with a matching expected review revision. NEW and CLOSED_NO_ACTION cannot generate packets. Handoff states do not change case review state.

| Current handoff state | Allowed next states |
|---|---|
| DRAFT | READY |
| READY | SENT_SIMULATED |
| SENT_SIMULATED | RECEIVED |
| RECEIVED | ACCEPTED, REJECTED, RETURNED_FOR_REVIEW |
| RETURNED_FOR_REVIEW | READY |
| ACCEPTED / REJECTED | None |

Every transition requires `expected_revision`; invalid/stale transitions return 409. Invalid enums/extra fields return 422; absent/expired records return 404. Source controls offer ready/send and destination controls offer receive/accept/reject/return. This UI separation is not authorization—there are deliberately no accounts or access-control claims.

| Endpoint | Behavior |
|---|---|
| `POST /api/v1/review/cases/{case_id}/handoffs` | Body: `origin_jurisdiction`, `destination_jurisdiction`, `reason`, `expected_case_revision`; returns new DRAFT record (201) |
| `GET /api/v1/handoffs?case_id=…` | Source packet summaries, including unsent drafts |
| `GET /api/v1/handoffs?destination=DELHI` | Destination summaries; only packets with at least one simulated send |
| `GET /api/v1/handoffs/{id}` | Frozen payload, recomputed integrity, lifecycle and audit |
| `POST /api/v1/handoffs/{id}/transition` | Body: `state`, `expected_revision`; shared validated state machine |
| `GET /api/v1/handoffs/{id}/export` | Exact canonical JSON bytes, `X-Payload-SHA256`, no-store and suggested filename |

Both filters may be combined; unfiltered listing returns all process-local summaries. Lists sort newest simulated-send time (creation time for drafts) first, then ID. Opening/listing is read-only and does not imply receipt. Manual receive is separate from manual acceptance. A returned packet stays visible in the destination history while the source readies/resends it. Resending updates the latest `sent_at` and appends history, without changing payload.

The filename is `pollution-event-<event_id>-v<event_version>.json`. The browser checks against the record's expected digest; API consumers can use the response hash header. **Import is deferred**: there is no upload/import endpoint and no claim of verified externally supplied provenance. Export is the interoperability demonstration.

## Ephemeral audit and storage

One bounded in-memory repository holds **128 handoffs**, each with a **3,600-second TTL** from creation, independent of source-case expiry. Reads/actions do not extend TTL. Oldest-created entries are evicted at capacity; timers purge idle expired records; shutdown/restart removes everything. Source expiry blocks new packet generation but does not delete an already frozen handoff before its own expiry. Exported files are user-owned copies outside server TTL.

Each successful creation/action appends a record with sequence, UTC timestamp, action/state, handoff revision, event version, source/destination, hash and generic `source_control_room`/`destination_control_room` actor. Reads, invalid actions and export do not append. Prior entries are never edited; returned-packet retries append. The prototype caps audit history at **128 entries per handoff** and rejects further actions instead of truncating history. Generate a new packet from an active case if necessary.

Repository operations are synchronous between awaits on the single application event loop, with revision checks and deep-copy isolation. This is not a multi-worker delivery system. There is no network dispatch, queue, durable database or delivery guarantee. The UI says **Ephemeral prototype audit trail** and displays expiry.

## UI and manual verification

The existing three-area command center gains **Source cases / Incoming handoffs**. Begin review, select explicit origin/destination/reason, generate and inspect the packet, mark ready, then **Send simulated handoff**. Choose the demo destination inbox, open, verify integrity, receive, then accept/reject/return. Expand evidence/provenance or audit and export JSON.

Selecting an incoming record centers the existing map on its frozen report coordinate. Marker and text identify SIMULATED HANDOFF REPORT; no route arc, boundary overlay, AQ sensor or spatial causal claim is added. Map failure leaves the complete textual handoff usable. Controls remain keyboard accessible; mobile uses the existing stacked layout. A late inbox request cannot override a newly selected source workflow.

Destination actions only read/update the handoff repository. They do not rerun Gemini, AQ, Weather, FIRMS, Earth Engine or forecast, and cannot write case evidence, support, forecast or provenance. The snapshot may therefore become stale; this is visible and intentional.

With local configured Docker services running, the optional developer-only gate is:

```sh
node apps/web/scripts/verify-handoff.mjs
```

It submits the synthetic image, corroborates with configured providers, begins review, sends HARYANA → DELHI, receives/accepts, verifies unchanged case/payload/audit prefix, confirms no provider reruns, validates exported SHA-256 and checks live map/mobile behavior. It writes sanitized results, canonical export and screenshots under gitignored `data/verification`. It is never run in CI. CI uses sanitized fixtures and mocked Maps/providers only. See [Phase 3B verification](PHASE_3B_VERIFICATION.md).

## Before any real deployment — requirements only

Real integration would require authoritative jurisdiction boundaries; identity/authentication; RBAC; a durable database; a durable audit log; an official destination registry; secure transport; receiving-system authentication; privacy/data-governance review; retry/delivery guarantees; and legal/operational agreements. None is implemented or implied by this prototype.

Phase 2D remains **MODEL_NOT_ACCEPTED**; no custom model is deployed. Phase 3B added no ML, scientific QA changes, source attribution, alerts or authority dispatch. Phase 3C's limited receiving-contract and demo review is recorded below; production requirements remain separately scoped.


## Independent receiver review (Phase 3C)

The review found the existing exported v1 payload sufficient; no schema fields or semantics changed. IDs are sender-scoped references, not authenticated identities. `event_version` can have gaps; handoff `revision` and mutable audit/hash belong to the envelope, not the frozen payload. Empty FIRMS arrays mean a successful zero-detection query; null means unavailable. Missing satellite observations retain per-product availability. Nullable forecast and source-native units must be handled without substitutions. Report submission, unknown image capture, observation, retrieval, forecast-valid and packet-creation times are distinct. A manual jurisdiction code/reason is not an official recipient or scientific finding.

The standalone [JSON Schema](contracts/pollution_event_v1.schema.json) is generated directly from the backend serialization contract by `apps/api/scripts/export_openapi.py`. Tests compare it with the model; CI checks regeneration. It uses local `$defs` references and no remote registry. The schema requires the complete exported representation, including null/default fields emitted by the backend.

`apps/api/scripts/receive_pollution_event.py` is an independent offline example: copy it and the schema, install `jsonschema==4.26.0`, then run it with `--schema PATH --sha256 EXPECTED_SENDER_DIGEST`. It imports no AirshedOS application code, performs no network calls, limits input to 2 MiB, rejects malformed/duplicate-key/non-finite JSON, validates required schema fields and aware timestamps, checks key cross-field source/review references, verifies exact bytes and emits a minimal summary. It does not parse an untrusted schema supplied inside the packet. The schema file is trusted receiver configuration.

JSON Schema does not encode every Pydantic cross-field/scientific validator. The example independently checks top-level frozen timestamps, source/report relationships, review state and integer versions; it does not rerun scientific rules, validate the truth of provider claims or establish provenance authenticity. Matching bytes/schema is therefore a receiving-contract check, not permission to act on a real allegation. Do not calculate the expected hash from the received file itself and call that trusted comparison. Export/validation is not an import capability.

See [the practical commands](DEMO_CHECKLIST.md) and [final verification](PHASE_3C_VERIFICATION.md). Optional import and all production identity/durability requirements remain deferred.
