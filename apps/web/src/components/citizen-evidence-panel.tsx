"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type CitizenAnalysis, type CorroborationAssessment } from "@/lib/api";

import { Badge, LoadingState } from "./ui";
import { CorroborationCard } from "./corroboration-card";

const label = (text: string) => text.replaceAll("_", " ");
const time = (value: string) =>
  new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value)) + " IST";

export function CitizenEvidencePanel({ onCorroborated }: { onCorroborated?: (assessment: CorroborationAssessment, signal: AbortSignal) => Promise<boolean> }) {
  const [borderDemo, setBorderDemo] = useState(false);
  const [synthetic, setSynthetic] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState<CitizenAnalysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function chooseFile(next: File | null) {
    setSynthetic(false);
    setBorderDemo(false);
    setResult(null);
    setError("");
    setPreview("");
    if (
      next &&
      (!["image/jpeg", "image/png"].includes(next.type) ||
        next.size > 5 * 1024 * 1024)
    ) {
      setFile(null);
      setError("Choose one JPEG or PNG image up to 5 MiB.");
      return;
    }
    setFile(next);
    if (next) setPreview(URL.createObjectURL(next));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || busy) return;
    const data = new FormData(event.currentTarget);
    data.set("image", file);
    data.set("is_synthetic", String(synthetic));
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.analyzeCitizen(data));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Analysis could not complete. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function loadSample(crossBorder = false) {
    try {
      const response = await fetch("/demo/open-burning.png");
      if (!response.ok) throw new Error();
      chooseFile(new File([await response.blob()], "synthetic-open-burning.png", { type: "image/png" }));
      setSynthetic(true);
      setBorderDemo(crossBorder);
      for (const [name, value] of [["latitude", crossBorder ? "28.52" : "28.4595"], ["longitude", crossBorder ? "77.08" : "77.0266"]]) {
        const input = formRef.current?.elements.namedItem(name);
        if (input instanceof HTMLInputElement && (crossBorder || !input.value)) input.value = value;
      }
    } catch { setError("Synthetic sample could not be loaded. Choose a local image instead."); }
  }

  function clear() {
    formRef.current?.reset();
    chooseFile(null);
  }

  const analysis = result?.analysis;
  return (
    <section
      className="citizen-panel"
      aria-labelledby="citizen-title"
      id="field-evidence"
    >
      <div className="environment-heading">
        <div>
          <span className="eyebrow">02 / SUBMIT FIELD EVIDENCE</span>
          <h2 id="citizen-title">
            A field observation. A careful interpretation.
          </h2>
          <p>
            One image, its location and your description. Separate from
            environmental readings and incidents.
          </p>
        </div>
        <Badge tone="ai">AI interpretation · visual evidence only</Badge>
      </div>
      <div className="citizen-columns">
        <form
          ref={formRef}
          onSubmit={submit}
          className="citizen-form"
          aria-label="Submit field evidence"
        >
          <h3>Submit a field observation</h3>
          <fieldset disabled={busy}>
            <label htmlFor="citizen-image">
              Field image <span>JPEG or PNG · up to 5 MiB · 16 MP</span>
            </label>
            <input
              id="citizen-image"
              name="image"
              type="file"
              accept="image/jpeg,image/png"
              required={!synthetic}
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            />
            {preview && (
              // Browser-owned object URL: never uploaded to a frontend image service.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="citizen-preview"
                src={preview}
                alt="Selected citizen submission preview"
              />
            )}
            <div className="citizen-coordinates">
              <label>
                Field latitude
                <input
                  name="latitude"
                  type="number"
                  min="-90"
                  max="90"
                  step="any"
                  placeholder="28.4595"
                  required
                />
              </label>
              <label>
                Field longitude
                <input
                  name="longitude"
                  type="number"
                  min="-180"
                  max="180"
                  step="any"
                  placeholder="77.0266"
                  required
                />
              </label>
            </div>
            <label htmlFor="citizen-description">
              Your description <span>Optional · up to 2,000 characters</span>
            </label>
            <textarea
              id="citizen-description"
              name="description"
              maxLength={2000}
              rows={3}
              placeholder="Describe what you can see."
            />
            <p className="source-caveat">
              Submitting sends this image and context to Google Vertex AI for
              interpretation. AirshedOS does not retain the image. Structured
              report metadata and interpretation are held temporarily for
              corroboration, then expire. Avoid including identifying details.
            </p>
            {borderDemo && <p className="synthetic-label">SYNTHETIC CROSS-JURISDICTION DEMO · Fictional Delhi–Haryana border-area scenario at 28.52, 77.08. Exact boundary and location ownership are unverified. Choose control rooms manually after review.</p>}
            {synthetic && <p className="synthetic-label">SYNTHETIC IMAGE · Demonstration only. Gemini and provider calls still use live services.</p>}
            <div className="sample-actions"><button type="button" className="secondary" onClick={() => void loadSample()} disabled={busy}>Use synthetic sample image</button>
            <button type="button" className="secondary" onClick={() => void loadSample(true)} disabled={busy}>Use synthetic cross-jurisdiction demo</button>
            </div>
            <div className="citizen-actions">
              <button type="submit" disabled={!file || busy}>
                {busy ? "Interpreting image…" : "Interpret image"}
              </button>
              <button type="button" className="secondary" onClick={clear}>
                Clear submission
              </button>
            </div>
          </fieldset>
        </form>
        <div className="citizen-result" aria-live="polite" aria-busy={busy}>
          <h3>AI INTERPRETATION</h3>
          {busy && (
            <LoadingState>
              Interpreting visual evidence. This may take up to 30 seconds.
            </LoadingState>
          )}
          {error && (
            <p role="alert" className="source-caveat">
              {error}
            </p>
          )}
          {!result && !busy && !error && (
            <div className="citizen-empty">
              <span aria-hidden="true">◇</span>
              <p>The interpretation will appear here.</p>
              <p className="source-caveat">
                No environmental corroboration occurs in this step.
              </p>
            </div>
          )}
          {result && (
            <>
              <span className={`source-state ${analysis ? "live" : "error"}`}>
                {label(result.status)}
              </span>
              <p className="source-caveat">
                Submission received at {time(result.report.created_at)}.
                Location: {result.report.latitude}, {result.report.longitude}.
              </p>
              {result.report.description && (
                <blockquote className="citizen-description">
                  <strong>Citizen description · unverified</strong>
                  <p>{result.report.description}</p>
                </blockquote>
              )}
              {analysis ? (
                <CitizenInterpretation analysis={analysis} latencyMs={result.latency_ms} />
              ) : (
                <p role="alert">{result.message}</p>
              )}
            </>
          )}
          <div className="context-footnote citizen-disclaimer">
            <span>INTERPRETATION ≠ CORROBORATION</span>
            <p>
              AI interpretation — requires environmental corroboration. An image
              cannot establish pollutant concentration, source causality or a
              violation.
            </p>
          </div>
        </div>
      </div>
      {analysis && result && (
        <CorroborationCard
          key={result.report.id}
          reportId={result.report.id}
          ttlSeconds={result.structured_report_ttl_seconds}
          onCorroborated={onCorroborated}
        />
      )}
    </section>
  );
}

export function CitizenInterpretation({ analysis, latencyMs }: { analysis: NonNullable<CitizenAnalysis["analysis"]>; latencyMs?: number }) {
  return (
                <>
                  <Badge tone="ai">Gemini AI interpretation</Badge><p className="eyebrow">Possible event type</p>
                  <h4 className="citizen-event">
                    {label(analysis.event_type)}
                  </h4>
                  <p>
                    Interpretation confidence:{" "}
                    <strong>{label(analysis.event_type_confidence)}</strong>
                  </p>
                  <p className="source-caveat">
                    Model-estimated ordinal judgment, not a calibrated
                    probability or incident confidence.
                  </p>
                  <h4>Visible observations</h4>
                  <ul>
                    {analysis.visual_observations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <h4>Uncertainty</h4>
                  <ul>
                    {analysis.uncertainty_reasons.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <p className="source-caveat">
                    Model:{" "}
                    {analysis.provenance.model_version ??
                      analysis.provenance.model}{" "}
                    · Prompt: {analysis.provenance.prompt_version} ·{" "}
                    {latencyMs == null ? "Not retained" : `${(latencyMs / 1000).toFixed(1)} s`}
                  </p>
                  <p className="source-caveat">
                    Derived from {analysis.source_report_id}. Interpreted{" "}
                    {time(analysis.analyzed_at)}; image capture time unknown.
                  </p>
                </>
  );
}
