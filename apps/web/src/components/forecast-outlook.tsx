"use client";

import { useEffect, useState } from "react";
import { api, type ForecastContext, type Measurement } from "@/lib/api";

const units: Record<string, string> = {
  MICROGRAMS_PER_CUBIC_METER: "µg/m³",
  PARTS_PER_BILLION: "ppb",
};
const quantity = (m: Measurement | null | undefined) =>
  m
    ? `${m.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${units[m.unit] ?? m.unit}`
    : "Not supplied";
const time = (value: string) =>
  new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }) + " IST";
const states = {
  live: "Forecast retrieved",
  cached: "Forecast cached",
  unavailable: "Forecast unavailable",
  error: "Forecast provider error",
  not_configured: "Forecast not configured",
};

export function ForecastOutlook({
  context,
}: {
  context: ForecastContext | null;
}) {
  const [horizon, setHorizon] = useState<6 | 12 | 24>(6);
  const summary = context?.summaries.find((s) => s.horizon_hours === horizon);
  const current = context?.current_air_quality;
  const currentPm = current?.pollutants.find(
    (p) => p.code === "pm25",
  )?.concentration;
  const currentCpcb = current?.indexes.find((i) => i.code === "ind_cpcb");
  return (
    <section className="forecast-outlook" aria-label="Forecast outlook">
      <div className="environment-heading">
        <div>
          <span className="eyebrow">FORECAST OUTLOOK</span>
          <h3>Google Air Quality forecast</h3>
          <p>External provider outlook · separate from corroboration</p>
        </div>
        {context && (
          <span className={`source-state ${context.provider_status.status}`}>
            {states[context.provider_status.status]}
          </span>
        )}
      </div>
      {!context ? (
        <p className="source-caveat">Forecast outlook unavailable.</p>
      ) : (
        <>
          <div className="forecast-horizons" aria-label="Forecast horizon">
            {([6, 12, 24] as const).map((hours) => (
              <button
                key={hours}
                type="button"
                aria-pressed={horizon === hours}
                disabled={
                  !context.summaries.some((s) => s.horizon_hours === hours)
                }
                onClick={() => setHorizon(hours)}
              >
                Next {hours} hours
              </button>
            ))}
          </div>
          {summary && (
            <>
              <p className="forecast-trend">
                {summary.outlook === "UNAVAILABLE"
                  ? "Comparison unavailable"
                  : summary.outlook.replaceAll("_", " ")}
              </p>
              <p className="source-caveat">
                Hourly coverage: {summary.available_hours}/{horizon} · PM2.5:{" "}
                {summary.pm25_hours}/{horizon} · CPCB: {summary.cpcb_hours}/
                {horizon}.{" "}
                {summary.coverage !== "complete" &&
                  "Partial or missing forecast; peaks use available hours only."}
              </p>
              <dl className="forecast-comparison">
                <div>
                  <dt>Current PM2.5</dt>
                  <dd>{quantity(currentPm)}</dd>
                </div>
                <div>
                  <dt>Forecast peak PM2.5</dt>
                  <dd>{quantity(summary.max_pm25)}</dd>
                </div>
                <div>
                  <dt>Peak expected</dt>
                  <dd>
                    {summary.peak_at ? time(summary.peak_at) : "Not supplied"}
                    {summary.peak_basis === "ind_cpcb" ? " (CPCB AQI)" : ""}
                  </dd>
                </div>
                <div>
                  <dt>Forecast peak PM10</dt>
                  <dd>{quantity(summary.max_pm10)}</dd>
                </div>
                <div>
                  <dt>Current CPCB AQI</dt>
                  <dd>{currentCpcb?.value ?? "Not supplied"}</dd>
                </div>
                <div>
                  <dt>Forecast worst CPCB AQI</dt>
                  <dd>
                    {summary.max_cpcb_aqi ?? "Not supplied"}
                    {summary.worst_category
                      ? ` · ${summary.worst_category}`
                      : ""}
                  </dd>
                </div>
              </dl>
              {summary.max_cpcb_aqi == null && (
                <p className="source-caveat">
                  CPCB index unavailable. Other AQI scales are not substituted.
                </p>
              )}
              {summary.delta_pm25_vs_current && (
                <p className="source-caveat">
                  Peak PM2.5 change: {quantity(summary.delta_pm25_vs_current)}
                  {summary.relative_pm25_change_percent != null
                    ? ` (${summary.relative_pm25_change_percent.toFixed(1)}%)`
                    : ""}
                  .
                </p>
              )}
              <p className="source-caveat">{summary.comparison_note}</p>
              {current && (
                <p className="source-caveat">
                  Current AQ valid at {time(current.observed_at)} ·{" "}
                  {context.current_source_status.status.replaceAll("_", " ")}
                </p>
              )}
            </>
          )}
          <p className="source-caveat">{context.provider_status.message}</p>
          <p className="satellite-disclaimer">
            {context.independence_note} Forecasts do not establish that a
            reported event will cause future pollution.
          </p>
          <details className="source-details">
            <summary>Forecast source, timing and rules</summary>
            <p>
              {context.provenance.method} · {context.provenance.note}
            </p>
            <p>
              Retrieved:{" "}
              {context.retrieved_at
                ? `${time(context.retrieved_at)} (${context.retrieved_at} UTC offset retained)`
                : "Not retrieved"}
              . Issuance time: {context.issued_at ?? "Not supplied by provider"}
              .
            </p>
            <p>{context.temporal_note}</p>
            <p>
              Compared with current PM2.5, worsening means an increase of at
              least max(5 µg/m³, 10%); sharply worsening means at least max(25
              µg/m³, 50%). Improving means a fall of at least max(5 µg/m³, 10%);
              otherwise stable. Complete PM2.5 coverage and recent matching
              units are required. Descriptive thresholds, not regulatory
              categories or probabilities.
            </p>
            <p>
              Provider request: {context.provider_status.latency_ms} ms ·{" "}
              {context.policy_version}
            </p>
          </details>
        </>
      )}
      <p className="provider-credit">
        Google Maps · Includes data from Google Maps
        <br />
        Source: Includes air quality data from Google
      </p>
    </section>
  );
}

export function ForecastPanel({ lat, lng }: { lat: number; lng: number }) {
  const [context, setContext] = useState<ForecastContext | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api
      .forecast(lat, lng, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setContext(result);
          setError(false);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [lat, lng, retry]);
  return (
    <section
      className="forecast-panel"
      aria-label="Standalone provider forecast"
      aria-busy={loading}
    >
      {loading ? (
        <p role="status">Retrieving Google Air Quality forecast…</p>
      ) : (
        <ForecastOutlook context={context} />
      )}
      {error && (
        <p role="alert">
          Forecast connection unavailable. Current conditions and corroboration
          remain independent.
        </p>
      )}
      {!loading && (
        <button
          type="button"
          className="forecast-retry"
          onClick={() => {
            setLoading(true);
            setContext(null);
            setError(false);
            setRetry((n) => n + 1);
          }}
        >
          Refresh provider forecast
        </button>
      )}
    </section>
  );
}
