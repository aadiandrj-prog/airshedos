"use client";
import Link from "next/link";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import type { components } from "../lib/api-schema";
import { FireRadar, ForecastChart } from "./air-visuals";
import { PlumeWorkbench } from "./plume-workbench";

type Overview = components["schemas"]["Overview"];
type Measurement = components["schemas"]["Measurement"];
type Source = components["schemas"]["EnvironmentalSourceStatus"];
type Point = { latitude: number; longitude: number; accuracy: number };
const areas = [["delhi", "New Delhi"], ["gurugram", "Gurugram"], ["noida", "Noida"]];
const units: Record<string, string> = { MICROGRAMS_PER_CUBIC_METER: "µg/m³", PARTS_PER_BILLION: "ppb", DEGREES_CELSIUS: "°C", CELSIUS: "°C", KILOMETERS_PER_HOUR: "km/h", METERS_PER_SECOND: "m/s", MILLIBARS: "mbar", MEGAWATTS: "MW" };
const quantity = (m?: Measurement | null) => m ? `${m.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${units[m.unit] ?? m.unit}` : "Not supplied";
const time = (v?: string | null) => v ? new Date(v).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }) + " IST" : "Not supplied";
const labels: Record<string, string> = { live: "Retrieved", cached: "Cached", unavailable: "Unavailable", error: "Provider error", not_configured: "Not connected" };
function Status({ source }: { source: Source }) {
  return <div className="air-source"><span className="status-chip">{labels[source.status]}</span><p>{source.message}</p><p>Retrieved: {time(source.retrieved_at)}</p></div>;
}
function GoogleCredit({ weather = false }: { weather?: boolean }) { return <div className="air-attribution"><Image src="/attribution/google-maps.svg" alt="Google Maps" width={96} height={18} unoptimized /><small>{weather ? "Weather data" : "Source: Includes air quality data from Google"}</small></div>; }

export function AirOverview({ embedded = false }: { embedded?: boolean }) {
  const [area, setArea] = useState("gurugram");
  const [point, setPoint] = useState<Point | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState("");
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  useEffect(() => () => { controller.current?.abort(); ++sequence.current; }, []);
  useEffect(() => {
    if (!data) return;
    const expire = () => { if (Date.now() >= Date.parse(data.expires_at)) { setData(null); setError("These readings have expired. Load current conditions again."); } };
    const timer = setTimeout(expire, Math.max(0, Date.parse(data.expires_at) - Date.now()));
    document.addEventListener("visibilitychange", expire);
    return () => { clearTimeout(timer); document.removeEventListener("visibilitychange", expire); };
  }, [data]);
  function reset() { controller.current?.abort(); ++sequence.current; setData(null); setError(""); setLoading(false); setLocating(false); }
  function locate() {
    reset(); const current = sequence.current; setPoint(null); if (area === "nearby") setArea("gurugram"); setLocationMessage("");
    if (!navigator.geolocation) { setLocationMessage("Location services are unavailable. Choose an area instead."); return; }
    setLocating(true); setLocationMessage("Requesting location permission…");
    navigator.geolocation.getCurrentPosition(position => {
      if (current !== sequence.current) return;
      const { latitude, longitude, accuracy } = position.coords;
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
        setLocating(false); setLocationMessage("No valid location was returned. Choose an area instead."); return;
      }
      setPoint({ latitude: Math.round(latitude * 200) / 200, longitude: Math.round(longitude * 200) / 200, accuracy });
      setArea("nearby"); setLocating(false);
      setLocationMessage(`Approximate location ready. Device-reported accuracy: ${Number.isFinite(accuracy) ? Math.round(accuracy) + " metres" : "unknown"}. Select View current conditions to fetch readings.`);
    }, () => { if (current === sequence.current) { setLocating(false); setLocationMessage("Location access was denied or unavailable. Choose an area instead; no readings were requested."); } },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  }
  async function load() {
    controller.current?.abort();
    const request = new AbortController(); controller.current = request;
    const current = ++sequence.current;
    setLoading(true); setError(""); setData(null);
    try {
      if (area === "nearby" && !point) throw new Error("Share a location or select an area first.");
      const response = await fetch(`/api/explore/${area}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(area === "nearby" ? { latitude: point!.latitude, longitude: point!.longitude } : {}), cache: "no-store", signal: AbortSignal.any([request.signal, AbortSignal.timeout(75000)]) });
      if (!response.ok) throw new Error(response.status === 429 ? "The shared overview request limit has been reached. Please try later." : "Local conditions could not be loaded. Please try again; reporting remains separate.");
      const result = await response.json() as Overview;
      if (current === sequence.current && !request.signal.aborted) {
        if (result.area.id !== area || Date.parse(result.expires_at) <= Date.now()) throw new Error("The returned readings have expired. Please reload.");
        if (area === "nearby" && (result.area.latitude !== point!.latitude || result.area.longitude !== point!.longitude)) throw new Error("The returned location did not match. Please retry.");
        setData(result);
      }
    } catch (e) { if (!request.signal.aborted && current === sequence.current) setError(e instanceof Error ? e.message : "Overview unavailable."); }
    finally { if (current === sequence.current) setLoading(false); }
  }
  const EmptyHeading = embedded ? "h3" : "h2";
  const aq = data?.context.air_quality;
  const index = aq?.indexes.find(i => i.code === "ind_cpcb") ?? aq?.indexes[0];
  const weather = data?.context.weather;
  const fires = data?.context.fires;
  const sources = data ? [["Air quality", data.context.source_statuses.air_quality], ["Weather", data.context.source_statuses.weather], ["NASA FIRMS", data.context.source_statuses.fires], ["Google forecast", data.forecast.provider_status]] as const : [];
  return <div className={embedded ? "air-experience embedded" : "air-experience"}>
    <section className="air-intro"><p className="kicker"><span className="brand-dot" /> Environmental intelligence · on your terms</p>{embedded ? <h2>A clearer view of your air.</h2> : <h1>The air around you,<br />with context.</h1>}<p>Air quality, weather and satellite fire detections, together. Choose an area or explore conditions near you.</p>
      <form className="air-controls" onSubmit={e => { e.preventDefault(); void load(); }}>
        <label htmlFor="air-area">Choose an area<select id="air-area" value={area} onChange={e => { reset(); setArea(e.target.value); setLocationMessage(""); if (e.target.value !== "nearby") setPoint(null); }}>{areas.map(([id, name]) => <option key={id} value={id}>{name}</option>)}{point && <option value="nearby">Near you · approximate location</option>}</select></label>
        <button className="pilot-button" disabled={loading || locating}>{loading ? "Checking sources…" : "View current conditions"}<span aria-hidden="true"> ↗</span></button>
        <button className="secondary air-location" type="button" onClick={locate} disabled={locating}>{locating ? "Locating…" : "Use my location"}<span aria-hidden="true"> ⌖</span></button>
      </form>
      <p className="air-help">Location is optional. Your query point is rounded before a Google/NASA lookup. No continuous tracking or saved location history. <Link href="/privacy">Privacy details</Link></p>
      {locationMessage && <p role="status" className="air-location-message">{locationMessage}</p>}
      {point && <button type="button" className="air-forget secondary" onClick={() => { reset(); setPoint(null); setArea("gurugram"); setLocationMessage("Device location cleared from this view."); }}>Clear my location</button>}
    </section>
    {loading && <p role="status" className="air-message">Checking environmental sources. A sleeping demo server may take about a minute to start.</p>}
    {error && <p role="alert" className="air-message">{error}</p>}
    {!data && !loading && !error && <section className="air-empty"><div className="air-orbit" aria-hidden="true"><span /><span /><span /><i /></div><div><p className="kicker">Your surroundings, brought into focus</p><EmptyHeading>Four sources of context.<br />One place to explore.</EmptyHeading><p>Readings appear after you request them. Source times, missing data and uncertainty stay visible.</p><div className="air-source-pills"><span>Air quality</span><span>Weather</span><span>NASA FIRMS</span><span>Provider forecast</span></div></div></section>}
    {data && <div className="air-results" aria-live="polite">
      <div className="air-result-heading"><div><p className="kicker">Your environmental briefing</p><h2>{data.area.name}</h2><p>{data.area.note}</p></div><p>Checked {time(data.context.generated_at)}<br />Expires {time(data.expires_at)}</p></div>
      <nav className="air-jump" aria-label="Environmental sections"><a href="#air-forecast">Forecast graph</a><a href="#air-map">Google Map & plume</a><a href="#air-conditions">Conditions</a><a href="#air-fires">Fire activity</a><a href="#air-sources">Sources & limits</a></nav>
      <div className="air-grid">
        <section id="air-forecast" className="air-card air-wide air-forecast"><ForecastChart forecast={data.forecast} /><h3>Next 6, 12 and 24 hours</h3><div className="air-horizons">{([6, 12, 24] as const).map(h => { const s = data.forecast.summaries.find(v => v.horizon_hours === h); return <div key={h}><h4>Next {h} hours</h4><strong>{quantity(s?.max_pm25)}</strong><p>Peak PM2.5 in this window</p><p>Worst CPCB AQI: {s?.max_cpcb_aqi ?? "Not supplied"}</p><p>Coverage: {s?.available_hours ?? 0}/{h} hours · {s?.coverage ?? "none"}</p>{s?.outlook && <p>Compared with current PM2.5: {s.outlook.toLowerCase().replaceAll("_", " ")}</p>}</div>; })}</div>
          <Status source={data.forecast.provider_status} /><p className="air-help">Window peaks, not readings at the end of each window. Partial coverage can miss a higher peak. Issuance time: {time(data.forecast.issued_at)}.</p><p className="air-help">{data.forecast.independence_note}</p><GoogleCredit />
        </section>
        <PlumeWorkbench data={data} />
        <section id="air-conditions" className="air-card air-aqi"><p className="kicker">01 / Air quality</p><h3>{index?.display_name ?? "Current AQI"}</h3><p className="air-reading">{index?.value?.toLocaleString("en-IN") ?? "—"}</p><p className="air-category">{index?.category ?? "No usable index returned"}</p>{index && <p className="air-help">Index: {index.code} · dominant pollutant: {index.dominant_pollutant ?? "Not supplied"}</p>}
          <Status source={data.context.source_statuses.air_quality} /><p className="air-help">Observation: {time(aq?.observed_at)}. Provider estimate, not a new monitoring station.</p><GoogleCredit />
        </section>
        <section className="air-card air-weather"><p className="kicker">02 / Weather</p><h3>Temperature & wind</h3><p className="air-reading">{quantity(weather?.temperature)}</p><dl className="air-facts"><div><dt>Wind</dt><dd>{quantity(weather?.wind_speed)} {weather?.wind_cardinal ?? ""}</dd></div><div><dt>Relative humidity</dt><dd>{weather?.relative_humidity_percent != null ? `${weather.relative_humidity_percent}%` : "Not supplied"}</dd></div><div><dt>Pressure</dt><dd>{quantity(weather?.sea_level_pressure)}</dd></div></dl>
          <Status source={data.context.source_statuses.weather} /><p className="air-help">Observation: {time(weather?.observed_at)}</p><GoogleCredit weather />
        </section>
        <section className="air-card air-wide"><p className="kicker">What is in the reading</p><h3>Pollutants, in their source units.</h3><div className="air-pollutants">{aq?.pollutants.length ? aq.pollutants.map(p => <div key={p.code}><strong>{p.name ?? p.code}</strong><span>{quantity(p.concentration)}</span></div>) : <p>Pollutant concentrations are unavailable for this response.</p>}</div><GoogleCredit /></section>
        <section id="air-fires" className="air-card air-wide"><p className="kicker">03 / NASA FIRMS · {data.context.fire_dataset}</p><div className="air-panel-heading"><div><h3>Nearby active-fire detections</h3><p>Returned within {data.context.fire_search_radius_km} km · {data.context.fire_window_days}-day search window</p></div><p className="air-reading">{fires == null ? "—" : data.returned_fire_count}</p></div>
          <FireRadar context={data.context} /><Status source={data.context.source_statuses.fires} />
          {fires?.length === 0 && <p>No nearby detections returned for this window. This does not rule out pollution.</p>}
          {!!fires?.length && <details><summary>View detection list and acquisition times</summary><ul className="air-fire-list">{fires.map(f => <li key={f.source_id}><strong>{f.instrument ?? "Satellite detection"}</strong><span>{f.distance_from_query_km.toFixed(1)} km from query point · acquired {time(f.observed_at)}</span><span>{f.latitude.toFixed(3)}°, {f.longitude.toFixed(3)}° · radiative power {quantity(f.fire_radiative_power)}</span></li>)}</ul></details>}
          {data.fires_truncated && <p>Showing the first 50 returned detections.</p>}<p className="air-help">Satellite fire detections cannot identify a local source or prove a legal violation. Source: NASA LANCE / FIRMS.</p>
        </section>
        <section id="air-sources" className="air-card air-wide"><p className="kicker">04 / Transparency</p><h3>Know what is behind each number.</h3><div className="air-source-grid">{sources.map(([name, source]) => <div key={name}><strong>{name}</strong><Status source={source} /></div>)}</div><p className="air-help">{data.notice}</p><p className="air-help">Google AQ has a published 500 × 500m resolution. Weather can describe a wider area. Device coordinates do not establish measurement accuracy or identify a pollution source.</p><Link href="/methodology">Explore the methodology and source limits ↗</Link></section>
      </div>
    </div>}
    {!embedded && <><section className="air-report"><p className="kicker">From context to a concern</p><h2>Noticed something nearby?</h2><p>Environmental context is separate from reporting. Share what you observed and track your own report privately.</p><Link className="pilot-button secondary" href="/resident/reports/new">Report a concern</Link></section><footer className="air-legal"><Link href="/methodology">Methodology</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms of use</Link></footer></>}
  </div>;
}
