"use client";
import { useCallback, useEffect, useState } from "react";
import { authorityRequest, type Evidence, type Fragment, type Workspace } from "../../lib/authority-client";
import { displayedTime } from "../../lib/resident-client";
import type { components } from "../../lib/api-schema";
import { useDeadline } from "./expiry";

function Content({ fragment }: { fragment: Fragment }) {
  const p = fragment.payload;
  if (!p || fragment.state !== "AVAILABLE") return <p>Content unavailable: {fragment.state.replaceAll("_", " ").toLowerCase()}.</p>;
  if (p.kind === "retained_assessment_v1") {
    const rule = p as { support_level: string; reason_code: string; explanation: string; rules: { rule_id: string; verdict: string; summary: string }[] };
    return <><h4>Deterministic advisory support: {rule.support_level}</h4><p>{rule.reason_code}</p><p>{rule.explanation}</p>
      <p>Checklist category, not a calibrated probability or a legal decision. Saved inputs exclude Google AQ/weather/forecast.</p>
      <ul>{rule.rules.map((r) => <li key={r.rule_id}>{r.verdict}: {r.summary}</li>)}</ul></>;
  }
  if (p.kind === "gemini_normalized_v1") {
    const image = p.interpretation as components["schemas"]["GeminiEvidenceAnalysis"];
    return <><h4>Gemini interpretation — advisory</h4><p>{image.event_type.replaceAll("_", " ")} · Ordinal visual confidence: {image.event_type_confidence}</p>
      <ul>{image.visual_observations.map((s) => <li key={s}>{s}</li>)}</ul><p>Uncertainty: {image.uncertainty_reasons.join(" ")}</p>
      <p>Model: {String(p.model)} · Returned model version: {typeof p.model_version === "string" ? p.model_version : "not supplied"} · Prompt: {String(p.prompt_version)}. An image cannot establish a source, pollutant concentration or violation.</p></>;
  }
  if (p.kind === "firms_normalized_v1") return <p>Dataset {String(p.dataset)}: {String(p.detection_count)} detections. Nearest distance {p.nearest_distance_km == null ? "unavailable" : `${p.nearest_distance_km} km`}. An absence of detections does not clear the report.</p>;
  if (p.kind === "sentinel_normalized_v1") return <p>{String(p.product)}: {String(p.column_mol_m2)} mol/m²; {String(p.valid_pixel_count)} valid pixels. Regional column context cannot establish ground concentration or a local source.</p>;
  if (p.kind === "firms_normalized_v2") {
    const fires = p.observations as components["schemas"]["FireObservation"][];
    return <><p>{fires.length} retained nearby detections (snapshot capped at 500); dataset {String(p.dataset)}. An absence of detections does not clear the report.</p>
      <ul>{fires.slice(0,5).map((f) => <li key={f.source_id}>Acquired {displayedTime(f.observed_at)} · {f.distance_from_query_km.toFixed(2)} km · VIIRS confidence category {f.confidence ?? "unknown"}; not a probability.</li>)}</ul></>;
  }
  if (p.kind === "sentinel_normalized_v2") {
    const context = p.context as components["schemas"]["SatelliteAtmosphericContext"];
    return <><p>Regional satellite context cannot prove a local source or legal violation.</p><ul>{context.products.map((item) => <li key={item.product}>
      {item.product}: {item.observation ? <>{item.observation.value} {item.observation.unit}, acquired {displayedTime(item.observation.observed_at)}, {item.observation.quality.valid_grid_cells} valid grid cells. Collection {item.observation.collection}.</> : item.availability}</li>)}</ul></>;
  }
  return <p>Permitted normalized source record. Use its source/time/policy metadata; no visual or legal conclusion is inferred.</p>;
}
export function EvidencePane({ unitId, caseId, versions }: { unitId: string; caseId: string; versions: Workspace["evidence_versions"] }) {
  const [selected, setSelected] = useState(""); const [data, setData] = useState<Evidence | null>(null); const [error, setError] = useState("");
  const version = selected || versions[0]?.id;
  const load = useCallback(async () => version ? (await authorityRequest(unitId,`cases/${caseId}/evidence/${version}`)).json() as Promise<Evidence> : null, [unitId, caseId, version]);
  useEffect(() => { let active = true; void load().then((value) => { if (active) { setData(value); setError(""); } }).catch((failure) => { if (active) { setData(null); setError(failure.message); } }); return () => { active = false; }; }, [load]);
  const deadline = data?.fragments.filter((f) => f.state === "AVAILABLE").map((f) => f.expires_at).sort()[0];
  useDeadline(deadline, () => { setData(null); void load().then(setData).catch(() => setError("Expired content was removed. Reload the case for its current redacted evidence.")); });
  return <section className="case-panel" id="evidence-versions"><h2>Evidence versions</h2><p>Evidence is frozen per version. Refresh adds a version and does not replace a human decision. Expiry/redaction can remove protected content.</p>
    {!versions.length ? <p>No evidence version yet. Analysis pending; manual review remains available.</p> : <>
      <label>Evidence version<select aria-label="Evidence version" value={version} onChange={(e) => { setData(null); setSelected(e.target.value); }}>{versions.map((v) => <option key={v.id} value={v.id}>Version {v.version} · {displayedTime(v.created_at)}</option>)}</select></label>
      {error && <p role="alert">{error}</p>}{!data && !error && <p role="status">Loading permitted evidence…</p>}
      {data?.id === version && <><p>Input policy: {data.input_policy}. Version created {displayedTime(data.created_at)}.</p>
        {data.fragments.map((f) => <article className="resident-card" key={f.id}><h3>{f.source}</h3>
          <p>Observed: {f.observed_at ? displayedTime(f.observed_at) : "Unknown / not applicable"}. Retrieved: {displayedTime(f.retrieved_at)}. Expires: {displayedTime(f.expires_at)}.</p>
          <p>Attribution: {f.attribution}. Policy: {f.policy_version}.</p><Content fragment={f} /></article>)}</>}
    </>}
  </section>;
}
