"use client";

import { useEffect, useRef, useState } from "react";
import { api, type CorroborationAssessment } from "@/lib/api";

import { ForecastOutlook } from "./forecast-outlook";

const label = (text: string) => text.replaceAll("_", " ");
const sourceLabel = (text: string) =>
  (
    ({
      "Sentinel-5P no2": "Sentinel-5P NO₂",
      "Sentinel-5P co": "Sentinel-5P CO",
      "Sentinel-5P aerosol_index": "Sentinel-5P Aerosol Index",
    }) as Record<string, string>
  )[text] ?? text;
const time = (value: string) =>
  new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) +
  " IST";
const age = (seconds: number) =>
  seconds < 0
    ? "within clock-skew allowance"
    : seconds < 3600
      ? `${Math.round(seconds / 60)} min old`
      : `${(seconds / 3600).toFixed(1)} h old`;

function displayReference(rule: CorroborationAssessment["rules"][number]) {
  return (
    rule.evidence_references.find(
      (ref) => ref.source_id === rule.inputs_used.selected_source_id,
    ) ?? rule.evidence_references[0]
  );
}

export function CorroborationCard({
  reportId,
  ttlSeconds,
  onCorroborated,
}: {
  reportId: string;
  ttlSeconds: number | null;
  onCorroborated?: (assessment: CorroborationAssessment, signal: AbortSignal) => Promise<boolean>;
}) {
  const [result, setResult] = useState<CorroborationAssessment | null>(null);
  const [inQueue, setInQueue] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function corroborate() {
    if (busy) return;
    const active = new AbortController();
    controller.current = active;
    setBusy(true);
    setError("");
    setResult(null);
    setInQueue(false);
    try {
      const assessment = await api.corroborate(reportId, active.signal);
      if (!active.signal.aborted) {
        setResult(assessment);
        if (onCorroborated) {
          const queued = await onCorroborated(assessment, active.signal);
          if (!active.signal.aborted) setInQueue(queued);
        }
      }
    } catch (cause) {
      if (!active.signal.aborted)
        setError(
          cause instanceof Error
            ? cause.message
            : "Corroboration could not complete. Try again.",
        );
    } finally {
      if (!active.signal.aborted) setBusy(false);
    }
  }

  return (
    <section
      className="fusion-panel"
      aria-label="Evidence corroboration"
      aria-busy={busy}
    >
      <div className="fusion-action">
        <button type="button" onClick={corroborate} disabled={busy}>
          {busy
            ? "Checking environmental evidence…"
            : "Corroborate with environmental data"}
        </button>
        <p className="source-caveat">
          Uses the server-owned interpretation; the image is not sent again.
          Structured report availability: up to{" "}
          {Math.round((ttlSeconds ?? 1800) / 60)} minutes, or until server
          restart or capacity eviction.
        </p>
      </div>
      {busy && (
        <p role="status">
          Looking up environmental sources, then applying the evidence
          checklist. Satellite retrieval can take around 25 seconds; the separate Google forecast follows. Missing sources will remain visible.
        </p>
      )}
      {error && (
        <p role="alert" className="source-caveat">
          {error}
        </p>
      )}
      {inQueue && <p className="feedback">Assessment added to the officer queue above. <a href="#officer-command">Open the selected case to review and hand off.</a></p>}
      {result && !inQueue && (
        <AssessmentView result={result} reportId={reportId} />
      )}
    </section>
  );
}

export function AssessmentView({ result, reportId, showForecast = true }: { result: CorroborationAssessment; reportId: string; showForecast?: boolean }) {
  return (
        <article
          className="fusion-card"
          aria-labelledby={`fusion-${reportId}`}
          aria-live="polite"
        >
          <span className="eyebrow">EVIDENCE FUSION CARD</span><p className="source-caveat">DETERMINISTIC AIRSHEDOS ANALYSIS · rule-based support, not confirmation of an event.</p>
          <div className="fusion-heading">
            <div>
              <p className="eyebrow">Possible event</p>
              <h3 id={`fusion-${reportId}`}>{label(result.event_type)}</h3>
            </div>
            <div>
              <p className="eyebrow">Corroboration</p>
              <strong
                className={`fusion-level ${result.support_level.toLowerCase()}`}
              >
                {label(result.support_level)}
                {["STRONG", "MODERATE", "WEAK"].includes(result.support_level)
                  ? " SUPPORT"
                  : " EVIDENCE"}
              </strong>
            </div>
          </div>
          <p>{result.aggregation_explanation}</p>
          <p className="source-caveat">
            Checklist category, not a probability. Assessed{" "}
            {time(result.generated_at)}.
          </p>
          <div className="fusion-rows">
            {result.rules.map((rule, index) => (
              <div className="fusion-row" key={rule.rule_id}>
                <div className="fusion-row-heading">
                  <h4>{sourceLabel(rule.source)}</h4>
                  <span
                    className={`source-state ${rule.verdict === "SUPPORTS" ? "live" : rule.verdict === "WEAKLY_SUPPORTS" ? "cached" : "unavailable"}`}
                  >
                    {rule.source.startsWith("Sentinel") &&
                    rule.verdict === "NEUTRAL"
                      ? "CONTEXT ONLY"
                      : label(rule.verdict)}
                  </span>
                </div>
                <p>{rule.summary}</p>
                <p className="source-caveat">
                  Source: {label(result.source_summary[index].status)}
                  {displayReference(rule)?.age_seconds != null
                    ? ` · ${age(displayReference(rule)!.age_seconds!)}`
                    : ""}
                </p>
                {rule.source.startsWith("Sentinel") &&
                  rule.inputs_used.value != null && (
                    <p className="source-caveat">
                      {String(rule.inputs_used.value)}{" "}
                      {String(rule.inputs_used.unit)} · Quality:{" "}
                      {String(rule.inputs_used.quality)}
                    </p>
                  )}
                <details>
                  <summary>
                    {sourceLabel(rule.source)} provenance and rule
                  </summary>
                  <p className="source-caveat">
                    {rule.rule_id} · Evaluated {time(rule.generated_at)}
                  </p>
                  <dl className="fusion-inputs">
                    {Object.entries(rule.inputs_used).map(([key, value]) => (
                      <div key={key}>
                        <dt>{label(key)}</dt>
                        <dd>
                          {value === null
                            ? "Unavailable"
                            : typeof value === "object"
                              ? JSON.stringify(value)
                              : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {rule.evidence_references.map((ref) => (
                    <div className="fusion-reference" key={ref.source_id}>
                      <p>Source ID: {ref.source_id}</p>
                      <p>
                        Observed:{" "}
                        {ref.observed_at
                          ? time(ref.observed_at)
                          : "Image capture time unknown"}{" "}
                        · Retrieved / interpreted: {time(ref.retrieved_at)}
                      </p>
                      {ref.submission_offset_seconds != null && (
                        <p>
                          Observation offset from submission:{" "}
                          {Math.round(ref.submission_offset_seconds / 60)} min
                          (negative = before).
                        </p>
                      )}
                      <p>
                        {ref.provenance.method} · {ref.provenance.note}
                      </p>
                      {"model" in ref.provenance && (
                        <p>
                          Model: {ref.provenance.model} · Prompt:{" "}
                          {ref.provenance.prompt_version}
                        </p>
                      )}
                    </div>
                  ))}
                </details>
              </div>
            ))}
          </div>
          <div className="fusion-next">
            <span className="eyebrow">ADVISORY NEXT STEP</span>
            <h4>{label(result.recommended_next_step)}</h4>
            <p>No incident or authority task has been created.</p>
          </div>
          {showForecast && <ForecastOutlook context={result.forecast_outlook ?? null} />}
          <div className="context-footnote">
            <span>LIMITATIONS</span>
            <ul>
              {result.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <details>
            <summary>Assessment provenance</summary>
            <p className="source-caveat">
              {result.id} · Report {result.report_id} · {result.policy_version}
            </p>
            <p>{result.provenance.note}</p>
            <p>
              Temporal basis: submission time proxy ·{" "}
              {time(result.submission_time)}
            </p>
            <p>
              Positive checklist rules:{" "}
              {result.contributing_rule_ids.join(", ") || "None"}. Wind is
              conditional context and does not independently raise the support
              category.
            </p>
          </details>
        </article>
  );
}
