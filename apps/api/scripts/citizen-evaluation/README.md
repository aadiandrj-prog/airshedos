# Synthetic citizen-evidence smoke-test set

Five local AI-generated images, created on 2026-09-13 with the built-in OpenAI image-generation tool. These depict no actual reported incidents or identified people/companies. They are evaluation assets, never live citizen evidence. No externally scraped photography is included.

The deliberately small local subset follows Phase 2A's allowance for a small maintained image set plus mocked CI. This is **not** the aspirational 20–30-image representative dataset or a scientific benchmark. Five real Vertex image requests cover open burning, an ambiguous distant plume, construction dust, cloud/fog with misleading citizen text, and an irrelevant clean indoor scene. Ten critical category contracts (including traffic haze, clean street, night and blur) are tested with fakes in CI; fake outcomes are **not** evidence of live classification accuracy. A real diverse, independently reviewed evaluation set remains necessary before operational use.

`manifest.json` records each scene prompt, accepted broad interpretation classes, synthetic origin and description. The model never receives the filename, expected category or generation prompt. Coordinates 28.4595, 77.0266 are fixed test inputs, **not image geolocation**. No environmental requests run during this evaluation.

All five images were visually inspected. Exact generation prompt template (one separate call per scene):

> Use case: photorealistic-natural. Create ONE 1024x1024 synthetic evaluation photo for a software multimodal interpretation smoke-test, not an actual event record. [scene prompt from manifest] Natural unpolished smartphone framing. No text, labels, logos, watermarks, faces, identifying signs or plates. Do not dramatize pollution. The file will be documented as AI-generated.

The tool returned 1254×1254 PNGs, retained without modification here. These images were generated for this project’s testing, without an external photograph source. They are not asserted to be public-domain photographs. Their original generator metadata remains in these fixture files; upload preprocessing strips metadata before Vertex inference.

Run manually from the repository root:

```sh
apps/api/.venv/bin/python apps/api/scripts/evaluate_citizen_evidence.py \
  --output docs/verification/phase2a-gemini-live.json
```

This uses the actual multipart endpoint in an in-process HTTP test client with **real Vertex ADC calls**. It never runs in CI. Only sanitized interpretation/provenance, statuses, timings and expected broad categories are recorded. It does not save image payloads, citizen input or raw model responses in the verification artifact. An explicit directory argument accepts another manifest with the same shape. Exit 1 means at least one interpretation failed; broad-category mismatches are reported separately, not hidden or treated as a calibrated accuracy score.
