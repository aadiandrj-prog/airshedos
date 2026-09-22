# AirshedOS — final prototype overview

AirshedOS helps an environmental control-room officer review a reported event, inspect supporting context and share a structured case packet with a **simulated** neighbouring jurisdiction.

1. **Input:** a photo, reported coordinate and optional citizen description. The demonstration uses a clearly labelled generated image and fictional Delhi–Haryana border-area scenario.
2. **AI interpretation:** Gemini describes visible evidence using structured fields and ordinal confidence. An image does not establish pollutant concentration, event truth or legal responsibility.
3. **Environmental context:** Google Air Quality, Google Weather, NASA FIRMS and Earth Engine Sentinel-5P retain provider identity, observation time, availability, native units and provenance. A missing satellite observation or zero fire detections is a valid result, not proof of no pollution.
4. **Corroboration:** transparent deterministic AirshedOS rules explain support and limitations. Satellite columns are regional context, not ground-level concentrations. No causal source attribution is made.
5. **Forecast outlook:** Google's operational AQ forecast supplies 6/12/24-hour summaries. It is not an AirshedOS-trained prediction and never increases corroboration support. Current Google AQ and forecast share a provider ecosystem.
6. **Officer operations:** a selected-case map, equivalent text details and explicit review states help an officer decide what to inspect next. Review cannot edit the evidence or forecast.
7. **Interoperability:** `pollution_event_v1` freezes the reviewed case with provenance. An officer manually chooses Delhi, Haryana or Uttar Pradesh as a prototype recipient, sends a simulated handoff, receives/accepts/rejects/returns it and exports SHA-256-verified JSON. No government system is contacted.

**Research result:** an internal custom operational forecast model was evaluated and rejected because it underperformed the naive baseline. Phase 2D remains **MODEL_NOT_ACCEPTED**. No custom model is deployed; the locked final test period remains unopened by model evaluation.

**Prototype limits:** cases, handoffs and audit are bounded process-local state, lost on restart/expiry. Jurisdiction lookup is explicitly non-authoritative. Hashing checks bytes, not identity. There are no accounts, persistent database, alerts, authority routing or production delivery guarantees. Maps/provider failures remain visible without disabling the rest of the workflow.

The Next.js/TypeScript browser uses OpenAPI-generated types from FastAPI. Server credentials stay backend-only; Google Maps uses a separate browser-restricted key. The current verified deployment is local Docker. Public deployment is prepared but unprovisioned and requires separate authorization and risk review.

[Diagram source](architecture.mmd) · [Demo checklist](DEMO_CHECKLIST.md) · [Receiver contract](INTEROPERABILITY.md) · [Deployment readiness](DEPLOYMENT.md) · [Final verification](PHASE_3C_VERIFICATION.md)
