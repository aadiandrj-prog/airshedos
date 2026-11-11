"use client";
import { useEffect, useRef, useState } from "react";
import { residentRequest, retryHeaders, uploadPhoto, ResidentFailure } from "../../lib/resident-client";
import { OptionalPhoto } from "./optional-photo";

export function ReplyForm({ reportId, requestId, onSaved }: { reportId: string; requestId: string; onSaved: () => void }) {
  const [body, setBody] = useState(""); const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [photoFailed, setPhotoFailed] = useState(false);
  const [locked, setLocked] = useState(false);
  const attempt = useRef<{ key: string; createdAt: string; body?: { body: string; media_id: string | null } } | null>(null);
  const running = useRef(false); const alert = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) alert.current?.focus(); }, [error]);
  async function send(withoutPhoto = false) {
    if (running.current || !body.trim()) { if (!body.trim()) setError("Provide supplementary text before sending."); return; }
    running.current = true; setBusy(true); setError(""); setPhotoFailed(false);
    try {
      if (!attempt.current) attempt.current = { key: crypto.randomUUID(), createdAt: new Date().toISOString() };
      if (!attempt.current.body) {
        let mediaId: string | null = null;
        if (consent && file && !withoutPhoto) {
          try { mediaId = (await uploadPhoto(file)).id; }
          catch { setPhotoFailed(true); throw new Error("Photo upload failed. Retry or send supplementary text without a photo."); }
        }
        attempt.current.body = { body, media_id: mediaId }; setLocked(true);
      }
      await residentRequest(`reports/${reportId}/information-requests/${requestId}/replies`, {
        method: "POST", headers: retryHeaders(attempt.current), body: JSON.stringify(attempt.current.body) });
      onSaved();
    } catch (failure) {
      if (failure instanceof ResidentFailure && failure.status === 409) { onSaved(); return; }
      if (failure instanceof ResidentFailure && failure.status === 422 && attempt.current) {
        attempt.current.body = undefined; setLocked(false);
      }
      if (failure instanceof ResidentFailure && failure.status === 404 && attempt.current?.body?.media_id) setPhotoFailed(true);
      setError(failure instanceof Error ? failure.message : "Reply could not be confirmed. Please retry.");
    } finally { running.current = false; setBusy(false); }
  }
  return <form onSubmit={(event) => { event.preventDefault(); void send(); }}>
    <p>Your original report remains unchanged. This adds one reply to this request, for review.</p>
    <label>Additional information<textarea required minLength={1} maxLength={2000} value={body}
      disabled={busy || locked} onChange={(e) => setBody(e.target.value)} /></label>
    <OptionalPhoto file={file} onFile={setFile} consent={consent} onConsent={setConsent}
      disabled={busy || locked} />
    {error && <p role="alert" ref={alert} tabIndex={-1}>{error}</p>}
    <button type="submit" disabled={busy}>{busy ? "Saving reply…" : locked ? "Retry same reply" : "Send reply"}</button>
    {photoFailed && <button type="button" disabled={busy} onClick={() => {
      setFile(null); if (attempt.current?.body) attempt.current.body = { ...attempt.current.body, media_id: null };
      void send(true);
    }}>Send reply without photo</button>}
  </form>;
}
