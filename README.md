# AirshedOS

**A clearer picture of a reported pollution event.**

AirshedOS helps an environmental control-room officer bring a citizen's report, nearby environmental readings, and an air-quality forecast into one place. It shows what the available evidence supports, what is uncertain, and what the officer can review next.

It is a working demonstration, not an official pollution reporting or emergency service.

## What can you do with it?

- **Look at local conditions.** See air quality, weather, nearby satellite fire detections, and regional atmospheric observations.
- **Submit a photo.** Google's Gemini AI describes visible signs that might be relevant. It also states uncertainty: a photo alone cannot prove pollution or identify its cause.
- **Check the supporting evidence.** AirshedOS applies a transparent checklist to the photo interpretation and environmental information. The result is a support category—not a probability or a confirmed finding.
- **See what may happen next.** Google's air-quality forecast provides separate outlooks for the next 6, 12, and 24 hours.
- **Review a case on a map.** Begin review, acknowledge a case, or mark it for monitoring.
- **Try a simulated handoff.** Send a frozen case summary between prototype jurisdiction inboxes and export it for another system to read. No real authority is contacted.

## Try the demo

The demonstration includes a clearly labeled fictional case and a synthetic sample image. You do not need a real citizen report.

1. Open the command center and look at the environmental conditions.
2. Under **Field evidence**, choose **Use synthetic cross-jurisdiction demo**.
3. Select **Interpret image**, then **Corroborate with environmental data** to check the supporting evidence.
4. Review the location, evidence, and Google forecast in the case panel.
5. Select **Begin review**. You can then try the simulated handoff and receiving inbox.

For the complete walkthrough and backup plan, see the [demo checklist](docs/DEMO_CHECKLIST.md).

**[Open the public demo](https://airshedos.vercel.app).** The website runs on Vercel and its backend runs on Render. The free demo server may take about a minute to wake. Some live sources can be unavailable; see the [hosting status and setup guide](docs/HOSTING.md) for current limitations. Neon is reserved for future use and does not store cases. [Local setup](docs/DEVELOPMENT.md) is also available.

## How to read the labels

| Label | What it means |
| --- | --- |
| Live / cached | A response from an external provider, either newly retrieved or reused from a recent request. Check its observation time. |
| AI interpretation | Gemini's interpretation of the image, with stated uncertainty. |
| Deterministic / rule-based | A result from AirshedOS's explicit evidence checklist. |
| Provider forecast | An outlook supplied by Google Air Quality, not a model trained by AirshedOS. |
| Synthetic / demo | An invented image or case used to demonstrate the workflow. |
| Simulated | A workflow inside this prototype; nothing has been sent to a government system. |
| Unavailable / not configured | That source could not provide information. AirshedOS does not invent a replacement reading. |

## Where does the information come from?

| Source | What it contributes |
| --- | --- |
| Citizen report and Gemini | A location, optional description, and AI interpretation of visible evidence |
| Google Air Quality | Current air-quality information and a separate forecast |
| Google Weather | Current weather context |
| NASA FIRMS | Nearby satellite fire detections |
| Sentinel-5P through Google Earth Engine | Recent usable regional atmospheric observations |

A fire detection does not establish pollution causality. Satellite atmospheric columns are not the same as ground-level pollutant concentrations. Expand the source details in the app to see where a value came from and when it was observed.

## Important limits

- **A person makes the decision.** AirshedOS does not confirm violations, issue enforcement decisions, or automatically dispatch anyone.
- **Forecasts are separate from evidence support.** Google current AQ and Google forecast are related outputs; the forecast does not count as another independent vote.
- **The map's jurisdiction labels are prototypes**, not official administrative boundaries.
- **Records are temporary and shared within the prototype.** Reports, review states, and handoffs can expire or disappear when the backend restarts. The requested empty Neon database will not change this behavior.
- **There are no user accounts or private case spaces.** Use the synthetic sample for demonstrations, and avoid images with faces, plates, or other identifying details. Submitted images and context are processed by Google for interpretation.
- **Sources may be unavailable.** Maps or one provider can fail while the rest of the review workflow remains usable.
- **No custom prediction model is deployed.** An internal model was evaluated and rejected because it underperformed the baseline. Its recorded result remains `MODEL_NOT_ACCEPTED`.

## Learn more

- [Simple system overview](docs/SYSTEM_OVERVIEW.md)
- [Officer workflow and map guide](docs/COMMAND_CENTER.md)
- [How evidence is assessed](docs/CORROBORATION_RULES.md)
- [How forecasts should be understood](docs/FORECASTING.md)
- [Simulated handoffs and exported case summaries](docs/INTEROPERABILITY.md)
- [Developer setup and checks](docs/DEVELOPMENT.md)
- [Vercel, Render, and Neon hosting](docs/HOSTING.md)
- [Architecture and technical documentation](docs/ARCHITECTURE.md)
- [Latest visual redesign and verification](docs/UI_REDESIGN.md)

The earlier [phase verification records](docs/PHASE_3C_VERIFICATION.md) document the checks performed at each stage; they are historical results, not a claim that providers are continuously available.
