# One repeatable demo journey

Use the synthetic boundary-area journey below. It demonstrates live services around fictional input and a simulated workflow. Do not switch silently to fixture outputs when services fail. The legacy Phase 1A incident is preserved as a clearly labelled reference, not a second live journey.

## Before the demo

- Use the generated `apps/web/public/demo/open-burning.png` fixture. Its provenance is in the adjacent README; no private citizen media, faces or number plates are required.
- Start Docker Desktop. Check root ignored `.env` without displaying its values: server AQ/Weather key, FIRMS key, shared Google project, Gemini model/location and EE project. Confirm backend ADC is valid and the cloud project/APIs have access. OpenAQ is not needed for this demo.
- Maps needs the separate browser key restricted to Maps JavaScript API and the actual origin. Local supported origins are `http://localhost:3000/*` and `http://127.0.0.1:3000/*`. Rebuild after changing public frontend configuration.
- Start the verified local services from the repository root:

```sh
EARTH_ENGINE_ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json" \
  docker compose -p airshedos-phase1a -f docker-compose.yml \
  -f docker-compose.earth-engine.yml up --build -d --wait
```

- For a **known clean start**, restart the local API and reload the browser. This deliberately clears **all process-local reports, cases, handoffs, fixture action state and provider caches**; it does not touch `.env`, ADC, code, historical datasets or model artifacts. Perform this **before** warming caches. Do not reset in the middle of a demonstration. There is no public reset endpoint or hidden seeded interpretation.

```sh
docker compose -p airshedos-phase1a restart api
apps/api/.venv/bin/python apps/api/scripts/demo_preflight.py
```

- Wait for health/readiness to pass if the API is still restarting. Then optionally warm genuine provider caches at the synthetic coordinate:

```sh
apps/api/.venv/bin/python apps/api/scripts/demo_preflight.py --live \
  --output data/verification/demo-preflight.json
```

The read-only preflight reports PASS/WARN/FAIL without credentials. It checks API `/health` and `/ready`, frontend, synthetic fixture, runtime ground-provider configuration, local Gemini/EE/Maps configuration presence and Docker detectability. `--live` performs real ground/satellite/forecast queries. A configured project/key is **not** proof of valid authentication. The final browser rehearsal verifies Gemini and Maps. WARN provider states must be narrated; HTTP/service failures are FAIL. Satellite can return a valid live/cached query with no usable scene. No QA thresholds change.

- Open `http://localhost:3000`, verify Maps appears and source states are understandable. Ensure no unrelated cases remain. Cache warmth does not fabricate readings or change source timestamps.

## During the demo — approximately 3–5 minutes of narration

1. Open the command center. Use **1 · Provider context** to show genuine source states, timestamps and limitations. Zero FIRMS detections or no usable satellite scene are valid.
2. Use **2 · Synthetic image & interpretation**, then **Use synthetic cross-jurisdiction demo**. Show the explicit synthetic label and coordinate **28.52, 77.08**. Exact jurisdiction ownership is unverified; the narrow lookup returns Unknown.
3. Click **Interpret image**. The real Gemini response is an **AI interpretation**, not confirmed pollution. Show uncertainty briefly.
4. Click **Corroborate with environmental data**. Explain that AirshedOS applies deterministic rules and retains missing-source limitations. Satellite retrieval can be slower; visible loading text explains the wait.
5. Use **Open the selected case** to return to the officer workspace. Show the report marker/text and relevant fire context, without causal claims.
6. Show the separate **Google Air Quality forecast**. Select 6/12/24 hours if useful. It is Google's outlook, not an AirshedOS-trained prediction or another independent evidence vote.
7. **Begin review**. Choose **HARYANA** as the prototype source control room, **DELHI** as destination and **CROSS BORDER EVENT** as the manual workflow reason. These choices do not assert verified location ownership or cross-border causality.
8. **Generate frozen packet**; inspect support, forecast and provenance. **Mark packet ready**, then **Send simulated handoff**.
9. Switch to **Incoming handoffs**, select the Delhi demo inbox and open the packet. Opening alone does not acknowledge receipt.
10. **Receive in demo inbox**, show **INTEGRITY VERIFIED**, then **Accept handoff**. The source assessment and forecast remain unchanged; no providers run again.
11. **Export PollutionEvent JSON**. Show that an independent system can validate the contract and exact bytes using the expected hash from the sender record.

For a developer rehearsal of this same flow with sanitized timing/verification artifacts:

```sh
node apps/web/scripts/verify-handoff.mjs --final
```

This includes a genuine Gemini/provider/Maps path and an isolated-process receiver check. It also measures a separately identified cached-corroboration diagnostic **after** the timed rehearsal; that diagnostic can add a second ephemeral assessment. Reset before a presentation if you ran this developer diagnostic. Outputs under gitignored `data/verification/phase3c-*` include exact export, results and desktop/mobile captures; no HAR, raw network URLs or credential-bearing console output is saved. Elapsed automation time is not a claim about a human's 3–5-minute narration.

Standalone verification with an expected digest copied from the sender's record:

```sh
apps/api/.venv/bin/python -I apps/api/scripts/receive_pollution_event.py \
  data/verification/phase3c-pollution-event.json --sha256 EXPECTED_SENDER_SHA256
```

Never calculate a fresh expected hash from a suspect file and call that integrity verification. SHA-256 does not authenticate the sender. This tool does not import a case or send anything externally.

## Backup plan — be explicit

| Failure | Honest continuation |
|---|---|
| Maps missing key/auth/network | Use report coordinates and text evidence. Review/handoff still work; say the map is unavailable |
| AQ/Weather/FIRMS/Sentinel/forecast unavailable | Show the actual unavailable state; continue with remaining evidence and limitations. Missing fire response is not zero detections |
| Gemini unavailable | Retry manually only if appropriate. Otherwise show a **previously captured synthetic rehearsal export/screenshot**, visibly described as saved demo material. Do not imply a live interpretation or inject fake output into the live flow |
| Entire network/backend unavailable | Explain the outage and show saved, dated synthetic verification material. Offline exported JSON can still be independently verified. No claim of live execution |
| Case expired | Previously created handoff can survive until its own expiry. To create a new packet, interpret/corroborate a fresh report; do not change timestamps |
| Integrity mismatch | Acceptance/export is blocked. Inspect the expected hash/source packet; do not bypass the check |
| Browser refresh | Process-local queue/inbox survives until TTL/restart. Reselect the item; the selected panel itself is browser-local |
| Backend restart | State and caches are gone. Explain temporary storage, rerun preflight and begin again |

## After the demo

No special action is required for the local prototype. Ephemeral records expire automatically; local screenshots/exports remain on your machine. No authority was notified. Any separately authorized public demo must follow its agreed exposure/stop policy in [deployment readiness](DEPLOYMENT.md).
