"use client";
import { useState } from "react";
import type { components } from "../../lib/api-schema";
import { authorityRequest } from "../../lib/authority-client";
import { displayedTime } from "../../lib/resident-client";
import { useDeadline } from "./expiry";

type Live = { air_quality: components["schemas"]["AirQualityObservation"] | null;
  weather: components["schemas"]["MeteorologicalObservation"] | null;
  forecast: components["schemas"]["AirQualityForecastContext"]; expires_at: string };
export function ReviewerLiveContext({ unitId, caseId }: { unitId: string; caseId: string }) {
  const [data, setData] = useState<Live | null>(null); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  useDeadline(data?.expires_at, () => { setData(null); setMessage("Live context expired. Request again if useful."); });
  return <details><summary>Optional live Google context and separate forecast</summary>
    <p>Volatile context is not saved evidence. The forecast shares a provider ecosystem with current AQ and supplies no extra corroboration vote. 6/12/24-hour summaries are peaks within each window.</p>
    <button type="button" disabled={busy} onClick={async () => { setBusy(true); setMessage("Loading optional context…"); setData(null);
      try { const value: Live = await (await authorityRequest(unitId,`cases/${caseId}/live-context`,{ method:"POST",body:"{}" })).json(); setData(value); setMessage(value.air_quality || value.weather || value.forecast.summaries.length ? "Optional context loaded." : "No live context is available. Saved review remains usable."); }
      catch (failure) { setMessage((failure as Error).message); } finally { setBusy(false); }
    }}>Load live context and forecast</button><p role="status">{message}</p>
    {data && <><p>Content expires {displayedTime(data.expires_at)}.</p>
      {data.air_quality && <section><h3>Current Google Air Quality</h3><p>Observed {displayedTime(data.air_quality.observed_at)}; retrieved {displayedTime(data.air_quality.retrieved_at)}.</p>
        <ul>{data.air_quality.indexes.map((i) => <li key={i.code}>{i.display_name ?? i.code} ({i.code}): {i.value ?? "Unavailable"} {i.category}</li>)}</ul><p>Includes air quality data from Google.</p></section>}
      {data.weather && <section><h3>Current Google Weather</h3><p>Observed {displayedTime(data.weather.observed_at)}; retrieved {displayedTime(data.weather.retrieved_at)}.</p><p>Temperature {data.weather.temperature?.value ?? "Unavailable"} {data.weather.temperature?.unit}. Source: Google Maps Weather.</p></section>}
      <section><h3>Google forecast — separate outlook</h3><p>Provider state: {data.forecast.provider_status.status}. Issuance time {data.forecast.issued_at ? displayedTime(data.forecast.issued_at) : "not supplied by provider"}.</p>
        <ul>{data.forecast.summaries.map((s) => <li key={s.horizon_hours}>Next {s.horizon_hours} hours — window peak PM2.5 {s.max_pm25?.value ?? "Unavailable"} {s.max_pm25?.unit}; peak at {s.peak_at ? displayedTime(s.peak_at) : "unknown"}; coverage {s.coverage}.</li>)}</ul><p>Includes air quality forecast data from Google. Provider output, not a custom AirshedOS model.</p></section>
    </>}
  </details>;
}
