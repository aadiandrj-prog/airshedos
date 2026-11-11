"use client";
import { useEffect, useState } from "react";

export function OptionalPhoto({ file, onFile, consent, onConsent, disabled = false, legend = "Optional photo" }: {
  file: File | null; onFile: (file: File | null) => void; consent: boolean;
  onConsent: (consent: boolean) => void; disabled?: boolean; legend?: string;
}) {
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [file, preview]);
  return <fieldset disabled={disabled}><legend>{legend}</legend>
    <p>Text-only reports are valid. Without a photo, visual analysis is not applicable.</p>
    <p className="resident-help">With your agreement, a cleaned image derivative is kept privately for report review for up to 30 days, or less if the report expires or is deleted. Metadata is stripped; original uploads are not stored. You and approved assigned-unit reviewers can access the derivative.</p>
    <label className="resident-check"><input type="checkbox" checked={consent} onChange={(event) => {
      onConsent(event.target.checked); if (!event.target.checked) onFile(null);
    }} />I agree to private retention of a cleaned photo for report review.</label>
    <label>Photo (optional)<input type="file" accept="image/jpeg,image/png" disabled={!consent}
      onChange={(event) => {
        const candidate = event.target.files?.[0]; setError("");
        if (candidate && (!["image/jpeg", "image/png"].includes(candidate.type) || candidate.size > 4_000_000)) {
          setError("Use one JPEG/PNG up to 4,000,000 bytes. You can still submit text only.");
          event.target.value = ""; onFile(null); return;
        }
        setPreview(candidate ? URL.createObjectURL(candidate) : ""); onFile(candidate ?? null);
      }} /></label>
    {error && <p role="alert">{error}</p>}
    {file && preview && <>
      {/* Private local preview must not use a shared image optimizer/cache. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={preview} alt="Photo selected for your report" />
      <button type="button" onClick={() => onFile(null)}>Remove photo</button>
    </>}
    {!consent && <p>No photo will be uploaded. You may continue with text only.</p>}
  </fieldset>;
}
