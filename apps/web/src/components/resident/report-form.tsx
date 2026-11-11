"use client";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearResidentAttempts, keepAttempt, readAttempt, residentRequest, retryHeaders,
  uploadPhoto, ResidentFailure, type Attempt, type Receipt, type Submission } from "../../lib/resident-client";
import { OptionalPhoto } from "./optional-photo";
import { ReportedLocation } from "./location";
import { LocalContext } from "./local-context";

const subscribeReady = () => () => {};
const clientReady = () => true;
const serverReady = () => false;

export function ReportForm({ userId }: { userId: string }) {
  const router = useRouter();
  const hydrated = useSyncExternalStore(subscribeReady, clientReady, serverReady);
  const form = useRef<HTMLFormElement>(null);
  const attempt = useRef<Attempt | null>(null);
  const running = useRef(false);
  const [description, setDescription] = useState("");
  const [place, setPlace] = useState("");
  const [category, setCategory] = useState<Submission["declared_category"]>("UNSURE");
  const [latitude, setLatitude] = useState(""); const [longitude, setLongitude] = useState("");
  const [incidentTime, setIncidentTime] = useState("");
  const [file, setFile] = useState<File | null>(null); const [consent, setConsent] = useState(false);
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false); const [locked, setLocked] = useState(false);
  const [message, setMessage] = useState(""); const [error, setError] = useState("");
  const [photoFailed, setPhotoFailed] = useState(false);
  const [accepted, setAccepted] = useState<Receipt | null>(null);
  const alert = useRef<HTMLParagraphElement>(null);

  function finish(receipt: Receipt) {
    setAccepted(receipt); clearResidentAttempts();
    router.replace(`/resident/reports/${receipt.report_id}`);
  }

  useEffect(() => {
    const saved = readAttempt(userId);
    if (!saved) return;
    attempt.current = saved;
    void (async () => {
      try { finish(await (await residentRequest(`submissions/${saved.key}`)).json()); }
      catch (failure) {
        if (saved.body) {
          setDescription(saved.body.description); setPlace(saved.body.reported_place);
          setCategory(saved.body.declared_category); setLatitude(String(saved.body.reported_latitude));
          setLongitude(String(saved.body.reported_longitude)); setLocked(true); setRemember(true);
        }
        setError(failure instanceof ResidentFailure && failure.status === 404
          ? "No committed receipt was found. Re-enter any details that were not kept in this tab, then retry."
          : "Your previous attempt could not be checked. You can retry the same report.");
      }
    })();
    // Hydrate external per-tab state once for the verified account, never auto-submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);
  useEffect(() => { if (error) alert.current?.focus(); }, [error]);

  async function send(withoutPhoto = false) {
    if (running.current || accepted) return;
    if (!attempt.current?.body && !form.current?.reportValidity()) return;
    if (!attempt.current?.body && (!description.trim() || !place.trim())) {
      setError("Provide a useful description and reported place."); return;
    }
    running.current = true; setBusy(true); setError(""); setPhotoFailed(false);
    try {
      if (!attempt.current) attempt.current = { ownerId: userId, key: crypto.randomUUID(), createdAt: new Date().toISOString() };
      const current = attempt.current;
      keepAttempt(current, remember);
      try { finish(await (await residentRequest(`submissions/${current.key}`)).json()); return; }
      catch (failure) { if (!(failure instanceof ResidentFailure) || failure.status !== 404) throw failure; }
      if (!current.body) {
        let mediaId: string | null = null;
        if (consent && file && !withoutPhoto) {
          setMessage("Preparing your private photo…");
          try { mediaId = (await uploadPhoto(file)).id; }
          catch { setPhotoFailed(true); throw new Error("Photo upload could not complete. You can retry or send without a photo."); }
        }
        current.body = { description, reported_place: place, declared_category: category,
          reported_latitude: Number(latitude), reported_longitude: Number(longitude),
          declared_capture_at: incidentTime ? new Date(incidentTime).toISOString() : null, media_id: mediaId };
        keepAttempt(current, remember); setLocked(true);
      }
      setMessage("Saving your report…");
      const response = await residentRequest("reports", { method: "POST", headers: retryHeaders(current), body: JSON.stringify(current.body) });
      finish(await response.json());
    } catch (failure) {
      if (failure instanceof ResidentFailure && failure.status === 422 && attempt.current) {
        attempt.current.body = undefined; setLocked(false); keepAttempt(attempt.current, false);
      }
      if (failure instanceof ResidentFailure && failure.status === 404 && attempt.current?.body?.media_id)
        setPhotoFailed(true);
      if (failure instanceof ResidentFailure && failure.status === 409 && attempt.current) {
        try { finish(await (await residentRequest(`submissions/${attempt.current.key}`)).json()); return; } catch { /* Keep same retry reference. */ }
      }
      setError(failure instanceof Error ? failure.message : "The save could not be confirmed. Please retry.");
      setMessage("");
    } finally { running.current = false; setBusy(false); }
  }

  if (accepted) return <section role="status"><h2>Report received</h2><Link href={`/resident/reports/${accepted.report_id}`}>View your saved report</Link></section>;
  return <form className="resident-intake" ref={form} aria-busy={!hydrated || busy} onSubmit={(event) => { event.preventDefault(); void send(); }}>
    <p className="pilot-notice">Your report is saved before any AI or provider checks. This pilot does not provide emergency response or official government dispatch.</p>
    <fieldset disabled={!hydrated || busy || locked}><legend>01 · Your report</legend>
      <label>Description<textarea required minLength={1} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} aria-describedby="description-help" /></label>
      <small id="description-help">Describe what you noticed. Avoid names, phone numbers and unnecessary personal information. Up to 2,000 characters.</small>
      <label>What did you notice?<select value={category} onChange={(e) => setCategory(e.target.value as Submission["declared_category"])}>
        <option value="UNSURE">Unsure</option><option value="SMOKE_OR_BURNING">Smoke or burning</option><option value="DUST">Dust</option><option value="ODOUR">Odour</option><option value="OTHER">Other concern</option>
      </select></label>
      <label>Reported place<input required minLength={1} maxLength={200} value={place} onChange={(e) => setPlace(e.target.value)} placeholder="Area, landmark or nearby entrance" /></label>
      <label>Declared incident time (optional)<input type="datetime-local" value={incidentTime} onChange={(e) => setIncidentTime(e.target.value)} aria-describedby="time-help" /></label>
      <small id="time-help">Leave blank if unknown. A supplied time is your declaration, not a verified capture time. The input uses your device timezone.</small>
    </fieldset>
    <ReportedLocation latitude={latitude} longitude={longitude} disabled={!hydrated || busy || locked} onChange={(lat, lng) => { if (!locked) { setLatitude(lat); setLongitude(lng); } }} />
    <OptionalPhoto legend="03 · Optional photo" file={file} onFile={setFile} consent={consent} onConsent={setConsent} disabled={!hydrated || busy || locked} />
    <label className="resident-check"><input type="checkbox" checked={remember} disabled={!hydrated || busy || locked} onChange={(e) => setRemember(e.target.checked)} />Allow this tab to keep the attempted report&apos;s text for retries (up to 24 hours). It clears after receipt or sign-out. Photos and login tokens are never kept in this draft.</label>
    <p className="resident-help">Without that option, this tab keeps only a private retry reference. Nothing submits automatically after a reload.</p>
    <LocalContext latitude={latitude} longitude={longitude} />
    {error && <p role="alert" ref={alert} tabIndex={-1}>{error}</p>}
    <p role="status">{message}</p>
    <div className="form-submit"><button type="submit" disabled={!hydrated || busy}>{busy ? "Saving…" : locked || error ? "Retry same report" : "Submit report"}</button>
    {photoFailed && <button type="button" disabled={!hydrated || busy} onClick={() => {
      setFile(null);
      if (attempt.current?.body) attempt.current.body = { ...attempt.current.body, media_id: null };
      void send(true);
    }}>Send without photo</button>}
    <Link href="/resident/reports">Check my saved reports</Link></div>
  </form>;
}
