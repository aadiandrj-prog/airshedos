"use client";
import { useEffect, useState } from "react";
import { residentRequest, displayedTime } from "../../lib/resident-client";
import type { components } from "../../lib/api-schema";

export function LocalContext({ latitude, longitude, reportId }: { latitude: string; longitude: string; reportId?: string }) {
  const [data, setData] = useState<components["schemas"]["LocalContext"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [loadedPlace, setLoadedPlace] = useState("");
  const place = `${reportId ?? "draft"}: ${latitude}, ${longitude}`;
  const current = loadedPlace === place ? data : null;
  useEffect(() => {
    if (!data) return;
    const timer = setTimeout(() => { setData(null); setMessage("Local context expired. Request it again if useful."); },
      Math.max(0, Date.parse(data.expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [data]);
  return <details><summary>Optional local AQ and weather context</summary>
    <p>General conditions at the coordinates you choose cannot identify a pollution source or verify this report. Context is separate from submission and is not saved in your case.</p>
    {!reportId && <p>Save your report first. Optional source context can then be requested from its saved detail.</p>}
    <button type="button" disabled={busy} onClick={async () => {
      if (!reportId) { setMessage("No local context is available. You can still submit your report."); return; }
      if (!latitude || !longitude || !Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude))) {
        setMessage("Enter reported coordinates first, or submit without local context."); return;
      }
      setBusy(true); setMessage("Loading optional context…");
      try {
        const response = await residentRequest("context", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ report_id:reportId }) });
        const value = await response.json(); setData(value); setLoadedPlace(place);
        setMessage(value.air_quality || value.weather ? "Optional context loaded." : "No local context is available. Your saved report remains available.");
      } catch { setData(null); setMessage("Local context unavailable. Your saved report remains available."); }
      finally { setBusy(false); }
    }}>Load optional context</button>
    <p role="status">{message}</p>
    {data && loadedPlace !== place && <p>Coordinates changed. Load context again for the current reported place.</p>}
    {current?.air_quality && <section><h3>Google Air Quality</h3>
      <p>Observed {displayedTime(current.air_quality.observed_at)}; retrieved {displayedTime(current.air_quality.retrieved_at)}.</p>
      <ul>{current.air_quality.indexes.map((item) => <li key={item.code}>{item.display_name ?? item.code} ({item.code}): {item.value ?? "Unavailable"} {item.category ?? ""}</li>)}</ul>
      <p>Source: Includes air quality data from Google.</p>
    </section>}
    {current?.weather && <section><h3>Google Weather</h3>
      <p>Observed {displayedTime(current.weather.observed_at)}; retrieved {displayedTime(current.weather.retrieved_at)}.</p>
      <p>Temperature: {current.weather.temperature ? `${current.weather.temperature.value} ${current.weather.temperature.unit}` : "Unavailable"}.</p>
      <p>Source: Google Maps Weather.</p>
    </section>}
  </details>;
}
