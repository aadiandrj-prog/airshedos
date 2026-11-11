"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { authorityRequest, AuthorityFailure, reviewLabel, type Reviewer, type Workspace } from "../../lib/authority-client";
import { displayedTime, reporterStatusLabel, type Stage } from "../../lib/resident-client";
import { ActionForm } from "./action-form";
import { EvidencePane } from "./evidence";
import { ReviewerLiveContext } from "./live-context";
import { useDeadline } from "./expiry";

type Mutation = (path: string, body: object) => Promise<boolean>;
type Event = { revision: number; action: string; reason?: string | null; created_at: string; evidence_version_id?: string | null };
function Photo({ unitId, caseId, media }: { unitId: string; caseId: string; media: Stage | null }) {
  const [unavailable, setUnavailable] = useState(false);
  useDeadline(media?.expires_at, () => setUnavailable(true));
  if (!media) return <p>No photo attached.</p>;
  if (unavailable || media.state !== "ATTACHED") return <p>Private photo unavailable or expired.</p>;
  // No shared image optimizer, public object URL or permanent bearer URL.
  // eslint-disable-next-line @next/next/no-img-element
  return <figure><img src={`/api/app/v2/authority/units/${unitId}/cases/${caseId}/media/${media.id}`} alt="Private resident-supplied derivative" onError={() => setUnavailable(true)} /><figcaption>Cleaned private image. Expires {displayedTime(media.expires_at)}; capture time remains resident-declared or unknown.</figcaption></figure>;
}
function Publication({ request = false, disabled, closed = false, act }: { request?: boolean; disabled: boolean; closed?: boolean; act: Mutation }) {
  const [message, setMessage] = useState(""); const [status, setStatus] = useState("UPDATE_AVAILABLE"); const [preview, setPreview] = useState(false);
  return <form onSubmit={(e) => { e.preventDefault(); if (message.trim()) setPreview(true); }}>
    {!request && <label>Reporter status to publish<select aria-label="Reporter status to publish" value={status} disabled={disabled} onChange={(e) => { setStatus(e.target.value); setPreview(false); }}>
      {["IN_REVIEW","FOLLOW_UP_PLANNED","UPDATE_AVAILABLE","CLOSED"].map((s) => <option key={s} value={s} disabled={s === "CLOSED" && !closed}>{reporterStatusLabel(s)}</option>)}
    </select></label>}
    <label>{request ? "Reporter-visible question" : "Reporter-visible message"}<textarea required maxLength={1000} value={message} disabled={disabled}
      onChange={(e) => { setMessage(e.target.value); setPreview(false); }} /></label>
    <button type="submit" disabled={disabled || !message.trim() || !request && status === "CLOSED" && !closed}>{request ? "Preview information request" : "Preview resident update"}</button>
    {preview && <section className="resident-card" aria-label={request ? "Information request preview" : "Resident update preview"}>
      <h3>What the resident will see</h3><p>{request ? "Request for more information" : reporterStatusLabel(status)}</p><p>{message}</p>
      <p>Only this message is published. Internal notes and findings are separate. Do not claim government receipt or unverified remediation.</p>
      <button type="button" disabled={disabled} onClick={async () => {
        if (await act(request ? "information-requests" : "reporter-updates", request ? { prompt:message } : { status,message })) { setMessage(""); setPreview(false); }
      }}>{request ? "Publish information request" : "Publish update to reporter"}</button>
    </section>}
  </form>;
}
function FollowUp({ task, disabled, admin, reviewers, act }: { task: Workspace["field_follow_ups"][number]; disabled: boolean; admin: boolean; reviewers: Reviewer[]; act: Mutation }) {
  const [action, setAction] = useState("CLAIM"); const [member, setMember] = useState(""); const [reason, setReason] = useState("");
  return <article className="resident-card" aria-label={`Field follow-up ${task.id}`}><h3>Field follow-up · {task.state}</h3>
    <p>{task.instructions}</p><p>Assignee: {task.assigned_member_id ? reviewers.find((m) => m.id === task.assigned_member_id)?.label ?? "Unavailable member" : "Unassigned"}.</p>
    {task.outcome && <p>Recorded finding: {task.outcome}. This is a reviewer statement, not automatic proof that pollution ended.</p>}
    {task.completed_at && <p>Completed {displayedTime(task.completed_at)}.</p>}
    {["REQUESTED","ASSIGNED"].includes(task.state) && <form onSubmit={async (e) => { e.preventDefault();
      if (await act(`field-follow-ups/${task.id}/events`,{ action,reason,...(action === "ASSIGN" ? { membership_id:member } : {}) })) setReason(""); }}>
      <label>Follow-up action<select aria-label="Follow-up action" value={action} disabled={disabled} onChange={(e) => setAction(e.target.value)}>
        <option value="CLAIM">Claim for myself</option>{admin && <option value="ASSIGN">Assign to unit member</option>}
        {task.state === "ASSIGNED" && <option value="COMPLETE">Record completed finding</option>}<option value="CANCEL">Cancel follow-up</option>
      </select></label>
      {action === "ASSIGN" && <label>Follow-up assignee<select aria-label="Follow-up assignee" required value={member} disabled={disabled} onChange={(e) => setMember(e.target.value)}><option value="">Choose a unit member</option>{reviewers.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label>}
      <label>Follow-up reason or finding<textarea required maxLength={2000} disabled={disabled} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      <button type="submit" disabled={disabled}>Record follow-up action</button>
    </form>}
  </article>;
}
export function CaseDetail({ unitId, caseId, admin }: { unitId: string; caseId: string; admin: boolean }) {
  const [data, setData] = useState<Workspace | null>(null); const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false); const [blocked, setBlocked] = useState(false);
  const [target, setTarget] = useState(""); const [reason, setReason] = useState(""); const [assignee, setAssignee] = useState("");
  const [older, setOlder] = useState<Event[]>([]); const running = useRef(false); const alert = useRef<HTMLParagraphElement>(null);
  const load = useCallback(async () => (await authorityRequest(unitId,`cases/${caseId}`)).json() as Promise<Workspace>, [unitId,caseId]);
  useEffect(() => { let active = true; void Promise.all([load(), authorityRequest(unitId,"reviewers").then((r) => r.json())]).then(([value, roster]) => {
    if (active) { setData(value); setReviewers(roster); setError(""); }
  }).catch((failure) => { if (active) { setData(null); setError(failure.message); } }); return () => { active = false; }; }, [load,unitId]);
  useEffect(() => { if (error) alert.current?.focus(); }, [error]);
  useDeadline(data?.content_expires_at, () => { setData(null); setOlder([]); setReason(""); setBlocked(true); setError("Report content expired and has been removed from this view."); });
  async function reload() { try { setData(await load()); setBlocked(false); setError(""); setOlder([]); setMessage("Current case loaded. Review its history before repeating any uncertain action."); }
    catch (failure) { setData(null); setError((failure as Error).message); } }
  const act: Mutation = async (path, body) => {
    if (!data || blocked || running.current) return false;
    running.current = true; setBusy(true); setError(""); setMessage("");
    try { await authorityRequest(unitId,`cases/${caseId}/${path}`,{ method:"POST",body:JSON.stringify({ ...body,expected_revision:data.revision }) });
      setData(await load()); setOlder([]); setMessage("Action recorded. Current case reloaded."); return true;
    } catch (failure) { const f = failure as AuthorityFailure; setError(f.message); if (![422,429].includes(f.status)) setBlocked(true);
      if ([401,403,404].includes(f.status)) setData(null); return false;
    } finally { running.current = false; setBusy(false); }
  };
  const disabled = busy || blocked;
  return <div className="resident-stack">
    {error && <><p role="alert" ref={alert} tabIndex={-1}>{error}</p><Link href={`/sign-in?returnTo=${encodeURIComponent(`/authority/cases/${caseId}?unit=${unitId}`)}`}>Sign in again</Link></>}<p role="status">{busy ? "Recording action…" : message}</p>
    <button type="button" onClick={() => void reload()} disabled={busy}>Reload current case</button>
    {!data && !error && <p role="status">Loading permitted case…</p>}
    {data?.id === caseId && <>
      <div className="case-status"><span className="status-chip">{reviewLabel(data.review_state)}</span><span>Revision {data.revision} · Human review and analysis are separate</span></div>
      <nav className="case-section-nav" aria-label="Case sections"><a href="#declared-report">Report & evidence</a><a href="#review-actions">Review actions</a><a href="#resident-question">Resident reply</a><a href="#reporter-publication">Publish update</a><a href="#case-history">History & export</a></nav>
      <div className="case-workbench"><div className="case-evidence-column">
<section id="declared-report" className="case-panel"><h2>Resident-declared report</h2><p>{data.description}</p><dl><dt>Reported place</dt><dd>{data.reported_place ?? "Not supplied"}</dd>
        <dt>Declared concern</dt><dd>{data.declared_category.replaceAll("_", " ").toLowerCase()}</dd>
        <dt>Reported coordinates</dt><dd>{data.reported_location.latitude}, {data.reported_location.longitude} (unverified)</dd>
        <dt>Declared incident time</dt><dd>{data.declared_capture_at ? displayedTime(data.declared_capture_at) + " (resident-declared)" : "Unknown (not supplied)"}</dd>
        <dt>Accepted</dt><dd>{displayedTime(data.accepted_at)}</dd></dl><p>Displayed times use your browser timezone. Receipt and provider retrieval times are not verified incident time.</p>
        {data.withdrawn_at && <p>Resident withdrew this report. New processing is stopped; withdrawal does not prove the report false.</p>}
        <Photo key={data.media?.id ?? "none"} unitId={unitId} caseId={caseId} media={data.media} />
      </section>
<section id="processing" className="case-panel"><h2>Processing attempts</h2><p>Analysis is queued durably and runs in a separate worker. Interrupted jobs recover within a bounded retry policy; refresh creates a new evidence version.</p>
        <p>Analysis uses the original report photo and declared coordinates. Supplementary text/photos remain separate material for human review.</p>
        <ul>{data.processing_attempts.map((a,index) => <li key={`${a.request_id}-${a.stage}-${index}`}>{a.stage}: {a.state} {a.safe_reason && `(${a.safe_reason})`} · requested {displayedTime(a.request_created_at)}</li>)}</ul>
        <ActionForm label="Reason for evidence refresh" button="Queue evidence refresh" disabled={disabled || !!data.withdrawn_at || data.review_state === "CLOSED_NO_ACTION"} onSave={(text) => act("enrichments",{ reason:text })} />
      </section>
<EvidencePane unitId={unitId} caseId={caseId} versions={data.evidence_versions} />
<section className="case-panel"><h2>Environmental context</h2><ReviewerLiveContext unitId={unitId} caseId={caseId} /></section>
<section id="case-history" className="case-panel"><h2>Audit history</h2><p>Recent actions are bound to the evidence version visible when recorded. Earlier actions are paginated.</p>
        <ol>{[...(data.history as Event[]),...older].map((e) => <li key={e.revision}>Revision {e.revision} · {e.action} · {displayedTime(e.created_at)}{e.reason && <p>{e.reason}</p>}<small>Evidence version: {e.evidence_version_id ?? "None available"}</small></li>)}</ol>
        <button type="button" disabled={busy || data.history.length + older.length === 0} onClick={async () => {
          const entries = [...data.history as Event[],...older]; const before = Math.min(...entries.map((e) => e.revision));
          try { const entries: Event[] = await (await authorityRequest(unitId,`cases/${caseId}/history?before_revision=${before}`)).json(); setOlder((current) => [...current,...entries]); if (!entries.length) setMessage("No earlier audit actions."); } catch (failure) { setError((failure as Error).message); }
        }}>Load earlier audit actions</button>
      </section>
<section id="manual-export" className="case-panel"><h2>Access-controlled manual export</h2><p>Version 2 exports the most recent 100 evidence versions and 500 audit actions as provenance metadata, with totals and an explicit truncation flag. Private note/reason bodies, reporter identity, exact location, media and provider payloads are omitted by policy. This does not send the case anywhere.</p>
        <button type="button" disabled={disabled} onClick={async () => { try { const value = await (await authorityRequest(unitId,`cases/${caseId}/export-v2`)).json();
          const blob = new Blob([JSON.stringify(value,null,2)],{ type:"application/json" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href=url; a.download=`pilot-case-${caseId}-metadata-v2.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000); setMessage("Manual metadata export downloaded. No government delivery occurred.");
        } catch (failure) { setError((failure as Error).message); } }}>Download manual metadata packet</button>
      </section>
<section id="external-reference" className="case-panel"><h2>Manual external complaint reference</h2><p>{data.external_reference ?? "No reference recorded."}</p><p>A reference is a manual record, not evidence of delivery or agency receipt.</p>
        <ActionForm label="External complaint reference" button="Record manual reference" maxLength={200} disabled={disabled} onSave={(text) => act("external-references",{ reference:text })} /></section>
      </div><div className="case-actions-column">
<section id="review-actions" className="case-panel"><h2>Human review</h2><p>Case {data.id} · Revision <strong data-testid="case-revision">{data.revision}</strong> · {reviewLabel(data.review_state)}</p>
        <p>Review is independent of processing. Closure records that review ended; it does not assert that pollution was eliminated.</p>
        <p>Owner: {data.assigned_member_id ? reviewers.find((r) => r.id === data.assigned_member_id)?.label ?? "Unavailable member" : "Unassigned to a reviewer"}.</p>
        <button type="button" disabled={disabled} onClick={() => void act("assignments",{ claim_self:true })}>Claim case for myself</button>
        {admin && <form onSubmit={(e) => { e.preventDefault(); void act("assignments",{ membership_id:assignee || null }); }}>
          <label>Case assignee<select aria-label="Case assignee" disabled={disabled} value={assignee} onChange={(e) => setAssignee(e.target.value)}><option value="">Unassigned</option>{reviewers.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label><button type="submit" disabled={disabled}>Assign case</button></form>}
        <form onSubmit={async (e) => { e.preventDefault(); if (await act("review-events",{ state:target,reason })) { setReason(""); setTarget(""); } }}>
          <label>Review action<select aria-label="Review action" required disabled={disabled} value={target} onChange={(e) => setTarget(e.target.value)}><option value="">Choose an allowed action</option>{data.permitted_review_states.map((s) => <option key={s} value={s} disabled={s === "CLOSED_NO_ACTION" && data.field_follow_ups.some((t) => ["REQUESTED","ASSIGNED"].includes(t.state))}>{reviewLabel(s)}</option>)}</select></label>
          {data.field_follow_ups.some((t) => ["REQUESTED","ASSIGNED"].includes(t.state)) && <p>Complete or cancel open field follow-ups before closing this review.</p>}
          <label>Review reason<textarea required maxLength={2000} disabled={disabled} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <button type="submit" disabled={disabled || !target || !reason.trim()}>Record review decision</button>
        </form>
      </section>
<section id="internal-notes" className="case-panel internal-panel"><h2>Internal notes — review unit only</h2><p>Visible to your review unit. These notes never publish automatically.</p><ul>{data.internal_notes.map((n,i) => <li key={i}>{n}</li>)}</ul>
        <ActionForm label="Internal note" button="Add internal note" disabled={disabled} onSave={(text) => act("internal-notes",{ body:text })} /></section>
<section id="resident-question" className="case-panel"><h2>Request information from resident</h2><Publication request disabled={disabled || data.review_state === "CLOSED_NO_ACTION"} act={act} />
        <ul>{data.information_requests.map((r) => <li key={r.id}>{r.state}: {r.prompt}</li>)}</ul>
        <h3>Resident supplementary information</h3>{!data.supplements.length && <p>No supplementary reply yet.</p>}
        {data.supplements.map((s) => <article key={s.id}><p>{s.body}</p><p>Received {displayedTime(s.accepted_at)}. Original report and evidence are unchanged.</p>{s.media && <Photo unitId={unitId} caseId={caseId} media={s.media} />}</article>)}
      </section>
<section id="field-follow-up" className="case-panel"><h2>Pilot field follow-up</h2><p>A recorded request or finding does not establish dispatch by a government body.</p>
        <ActionForm label="Field follow-up instructions" button="Request field follow-up" disabled={disabled || data.review_state === "CLOSED_NO_ACTION"} onSave={(text) => act("field-follow-ups",{ reason:text })} />
        {data.field_follow_ups.map((t) => <FollowUp key={t.id} task={t} disabled={disabled} admin={admin} reviewers={reviewers} act={act} />)}
      </section>
<section id="reporter-publication" className="case-panel publication-panel"><h2>Publish update to reporter</h2><p>Write a separate public message. Internal review/closure alone does not update the resident timeline. Publish CLOSED only after internal review closure.</p><Publication disabled={disabled} closed={data.review_state === "CLOSED_NO_ACTION"} act={act} />
        <h3>Already published</h3><ol>{data.published_updates.map((u) => <li key={u.id}>{reporterStatusLabel(u.status)}: {u.message ?? "Initial durable receipt"} · {displayedTime(u.published_at)}</li>)}</ol>
      </section>
      </div></div>
    </>}
    <Link href={`/authority/cases?unit=${unitId}`}>Back to case queue</Link>
  </div>;
}
