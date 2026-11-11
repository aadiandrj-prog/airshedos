"use client";
import { useDeadline } from "../authority/expiry";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { displayedTime, processingLabel, reporterStatusLabel, residentRequest, type Detail, type Stage } from "../../lib/resident-client";
import { LocalContext } from "./local-context";
import { ReplyForm } from "./reply-form";

function PrivatePhoto({ media }: { media: Stage | null }) {
  const [expired, setExpired] = useState(false); const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    if (!media) return;
    // Browser timers overflow above ~24.8 days; media can remain valid for 30 days.
    const delay = () => Math.min(2_147_483_647, Math.max(0, Date.parse(media.expires_at) - Date.now()));
    const check = () => {
      if (Date.parse(media.expires_at) <= Date.now()) setExpired(true);
      else timer = setTimeout(check, delay());
    };
    let timer = setTimeout(check, delay());
    return () => clearTimeout(timer);
  }, [media]);
  if (!media) return <p>No photo retained.</p>;
  if (expired || unavailable || media.state !== "ATTACHED") return <p>Photo unavailable or expired under retention rules.</p>;
  // A native same-origin image preserves authenticated no-store delivery; no shared optimizer.
  // eslint-disable-next-line @next/next/no-img-element
  return <figure><img src={`/api/app/v2/resident/media/${media.id}`} alt="Private photo attached to your report" onError={() => setUnavailable(true)} /><figcaption>Private cleaned derivative. Expires {displayedTime(media.expires_at)}.</figcaption></figure>;
}

export function ReportDetail({ reportId }: { reportId: string }) {
  const [data, setData] = useState<Detail | null>(null); const [error, setError] = useState("");
  const load = useCallback(async () => (await residentRequest(`reports/${reportId}`)).json(), [reportId]);
  const reload = () => void load().then((value) => { setData(value); setError(""); })
    .catch(() => { setData(null); setError("This report could not be loaded. It may have expired or be outside your account."); });
  useEffect(() => {
    let active = true;
    void load().then((value) => { if (active) { setData(value); setError(""); } })
      .catch(() => { if (active) { setData(null); setError("This report could not be loaded. It may have expired or be outside your account."); } });
    return () => { active = false; };
  }, [load]);
  useDeadline(data?.content_expires_at, () => { setData(null); setError("This report’s retention period ended. Its content was removed from this view."); });
  if (error) return <section><p role="alert">{error}</p><button type="button" onClick={reload}>Retry loading report</button><p><Link href={`/sign-in?returnTo=${encodeURIComponent(`/resident/reports/${reportId}`)}`}>Sign in again</Link></p><p><Link href="/resident/reports">Back to my reports</Link></p></section>;
  if (!data || data.id !== reportId) return <p role="status">Loading your saved report…</p>;
  const timeline = [
    ...data.published_updates.map((item) => ({ id: item.id, time: item.published_at,
      title: reporterStatusLabel(item.status), body: item.message, order: item.timeline_order ?? 0 })),
    ...(data.supplements ?? []).map((item) => ({ id: item.id, time: item.accepted_at,
      title: "Your supplementary information received", body: item.body, order: item.timeline_order ?? 0 })),
  ].sort((a,b) => Date.parse(a.time) - Date.parse(b.time) || a.order - b.order || a.id.localeCompare(b.id));
  return <div className="resident-stack">
    <section className="resident-card receipt-panel" aria-label="Saved report acknowledgement"><span className="status-chip">Saved in your account</span><h2>Report received</h2>
      <p>Reference: <strong>{data.receipt_id}</strong></p><p>Saved {displayedTime(data.accepted_at)}.</p>
      <h3>{processingLabel(data.processing.state)}</h3><p>Your report has been saved. Analysis is separate and is not required for this receipt.</p>
      <p>Original visual analysis: {data.processing.visual_state === "NOT_APPLICABLE" ? data.media ? "not applicable (photo unavailable for this attempt)" : "not applicable (no photo)" : data.processing.visual_state.toLowerCase()}.</p>
    </section>
    {(data.information_requests ?? []).filter((request) => request.state === "OPEN" && request.prompt).map((request) => <section className="resident-card reply-request" key={request.id}>
      <h2>More information requested</h2><p>{request.prompt}</p>
      <ReplyForm reportId={data.id} requestId={request.id} onSaved={reload} />
    </section>)}
    <section className="resident-card"><h2>Your submitted information</h2><p>{data.description}</p>
      <dl><dt>Declared concern</dt><dd>{data.declared_category.replaceAll("_", " ").toLowerCase()}</dd>
        <dt>Reported place</dt><dd>{data.reported_place ?? "Place label not supplied"}</dd>
        <dt>Reported coordinates</dt><dd>{data.reported_location.latitude}, {data.reported_location.longitude} (resident-declared)</dd>
        <dt>Declared incident time</dt><dd>{data.declared_capture_at ? `${displayedTime(data.declared_capture_at)} (resident-declared)` : "Unknown (not supplied)"}</dd></dl>
      <p className="resident-help">Displayed times use your browser timezone. Report receipt time does not verify incident or photo capture time.</p>
      <PrivatePhoto media={data.media} />
    </section>
    <LocalContext reportId={data.id} latitude={String(data.reported_location.latitude)} longitude={String(data.reported_location.longitude)} />
    <section className="resident-card"><h2>Status timeline</h2><p>Only published review updates and your replies appear here.</p><ol className="resident-timeline">{timeline.map((event) => <li key={event.id}><strong>{event.title}</strong><time dateTime={event.time}>{displayedTime(event.time)}</time>{event.body && <p>{event.body}</p>}</li>)}</ol></section>
    {(data.supplements ?? []).map((supplement) => supplement.media && <section key={supplement.id}><h3>Photo with your supplementary information</h3><PrivatePhoto media={supplement.media} /></section>)}
    <Link href="/resident/reports">Back to my reports</Link>
  </div>;
}
