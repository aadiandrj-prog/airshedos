"use client";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import type { components } from "../lib/api-schema";

type Overview = components["schemas"]["Overview"];
type Measurement = components["schemas"]["Measurement"];
type Source = components["schemas"]["EnvironmentalSourceStatus"];
const areas = [["delhi", "New Delhi"], ["gurugram", "Gurugram"], ["noida", "Noida"]];
const units: Record<string, string> = { MICROGRAMS_PER_CUBIC_METER: "µg/m³", PARTS_PER_BILLION: "ppb", DEGREES_CELSIUS: "°C", CELSIUS: "°C", KILOMETERS_PER_HOUR: "km/h", METERS_PER_SECOND: "m/s", MILLIBARS: "mbar", MEGAWATTS: "MW" };
const quantity = (m?: Measurement | null) => m ? `${m.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${units[m.unit] ?? m.unit}` : "Not supplied";
const time = (v?: string | null) => v ? new Date(v).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }) + " IST" : "Not supplied";
const labels: Record<string, string> = { live: "Retrieved", cached: "Cached", unavailable: "Unavailable", error: "Provider error", not_configured: "Not connected" };
function Status({ source }: { source: Source }) {
  return <div className="air-source"><span className="status-chip">{labels[source.status]}</span><p>{source.message}</p><p>Retrieved: {time(source.retrieved_at)}</p></div>;
}
function GoogleCredit() { return <div className="air-attribution"><Image src="/attribution/google-maps.svg" alt="Google Maps" width={96} height={18} unoptimized /><small>Source: Includes air quality data from Google</small></div>; }

export function AirOverview() {
  const [area, setArea] = useState("gurugram");
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!data) return;
    const expire = () => { if (Date.now() >= Date.parse(data.expires_at)) { setData(null); setError("These readings have expired. Load current conditions again."); } };
    const timer = setTimeout(expire, Math.max(0, Date.parse(data.expires_at) - Date.now()));
    document.addEventListener("visibilitychange", expire);
    return () => { clearTimeout(timer); document.removeEventListener("visibilitychange", expire); };
  }, [data]);
  async function load() {
    controller.current?.abort();
    const request = new AbortController(); controller.current = request;
    const current = ++sequence.current;
    setLoading(true); setError(""); setData(null);
    try {
      const response = await fetch(`/api/explore/${area}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}", cache: "no-store", signal: AbortSignal.any([request.signal, AbortSignal.timeout(75000)]) });
      if (!response.ok) throw new Error(response.status === 429 ? "The shared overview request limit has been reached. Please try later." : "Local conditions could not be loaded. Please try again; reporting remains separate.");
      const result = await response.json() as Overview;
      if (current === sequence.current && !request.signal.aborted) {
        if (result.area.id !== area || Date.parse(result.expires_at) <= Date.now()) throw new Error("The returned readings have expired. Please reload.");
        setData(result);
      }
    } catch (e) { if (!request.signal.aborted && current === sequence.current) setError(e instanceof Error ? e.message : "Overview unavailable."); }
    finally { if (current === sequence.current) setLoading(false); }
  }
  const aq = data?.context.air_quality;
  const index = aq?.indexes.find(i => i.code === "ind_cpcb") ?? aq?.indexes[0];
  const weather = data?.context.weather;
  const fires = data?.context.fires;
  return <>
    <section className="air-intro"><p className="kicker">Environmental overview</p><h1>The air around you,<br />with context.</h1><p>Explore current conditions at a representative point in a supported area. No account or report required.</p>
      <form className="air-controls" onSubmit={e => { e.preventDefault(); void load(); }}>
        <label htmlFor="air-area">Choose an area<select id="air-area" value={area} onChange={e => { controller.current?.abort(); ++sequence.current; setArea(e.target.value); setData(null); setError(""); setLoading(false); }}>{areas.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <button className="pilot-button" disabled={loading}>{loading ? "Checking sources…" : "View current conditions"}</button>
      </form><p className="air-help">Delhi NCR preview · area points, not city-wide averages or your device location. Readings refresh on request within shared usage limits.</p>
    </section>
    {loading && <p role="status" className="air-message">Retrieving independent sources. A sleeping demo server may take about a minute to start.</p>}
    {error && <p role="alert" className="air-message">{error}</p>}
    {!data && !loading && !error && <section className="air-empty"><h2>Know the conditions before you report.</h2><p>Load air quality, weather, nearby fire detections and a separate provider forecast for your selected area.</p><p>No satellite imagery or automatic location tracking is used in this overview.</p></section>}
    {data && <div className="air-results" aria-live="polite">
      <div className="air-result-heading"><h2>{data.area.name}</h2><p>Checked {time(data.context.generated_at)} · expires {time(data.expires_at)}</p></div>
      <div className="air-grid">
        <section className="air-card air-aqi"><p className="kicker">Air quality</p><h3>{index?.display_name ?? "Current AQI"}</h3><p className="air-reading">{index?.value?.toLocaleString("en-IN") ?? "—"}</p><p>{index?.category ?? "No usable index returned"}</p>{index && <p>Index: {index.code} · dominant pollutant: {index.dominant_pollutant ?? "Not supplied"}</p>}
          <Status source={data.context.source_statuses.air_quality} /><p className="air-help">Observation: {time(aq?.observed_at)}. Provider estimate, not a new monitoring station.</p><GoogleCredit />
        </section>
        <section className="air-card"><p className="kicker">Weather</p><h3>Temperature & wind</h3><p className="air-reading">{quantity(weather?.temperature)}</p><dl className="air-facts"><div><dt>Wind</dt><dd>{quantity(weather?.wind_speed)} {weather?.wind_cardinal ?? ""}</dd></div><div><dt>Relative humidity</dt><dd>{weather?.relative_humidity_percent != null ? `${weather.relative_humidity_percent}%` : "Not supplied"}</dd></div><div><dt>Pressure</dt><dd>{quantity(weather?.sea_level_pressure)}</dd></div></dl>
          <Status source={data.context.source_statuses.weather} /><p className="air-help">Observation: {time(weather?.observed_at)}</p><div className="air-attribution"><Image src="/attribution/google-maps.svg" alt="Google Maps" width={96} height={18} unoptimized /><small>Weather data</small></div>
        </section>
        <section className="air-card air-wide"><p className="kicker">Pollutant measurements</p><h3>Readings in their source units</h3><div className="air-pollutants">{aq?.pollutants.length ? aq.pollutants.map(p => <div key={p.code}><strong>{p.name ?? p.code}</strong><span>{quantity(p.concentration)}</span></div>) : <p>Pollutant concentrations are unavailable for this response.</p>}</div><GoogleCredit /></section>
        <section className="air-card air-wide"><p className="kicker">Separate provider forecast</p><h3>Next 6, 12 and 24 hours</h3><div className="air-horizons">{([6, 12, 24] as const).map(h => { const s = data.forecast.summaries.find(v => v.horizon_hours === h); return <div key={h}><h4>Next {h} hours</h4><strong>{quantity(s?.max_pm25)}</strong><p>Peak PM2.5 in this window</p><p>Worst CPCB AQI: {s?.max_cpcb_aqi ?? "Not supplied"}</p><p>Coverage: {s?.available_hours ?? 0}/{h} hours · {s?.coverage ?? "none"}</p></div>; })}</div>
          <Status source={data.forecast.provider_status} /><p className="air-help">Window peaks, not readings at the end of each window. Partial coverage can miss a higher peak. Issuance time: {time(data.forecast.issued_at)}.</p><p className="air-help">{data.forecast.independence_note}</p><GoogleCredit />
        </section>
        <section className="air-card air-wide"><p className="kicker">NASA FIRMS · {data.context.fire_dataset}</p><h3>Nearby active-fire detections</h3><p className="air-reading">{fires == null ? "—" : data.returned_fire_count}</p><p>Returned within {data.context.fire_search_radius_km} km · {data.context.fire_window_days}-day search window</p>
          <Status source={data.context.source_statuses.fires} />
          {fires?.length === 0 && <p>No nearby detections returned for this window. This does not rule out pollution.</p>}
          {!!fires?.length && <ul className="air-fire-list">{fires.map(f => <li key={f.source_id}><strong>{f.instrument ?? "Satellite detection"}</strong><span>{f.distance_from_query_km.toFixed(1)} km from area point · acquired {time(f.observed_at)}</span><span>{f.latitude.toFixed(3)}°, {f.longitude.toFixed(3)}° · radiative power {quantity(f.fire_radiative_power)}</span></li>)}</ul>}
          {data.fires_truncated && <p>Showing the first 50 returned detections.</p>}<p className="air-help">Satellite fire detections cannot identify a local source or prove a legal violation. Source: NASA LANCE / FIRMS.</p>
        </section>
      </div><p className="air-help">{data.notice}</p>
    </div>}
    <section className="air-report"><h2>Noticed something nearby?</h2><p>Environmental context is separate from reporting. Share what you observed and track your own report privately.</p><Link className="pilot-button secondary" href="/resident/reports/new">Report a concern</Link></section>
    <footer className="air-help"><Link href="/privacy">Privacy</Link> · <Link href="/terms">Terms of use</Link></footer>
  </>;
}
