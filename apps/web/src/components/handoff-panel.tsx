"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Badge, EmptyState } from "./ui";
import { api, type HandoffRecord, type HandoffSummary, type HandoffJurisdiction, type HandoffReason, type HandoffState, type OfficerCase } from "@/lib/api";

const jurisdictions: HandoffJurisdiction[] = ["DELHI", "HARYANA", "UTTAR_PRADESH"];
const reasons: HandoffReason[] = ["CROSS_BORDER_EVENT", "DOWNWIND_IMPACT", "JURISDICTION_MISMATCH", "SHARED_CORRIDOR_CONTEXT", "MANUAL_OFFICER_HANDOFF"];
const label = (s: string) => s.replaceAll("_", " ");
const time = (s: string) => new Date(s).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST";
const actionLabels: Record<HandoffState, string> = {
  DRAFT: "Draft", READY: "Mark packet ready", SENT_SIMULATED: "Send simulated handoff",
  RECEIVED: "Receive in demo inbox", ACCEPTED: "Accept handoff", REJECTED: "Reject handoff",
  RETURNED_FOR_REVIEW: "Return for review",
};
const errorMessage = (cause: unknown) => cause instanceof Error ? cause.message : "Handoff unavailable. Please retry.";

export function HandoffDetail({ record, side, onChange }: {
  record: HandoffRecord; side: "source" | "destination"; onChange: (record: HandoffRecord) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const event = record.payload;
  const permitted = record.allowed_transitions.filter(s => side === "source" ? ["READY", "SENT_SIMULATED"].includes(s) : !["READY", "SENT_SIMULATED"].includes(s));
  async function act(state: HandoffState) {
    if (busy) return;
    setBusy(true); setError("");
    try { onChange(await api.transitionHandoff(record.id, state, record.revision)); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError("");
    try { onChange(await api.handoff(record.id)); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function download() {
    setBusy(true); setError("");
    try {
      const bytes = await api.exportHandoff(record.id);
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))).map(v => v.toString(16).padStart(2, "0")).join("");
      if (digest !== record.payload_hash) throw new Error("Integrity mismatch. Export blocked.");
      const url = URL.createObjectURL(new Blob([bytes], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url;
      link.download = `pollution-event-${event.event_id}-v${event.event_version}.json`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <section className="handoff-detail" aria-label="Handoff review panel" aria-busy={busy}>
    <Badge tone="caution">SIMULATED HANDOFF · PROTOTYPE RECIPIENT</Badge>
    {event.evidence.is_synthetic && <p className="synthetic-label">SYNTHETIC CROSS-JURISDICTION DEMO · Not a real allegation.</p>}
    <h3>Jurisdiction handoff</h3>
    <div className="handoff-route"><div><span>From</span><strong>{label(event.origin_jurisdiction).toLowerCase()}</strong></div><span aria-hidden="true">→</span><div><span>To</span><strong>{label(event.destination_jurisdiction).toLowerCase()}</strong></div></div>
    <dl className="case-facts">
      <div><dt>Reason selected by officer</dt><dd>{label(event.handoff_reason)}</dd></div>
      <div><dt>Possible event</dt><dd>{label(event.possible_event_type)}</dd></div>
      <div><dt>Corroboration</dt><dd>{event.corroboration_support} support</dd></div>
      <div><dt>Frozen case review state</dt><dd>{label(event.review_state)} · revision {event.source_review_revision}</dd></div>
      <div><dt>Location</dt><dd>{event.location.latitude}, {event.location.longitude} · {event.location.jurisdiction_at_location.state} (prototype lookup)</dd></div>
      <div><dt>Handoff state</dt><dd><strong>{label(record.state)}</strong> · revision {record.revision}</dd></div>
      <div><dt>Integrity</dt><dd role="status">INTEGRITY {record.integrity}</dd></div>
    </dl>
    <p>Google AQ forecast: {event.forecast ? `${event.forecast.status} · ${event.forecast.summaries.map(s => `${s.horizon_hours}h ${label(s.outlook)}`).join(" · ")}` : "Unavailable in frozen packet"}. Separate from corroboration.</p>
    <p className="source-caveat">Origin is a manually selected prototype control room, not verified jurisdiction ownership. No government system receives this packet. Receipt does not refresh evidence.</p>
    {error && <p role="alert">{error}</p>}
    <div className="review-actions">{permitted.map(state => <button type="button" key={state} disabled={busy || record.integrity !== "VERIFIED"} onClick={() => void act(state)}>{actionLabels[state]}</button>)}</div>
    <button type="button" className="secondary" disabled={busy} onClick={() => void refresh()}>Refresh handoff</button>{" "}
    <button type="button" className="secondary" disabled={busy || record.integrity !== "VERIFIED"} onClick={() => void download()}>Export PollutionEvent JSON</button>
    <details><summary>View packet details</summary><p>{label(event.origin_jurisdiction)} → {label(event.destination_jurisdiction)}</p><p>{event.schema_version} · event version {event.event_version}</p><p>Created {time(record.created_at)} · Simulated send {record.sent_at ? time(record.sent_at) : "Not sent"}</p><p>Packet {record.id} · revision {record.revision}</p></details>
    <details><summary>Frozen evidence & provenance</summary>
      <p>Submitted {time(event.temporal.report_submitted_at)} · image capture time unknown.</p>
      <p>Gemini: {event.evidence.gemini.provenance.model} · prompt {event.evidence.gemini.provenance.prompt_version} · ordinal confidence {event.evidence.gemini.event_type_confidence}.</p>
      <p>FIRMS: {event.evidence.fires == null ? "Unavailable" : `${event.evidence.fires.length} detections`}. Satellite: {event.evidence.satellite == null ? "Unavailable" : event.evidence.satellite.map(p => `${p.product}: ${p.availability}`).join("; ")}.</p>
      <ul>{event.evidence.source_statuses.map(s => <li key={s.provider}>{s.provider}: {s.status} · retrieved {s.retrieved_at ? time(s.retrieved_at) : "Unknown"}</li>)}</ul>
      <p>SHA-256: {record.payload_hash}</p><p>Hash checks content integrity, not identity or authenticity.</p>
      <ul>{event.limitations.map((s, i) => <li key={i}>{s}</li>)}</ul>
      <details><summary>PollutionEvent JSON preview</summary><pre>{JSON.stringify(event, null, 2)}</pre></details>
    </details>
    <details><summary>Ephemeral prototype audit trail ({record.audit.length})</summary>
      <p>{record.audit_notice}</p><ol>{record.audit.map(a => <li key={a.sequence}>{time(a.timestamp)} · {label(a.action)} · {a.actor} · version {a.event_version} · revision {a.handoff_revision}<br />{label(a.origin_jurisdiction)} → {label(a.destination_jurisdiction)}<br />SHA-256 {a.payload_hash}</li>)}</ol>
    </details>
    <p className="source-caveat">Expires {time(record.expires_at)} independently of the source case. Restart or capacity eviction also removes the packet.</p>
  </section>;
}

export function HandoffComposer({ selectedCase }: { selectedCase: OfficerCase }) {
  const [origin, setOrigin] = useState<HandoffJurisdiction | "">("");
  const [destination, setDestination] = useState<HandoffJurisdiction | "">("");
  const [reason, setReason] = useState<HandoffReason>("MANUAL_OFFICER_HANDOFF");
  const [record, setRecord] = useState<HandoffRecord | null>(null);
  const [records, setRecords] = useState<HandoffSummary[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api.handoffs({ case_id: selectedCase.id }).then(items => { if (active) setRecords(items); }).catch(() => { if (active) setError("Source handoff list unavailable."); });
    return () => { active = false; };
  }, [selectedCase.id, record]);
  const eligible = ["UNDER_REVIEW", "ACKNOWLEDGED", "MONITORING"].includes(selectedCase.review.state);
  async function create(event: FormEvent) {
    event.preventDefault(); if (!origin || !destination || busy) return;
    setBusy(true); setError("");
    try { setRecord(await api.createHandoff(selectedCase.id, { origin_jurisdiction: origin, destination_jurisdiction: destination, reason, expected_case_revision: selectedCase.review.revision })); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function open(id: string) {
    setBusy(true); setError("");
    try { setRecord(await api.handoff(id)); }
    catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <section className="handoff-composer" aria-label="Hand off case">
    <h4>Hand off case</h4><p>Explicit manual action · simulated transfer only</p>
    {!eligible && <p>Begin case review to generate a packet. Closed cases cannot be handed off.</p>}
    <form onSubmit={create} aria-label="Create simulated handoff"><fieldset disabled={busy || !eligible}>
      <label>Source control room<select required value={origin} onChange={e => setOrigin(e.target.value as HandoffJurisdiction)}><option value="">Choose prototype origin</option>{jurisdictions.map(j => <option key={j} value={j}>{label(j)}</option>)}</select></label>
      <label>Destination jurisdiction<select required value={destination} onChange={e => setDestination(e.target.value as HandoffJurisdiction)}><option value="">Choose prototype destination</option>{jurisdictions.map(j => <option key={j} value={j} disabled={j === origin}>{label(j)}</option>)}</select></label>
      <label>Handoff reason<select value={reason} onChange={e => setReason(e.target.value as HandoffReason)}>{reasons.map(r => <option key={r} value={r}>{label(r)}</option>)}</select></label>
      <p className="source-caveat">Reason is an officer-selected workflow rationale, not a scientific finding. Destination is never inferred automatically.</p>
      <button type="submit" disabled={!origin || !destination || origin === destination}>Generate frozen packet</button>
    </fieldset></form>
    {error && <p role="alert">{error}</p>}
    {records.length > 0 && <details><summary>Source handoffs ({records.length})</summary>{records.map(r => <button type="button" className="case-choice" key={r.id} disabled={busy} onClick={() => void open(r.id)}>Version {r.event_version} → {label(r.destination_jurisdiction)} · {label(r.state)}</button>)}</details>}
    {record && <HandoffDetail key={record.id} record={record} side="source" onChange={setRecord} />}
  </section>;
}

export function HandoffInbox({ selected, onSelect }: { selected: HandoffRecord | null; onSelect: (record: HandoffRecord) => void }) {
  const [destination, setDestination] = useState<HandoffJurisdiction>("DELHI");
  const [items, setItems] = useState<HandoffSummary[]>([]);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const selection = useRef(0);
  useEffect(() => () => { ++selection.current; }, []);
  useEffect(() => {
    let active = true;
    api.handoffs({ destination }).then(result => { if (active) { setItems(result); setError(""); } }).catch(() => { if (active) setError("Demo inbox unavailable. Refresh to retry."); });
    return () => { active = false; };
  }, [destination, refresh, selected]);
  async function open(id: string) {
    const version = ++selection.current;
    try {
      const record = await api.handoff(id);
      if (version === selection.current) { onSelect(record); setError(""); }
    } catch (cause) { if (version === selection.current) setError(errorMessage(cause)); }
  }
  return <section aria-label="Incoming handoffs" className="handoff-inbox">
    <h4>Incoming handoffs</h4><p>Demo recipients only. Opening does not acknowledge receipt.</p>
    <label>Demo recipient jurisdiction<select value={destination} onChange={e => { ++selection.current; setItems([]); setError(""); setDestination(e.target.value as HandoffJurisdiction); }}>{jurisdictions.map(j => <option key={j} value={j}>{label(j)}</option>)}</select></label>
    <button className="secondary" onClick={() => setRefresh(v => v + 1)}>Refresh inbox</button>
    {error && <p role="alert">{error}</p>}
    {!items.length && !error && <EmptyState title="No simulated handoffs for this destination.">Sent packets appear here for manual receipt and review. No authority is connected.</EmptyState>}
    {items.map(item => <button className="case-choice" key={item.id} aria-pressed={selected?.id === item.id} onClick={() => void open(item.id)}>
      <span className="tag demo">SIMULATED {item.is_synthetic && "· SYNTHETIC"}</span>
      <strong>{label(item.possible_event_type)} · {item.corroboration_support} support</strong>
      <span>{label(item.origin_jurisdiction)} → {label(item.destination_jurisdiction)}</span>
      <span>{label(item.reason)} · {label(item.state)}</span>
      <small>Sent {item.sent_at ? time(item.sent_at) : "Not sent"} · Integrity {item.integrity}</small>
    </button>)}
  </section>;
}
