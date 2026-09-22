"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type HandoffRecord, type CaseSummary, type Incident, type OfficerCase, type ReviewState } from "@/lib/api";
import { HandoffComposer, HandoffDetail, HandoffInbox } from "./handoff-panel";
import { SpatialMap, type MapPoint } from "./spatial-map";
import { ForecastOutlook } from "./forecast-outlook";
import { AssessmentView } from "./corroboration-card";
import { CitizenInterpretation } from "./citizen-evidence-panel";
import { EnvironmentReadings } from "./environment-panel";
import { SatelliteReadings } from "./satellite-panel";

const label = (s: string) => s.replaceAll("_", " ");
const time = (s: string) => new Date(s).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST";
const actions: Record<ReviewState, string> = {
  NEW: "New", UNDER_REVIEW: "Begin review", ACKNOWLEDGED: "Acknowledge case",
  MONITORING: "Mark for monitoring", CLOSED_NO_ACTION: "Close with no action",
};

export function OfficerCommandCenter({ incident, selectedCase, onCase }: {
  incident: Incident | null; selectedCase: OfficerCase | null;
  onCase: (item: OfficerCase | null) => void;
}) {
  const [inbox, setInbox] = useState(false);
  const [incoming, setIncoming] = useState<HandoffRecord | null>(null);
  const activeIncoming = selectedCase ? null : incoming;
  const incomingEvent = activeIncoming?.payload;
  const [queue, setQueue] = useState<CaseSummary[]>([]);
  const [queueError, setQueueError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const selection = useRef(0);
  const currentCaseId = useRef(selectedCase?.id);
  useEffect(() => { currentCaseId.current = selectedCase?.id; }, [selectedCase?.id]);
  const [selectedMarker, setSelectedMarker] = useState("");
  const [probe, setProbe] = useState(false);
  const refreshQueue = useCallback(async () => {
    try { setQueue(await api.cases()); setQueueError(""); }
    catch { setQueueError("Case queue unavailable. Evidence intake and current conditions remain usable."); }
  }, []);
  useEffect(() => {
    let active = true;
    api.cases().then((items) => { if (active) { setQueue(items); setQueueError(""); } })
      .catch(() => { if (active) setQueueError("Case queue unavailable. Evidence intake remains usable."); });
    return () => { active = false; };
  }, [selectedCase]);
  const snapshot = selectedCase?.snapshot;
  const report = snapshot?.record.report;
  const context = snapshot?.assessment.environmental_context;
  const points = useMemo<MapPoint[]>(() => {
    if (incomingEvent) {
      const event = incomingEvent;
      return [{ id: event.event_id, role: "REPORT", lat: event.location.latitude, lng: event.location.longitude, label: `SIMULATED HANDOFF REPORT · ${event.event_id}` }];
    }
    if (snapshot) {
      const r = snapshot.record.report;
      const fires = snapshot.assessment.environmental_context.fires ?? [];
      return [{ id: "report:" + r.id, role: "REPORT", lat: r.latitude, lng: r.longitude,
        label: `${r.is_synthetic ? "SYNTHETIC " : ""}REPORT · ${r.id}` },
        ...fires.slice(0, 50).map((f) => ({ id: "fire:" + f.source_id, role: "FIRE_DETECTION" as const,
          lat: f.latitude, lng: f.longitude, label: `ACTIVE FIRE DETECTION · ${f.source_id}` }))];
    }
    if (probe || !incident) return [{ id: "probe", role: "PROBE", lat: 28.4595, lng: 77.0266, label: "PROBE · Gurugram coordinate" }];
    return [{ id: incident.id, role: "INCIDENT", lat: incident.latitude, lng: incident.longitude, label: "DEMO INCIDENT · " + incident.id }];
  }, [snapshot, incident, probe, incomingEvent]);
  const activeMarker = points.some((p) => p.id === selectedMarker) ? selectedMarker : points[0]?.id ?? "";
  const fire = context?.fires?.find((f) => "fire:" + f.source_id === activeMarker);
  const choose = async (id: string) => {
    const previousId = currentCaseId.current;
    const version = ++selection.current;
    setBusy(true); setActionError("");
    try {
      const item = await api.case(id);
      if (version === selection.current && currentCaseId.current === previousId) { onCase(item); setIncoming(null); setSelectedMarker(""); setProbe(false); }
    } catch { if (version === selection.current) setActionError("Case expired or unavailable. Refresh the queue or corroborate a new report."); }
    finally { if (version === selection.current) setBusy(false); }
  };
  const act = async (state: ReviewState) => {
    if (!selectedCase || busy) return;
    const selectedId = selectedCase.id;
    const version = ++selection.current;
    setBusy(true); setActionError("");
    try {
      const updated = await api.review(selectedId, state, selectedCase.review.revision);
      if (version === selection.current && currentCaseId.current === selectedId) {
        // Preserve the immutable snapshot reference: review does not refit or reload the map.
        onCase({ ...selectedCase, review: updated.review });
      }
    } catch (cause) { if (version === selection.current) setActionError(cause instanceof Error ? cause.message : "Review could not be saved."); }
    finally { if (version === selection.current) setBusy(false); }
  };
  const showReference = (isProbe: boolean) => {
    ++selection.current; setBusy(false); setActionError(""); onCase(null); setIncoming(null); setSelectedMarker(""); setProbe(isProbe);
  };
  return <section className="officer-workspace" aria-label="Officer command center">
    <div className="workspace-heading"><span className="eyebrow">SPATIAL COMMAND CENTER</span><h2>Locate. Review. Decide the next step.</h2>
      <p>Manual officer review · temporary state · no authority dispatch</p></div>
    <div className="officer-grid">
      <aside className="case-queue" aria-label="Case queue">
        <div className="review-actions" role="group" aria-label="Queue view"><button type="button" aria-pressed={!inbox} onClick={() => setInbox(false)}>Source cases</button><button type="button" aria-pressed={inbox} onClick={() => setInbox(true)}>Incoming handoffs</button></div>
        {inbox ? <HandoffInbox selected={activeIncoming} onSelect={item => { ++selection.current; setBusy(false); setActionError(""); onCase(null); setIncoming(item); setSelectedMarker(""); }} /> : <>
        <h3>Case queue</h3><p className="source-caveat">New → under review → acknowledged / monitoring → closed. Newest submission first within each group.</p>
        <button type="button" className="secondary" onClick={() => void refreshQueue()}>Refresh queue</button>
        {queueError && <p role="alert">{queueError}</p>}
        {!queue.length && !queueError && <p>No citizen assessments yet. Submit evidence and corroborate below.</p>}
        {queue.map((item) => <button type="button" className="case-choice" key={item.id} aria-pressed={selectedCase?.id === item.id} disabled={busy} onClick={() => void choose(item.id)}>
          <span className="tag">{item.is_synthetic ? "SYNTHETIC INPUT" : "CITIZEN REPORT"}</span>
          <strong>{label(item.event_type)}</strong><span>{item.jurisdiction.state} · prototype</span>
          <span>{item.support_level} corroboration</span><span>{label(item.review.state)}</span>
          <small>Submitted {time(item.submitted_at)}</small>
        </button>)}
        <h4>Reference workflows</h4>
        {incident && <button type="button" className="case-choice" aria-pressed={!selectedCase && !activeIncoming && !probe} onClick={() => showReference(false)}>
          <span className="tag demo">FICTIONAL DEMO</span><strong>{incident.title}</strong>
          <span>{incident.jurisdiction.state} · fixture</span><span>Illustrative support only · {incident.status}</span>
          <small>Scenario time {time(incident.detected_at)}</small>
        </button>}
        <button type="button" className="case-choice" aria-pressed={!selectedCase && !activeIncoming && probe} onClick={() => showReference(true)}>Gurugram coordinate probe<span>28.4595, 77.0266 · no reported event</span></button>
        </>}
      </aside>
      <SpatialMap points={points} selectedId={activeMarker} onSelect={setSelectedMarker} />
      <section className="officer-detail" aria-label="Selected case details" aria-busy={busy}>
        {actionError && <p role="alert">{actionError}</p>}
        {activeIncoming ? <HandoffDetail key={activeIncoming.id} record={activeIncoming} side="destination" onChange={item => setIncoming(previous => previous?.id === item.id ? { ...item, payload: previous.payload } : previous)} /> : selectedCase && snapshot && report ? <>
          <span className="tag">{report.is_synthetic ? "SYNTHETIC INPUT · PROVIDER CONTEXT" : "CITIZEN EVIDENCE · PROVIDER CONTEXT"}</span>
          <h3>{label(snapshot.assessment.event_type)}</h3>
          <dl className="case-facts"><div><dt>Reported location</dt><dd>{report.latitude}, {report.longitude}</dd></div>
            <div><dt>Submitted</dt><dd>{time(report.created_at)}</dd></div><div><dt>Image capture time</dt><dd>Unknown</dd></div>
            <div><dt>Jurisdiction</dt><dd>{snapshot.jurisdiction.state} · prototype</dd></div>
            <div><dt>Review state</dt><dd>{label(selectedCase.review.state)}</dd></div></dl>
          <p className="source-caveat">{snapshot.jurisdiction.note}</p>
          {report.is_synthetic && <p className="synthetic-label">This image is synthetic, not a real reported event. Each environmental source retains its own live/cached/unavailable status.</p>}
          <p className="source-caveat">FIRMS: {context?.fires == null ? "Unavailable response" : context.fires.length === 0 ? "No nearby active-fire detections returned" : `${context.fires.length} active-fire detections returned`}. Satellite fire detection does not establish pollution causality.</p>
          {fire && <section className="selected-fire" aria-label="Selected active fire detection">
            <h4>ACTIVE FIRE DETECTION</h4><p>Satellite fire detection; does not establish pollution causality.</p>
            <p>Acquired {time(fire.observed_at)} · {fire.distance_from_query_km.toFixed(2)} km from report</p>
            <p>{fire.satellite ?? "Satellite unspecified"} / {fire.instrument ?? "Instrument unspecified"} · Source confidence: {fire.confidence ?? "Not supplied"}</p>
            <p>FRP: {fire.fire_radiative_power ? `${fire.fire_radiative_power.value} ${fire.fire_radiative_power.unit}` : "Not supplied"}</p>
            <details><summary>Fire detection provenance</summary><p>{fire.source_id}</p><p>{fire.provenance.method} · {fire.provenance.note}</p><p>Retrieved {time(fire.retrieved_at)}</p></details>
          </section>}
          <details><summary>Citizen evidence & interpretation</summary>
            {report.description && <blockquote>{report.description} — unverified citizen text</blockquote>}
            <CitizenInterpretation analysis={snapshot.record.analysis} />
          </details>
          <details><summary>Corroboration · {snapshot.assessment.support_level} support · explanations & provenance</summary>
            <AssessmentView result={snapshot.assessment} reportId={report.id} showForecast={false} />
          </details>
          <ForecastOutlook context={snapshot.assessment.forecast_outlook ?? null} />
          <details><summary>Environmental context at assessment</summary>
            <EnvironmentReadings context={snapshot.assessment.environmental_context} />
            {context?.satellite ? <SatelliteReadings context={context.satellite} /> : <p>Satellite context unavailable.</p>}
            <p>FIRMS: {context?.fires == null ? "Unavailable response" : context.fires.length === 0 ? "No nearby active-fire detections returned" : `${context.fires.length} detections returned`}. Up to 50 nearby detections appear on the map.</p>
            <ul>{context?.fires?.map((f) => <li key={f.source_id}>ACTIVE FIRE DETECTION · {f.latitude}, {f.longitude} · acquired {time(f.observed_at)} · {f.distance_from_query_km.toFixed(2)} km · {f.source_id}</li>)}</ul>
          </details>
          <section className="officer-review" aria-label="Officer review controls">
            <h4>Officer review</h4><p>Workflow state only. Evidence, corroboration and provider forecast stay unchanged.</p>
            <strong>{label(selectedCase.review.state)}</strong>
            <div className="review-actions">{selectedCase.review.allowed_transitions.map((state) => <button type="button" key={state} disabled={busy} onClick={() => void act(state)}>{state === "UNDER_REVIEW" && selectedCase.review.state !== "NEW" ? "Return to review" : actions[state]}</button>)}</div>
            {selectedCase.review.action_at && <p>Review action at {time(selectedCase.review.action_at)}</p>}
            <p className="source-caveat">Expires {time(selectedCase.expires_at)}; also lost on restart or capacity eviction. No officer identity or dispatch is recorded.</p>
            <button type="button" className="secondary" disabled={busy} onClick={() => void choose(selectedCase.id)}>Refresh selected case</button>
            <details><summary>Snapshot integrity</summary><p>Evidence SHA-256: {snapshot.evidence_sha256}</p><p>Review revision {selectedCase.review.revision} · {selectedCase.id}</p></details>
          </section>
          <HandoffComposer key={selectedCase.id} selectedCase={selectedCase} />
        </> : probe || !incident ? <>
          <span className="tag">COORDINATE PROBE</span><h3>Gurugram</h3><p>28.4595, 77.0266</p>
          <p>No incident is inferred at this coordinate. AQ and satellite context are not physical sensor markers.</p><a href="#environment-context">View live environmental context below</a>
        </> : <>
          <span className="tag demo">FICTIONAL DEMO</span><h3>{incident.title}</h3><p>{incident.latitude}, {incident.longitude}</p>
          <p>{incident.jurisdiction.name}, {incident.jurisdiction.state} · demo fixture jurisdiction</p>
          <p>Scenario time {time(incident.detected_at)} · {label(incident.status)}</p>
          <p>All incident evidence and probabilities are illustrative. No live readings establish this fictional event.</p>
          <a href="#incident-command">Open the preserved demo evidence and actions</a>
          <p>For the officer review workflow, use the synthetic sample in citizen intake, interpret, then corroborate.</p>
        </>}
      </section>
    </div>
  </section>;
}
