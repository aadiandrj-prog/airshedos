"use client";

import { useId, useState } from "react";
import type { components } from "../lib/api-schema";

type Forecast = components["schemas"]["AirQualityForecastContext"];
type Context = components["schemas"]["EnvironmentalContext"];
const hour = (at: string) => new Date(at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });

export function ForecastChart({ forecast }: { forecast: Forecast }) {
  const [metric, setMetric] = useState("pm25");
  const gradient = useId().replaceAll(":", "");
  const points = forecast.hourly_forecasts.map(h => ({ at: h.forecast_at,
    value: metric === "ind_cpcb" ? h.indexes.find(i => i.code === metric)?.value ?? null
      : h.pollutants.find(p => p.code === metric)?.concentration?.value ?? null,
    unit: metric === "ind_cpcb" ? "AQI" : h.pollutants.find(p => p.code === metric)?.concentration?.unit ?? "",
  }));
  const [selected, setSelected] = useState<number | null>(null);
  const usable = points.filter(p => p.value != null && Number.isFinite(p.value));
  const sameUnits = new Set(usable.map(p => p.unit)).size <= 1;
  const max = Math.max(1, ...usable.map(p => p.value!)) * 1.15;
  const start = Date.parse(forecast.window.start), end = Date.parse(forecast.window.end);
  const x = (at: string) => 48 + ((Date.parse(at) - start) / Math.max(1, end - start)) * 704;
  const y = (v: number) => 202 - v / max * 160;
  const segments: string[] = [];
  let path = "", previous = -Infinity;
  for (const point of points) {
    if (point.value == null || Date.parse(point.at) - previous > 3600000) {
      if (path) segments.push(path); path = "";
    }
    if (point.value != null) { path += `${path ? " L" : "M"}${x(point.at)},${y(point.value)}`; previous = Date.parse(point.at); }
  }
  if (path) segments.push(path);
  const active = selected == null ? usable[0] : points[selected];
  const unit = metric === "ind_cpcb" ? "AQI" : usable[0]?.unit === "MICROGRAMS_PER_CUBIC_METER" ? "µg/m³" : usable[0]?.unit ?? "";
  return <section className="air-chart-panel" aria-label="Hourly provider forecast">
    <div className="air-panel-heading"><div><p className="kicker">The next 24 hours</p><h3>An outlook, hour by hour.</h3></div><label>Chart metric<select value={metric} onChange={e => { setMetric(e.target.value); setSelected(null); }}><option value="pm25">PM2.5</option><option value="pm10">PM10</option><option value="ind_cpcb">CPCB AQI</option></select></label></div>
    {usable.length && sameUnits ? <>
      <p className="air-chart-reading" aria-live="polite">{active?.value?.toLocaleString("en-IN", { maximumFractionDigits: 1 }) ?? "—"} <span>{unit} · {active ? hour(active.at) + " IST" : ""}</span></p>
      <svg viewBox="0 0 800 250" role="img" aria-label={`${metric} hourly forecast. Gaps indicate missing hours. Exact values in the table below.`}>
        <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#7c3aed" stopOpacity=".23" /><stop offset="1" stopColor="#38bdf8" stopOpacity=".02" /></linearGradient></defs>
        {[0, .5, 1].map(t => <g key={t}><line x1="48" y1={y(max * t)} x2="752" y2={y(max * t)} stroke="#cbd5e1" strokeDasharray="4 6" /><text x="4" y={y(max * t) + 4} fill="#475569" fontSize="13">{Math.round(max * t)}</text></g>)}
        {segments.map((d, i) => { const ends = d.match(/[\d.-]+,[\d.-]+/g)!; return <g key={i}><path d={`${d} L${ends.at(-1)!.split(",")[0]},202 L${ends[0].split(",")[0]},202 Z`} fill={`url(#${gradient})`} /><path d={d} fill="none" stroke="#6d28d9" strokeWidth="3" /></g>; })}
        {points.map((p, i) => p.value == null ? null : <circle key={p.at} cx={x(p.at)} cy={y(p.value)} r={selected === i ? 6 : 3} fill={selected === i ? "#0369a1" : "#6d28d9"} onMouseEnter={() => setSelected(i)}><title>{hour(p.at)} IST: {p.value} {unit}</title></circle>)}
        {[0, 6, 12, 18, 24].map(h => <text key={h} x={48 + h / 24 * 704} y="236" textAnchor="middle" fill="#475569" fontSize="13">+{h}h</text>)}
      </svg>
      <label className="air-hour-select">Inspect a forecast hour<select value={selected ?? points.findIndex(p => p.value != null)} onChange={e => setSelected(Number(e.target.value))}>{points.map((p, i) => <option key={p.at} value={i}>{hour(p.at)} IST · {p.value == null ? "Not supplied" : `${p.value} ${unit}`}</option>)}</select></label>
      <details><summary>View hourly values as a table</summary><div className="air-table-wrap"><table><caption>Google provider forecast · {metric} · {unit}</caption><thead><tr><th scope="col">Valid time (IST)</th><th scope="col">Value</th></tr></thead><tbody>{points.map(p => <tr key={p.at}><th scope="row">{new Date(p.at).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" })} {hour(p.at)}</th><td>{p.value ?? "Not supplied"}</td></tr>)}</tbody></table></div></details>
    </> : <p className="air-help">{sameUnits ? "No usable hourly values for this metric. Other source cards may still be available." : "Source units differ; a combined chart is unavailable. Refer to source readings."}</p>}
    <p className="air-help">Google provider forecast, not measured history. Missing hours remain gaps. The 6/12/24-hour cards show window peaks; the curve shows hourly values.</p>
  </section>;
}

export function FireRadar({ context }: { context: Context }) {
  const [selected, setSelected] = useState<string | null>(null);
  const fires = context.fires ?? [], radius = context.fire_search_radius_km;
  const chosen = fires.find(f => f.source_id === selected) ?? fires[0];
  const position = (lat: number, lng: number) => {
    const phi = context.latitude * Math.PI / 180, other = lat * Math.PI / 180;
    const delta = (lng - context.longitude) * Math.PI / 180;
    return Math.atan2(Math.sin(delta) * Math.cos(other), Math.cos(phi) * Math.sin(other) - Math.sin(phi) * Math.cos(other) * Math.cos(delta));
  };
  return <div className="air-fire-radar"><div>
    <svg viewBox="0 0 360 360" role="img" aria-label={`Schematic of NASA fire detections within ${radius} kilometres of the query point. North is up. This is not a street map.`}>
      {[.33, .66, 1].map(r => <circle key={r} cx="180" cy="180" r={140 * r} fill={r === 1 ? "#f0f9ff" : "none"} stroke="#94a3b8" strokeDasharray="3 6" />).reverse()}
      <path d="M180 40V320M40 180H320" stroke="#cbd5e1" /><text x="180" y="23" textAnchor="middle" fill="#475569" fontSize="14">N</text><text x="340" y="185" fill="#475569" fontSize="14">E</text><text x="176" y="347" fill="#475569" fontSize="14">S</text><text x="8" y="185" fill="#475569" fontSize="14">W</text>
      <circle cx="180" cy="180" r="7" fill="#0369a1" /><circle cx="180" cy="180" r="13" fill="none" stroke="#0369a1" />
      {fires.map(f => { const bearing = position(f.latitude, f.longitude), distance = Math.min(1, f.distance_from_query_km / radius) * 140; return <circle key={f.source_id} cx={180 + Math.sin(bearing) * distance} cy={180 - Math.cos(bearing) * distance} r={chosen?.source_id === f.source_id ? 7 : 5} fill="#c2410c" stroke="white" strokeWidth="2"><title>{f.distance_from_query_km.toFixed(1)} km · {f.observed_at}</title></circle>; })}
    </svg><p className="air-help">Relative positions · {radius} km radius · blue point is the query centre. NASA detections only; no street map or sensor network.</p>
  </div><div>{fires.length ? <><label>Inspect a detection<select value={chosen?.source_id ?? ""} onChange={e => setSelected(e.target.value)}>{fires.map((f, i) => <option key={f.source_id} value={f.source_id}>Detection {i + 1} · {f.distance_from_query_km.toFixed(1)} km</option>)}</select></label><p className="air-detection-distance">{chosen.distance_from_query_km.toFixed(1)}<span> km from query point</span></p><p className="air-help">Acquired {new Date(chosen.observed_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</p><p className="air-help">Satellite: {chosen.satellite ?? "Not supplied"} · confidence class: {chosen.confidence ?? "Not supplied"}. A class is not a probability.</p></> : <p className="air-help">{context.fires === null ? "Detection source unavailable. No points have been invented." : "No detections returned in this search window. This does not rule out pollution."}</p>}</div></div>;
}
