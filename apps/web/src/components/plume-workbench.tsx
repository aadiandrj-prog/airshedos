"use client";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";
import type { components } from "../lib/api-schema";
import { DEFAULT_PLUME, drawPlume, gaussianGround, scenarioIssue, type PlumeScenario } from "../lib/plume";
import { ExploreMap } from "./explore-map";
type Overview = components["schemas"]["Overview"];
const number = (n: number | null) => n == null ? "Unavailable" : n.toLocaleString("en-IN",{maximumFractionDigits:2});
function ScenarioProfile({ scenario, distance }: { scenario: PlumeScenario; distance: number }) {
  const id=useId().replaceAll(":","");
  const values=Array.from({length:81},(_,i)=>({offset:-1000+i*25,value:gaussianGround(scenario,distance,-1000+i*25)}));
  const peak=Math.max(1,...values.map(v=>v.value??0))*1.15;
  const path=values.map((v,i)=>`${i?"L":"M"}${40+i/80*520},${185-(v.value??0)/peak*145}`).join(" ");
  return <div className="scenario-profile"><h4>Gaussian crosswind graph</h4><p className="air-help">Hypothetical ground-level increment, {distance/1000} km downwind. This is not the Google forecast or measured PM2.5.</p>
    <svg viewBox="0 0 600 235" role="img" aria-label="Hypothetical Gaussian crosswind profile in micrograms per cubic metre; numerical values in the scenario table">
      <defs><linearGradient id={id} x2="0" y2="1"><stop stopColor="#6d28d9" stopOpacity=".28"/><stop offset="1" stopColor="#38bdf8" stopOpacity=".03"/></linearGradient></defs>
      {[0,.5,1].map(t=><g key={t}><line x1="40" x2="560" y1={185-t*145} y2={185-t*145} stroke="#cbd5e1" strokeDasharray="4 5"/><text x="2" y={189-t*145} fill="#475569" fontSize="12">{Math.round(t*peak)}</text></g>)}
      <path d={`${path}L560,185L40,185Z`} fill={`url(#${id})`}/><path d={path} fill="none" stroke="#6d28d9" strokeWidth="3"/>
      {[-1000,-500,0,500,1000].map(m=><text key={m} x={40+(m+1000)/2000*520} y="213" textAnchor="middle" fill="#475569" fontSize="12">{m}m</text>)}
    </svg><details><summary>View scenario values</summary><div className="air-table-wrap"><table><caption>Illustrative scenario only · µg/m³ increment</caption><thead><tr><th scope="col">Crosswind offset</th><th scope="col">Scenario increment</th></tr></thead><tbody>{[-1000,-500,-250,-100,0,100,250,500,1000].map(y=><tr key={y}><th scope="row">{y} m</th><td>{number(gaussianGround(scenario,distance,y))}</td></tr>)}</tbody></table></div></details>
  </div>;
}
function ScenarioCanvas({ scenario }: { scenario: PlumeScenario }) {
  const ref=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{if(ref.current)drawPlume(ref.current,scenario,180);},[scenario]);
  const toX=(m:number)=>50+(m+3000)/6000*500, toY=(m:number)=>30+(3000-m)/6000*500;
  return <div className="scenario-grid"><canvas ref={ref} aria-hidden="true"/><svg viewBox="0 0 600 560" role="img" aria-label="Illustrative plume on a six kilometre local coordinate grid. Purple point is a hypothetical source; north is up.">
    {[-2000,-1000,0,1000,2000].map(m=><g key={m}><path d={`M${toX(m)},30V530M50,${toY(m)}H550`} stroke="#cbd5e1" strokeDasharray="3 5"/><text x={toX(m)} y="552" textAnchor="middle" fill="#475569" fontSize="12">{m/1000}km E</text></g>)}
    <text x="300" y="19" textAnchor="middle" fill="#334155" fontSize="14">N ↑ · illustrative grid</text>
    <circle cx={toX(scenario.sourceEastM)} cy={toY(scenario.sourceNorthM)} r="8" fill="#6d28d9" stroke="white" strokeWidth="2"/>
    <text x={Math.min(410,Math.max(55,toX(scenario.sourceEastM)+12))} y={toY(scenario.sourceNorthM)-12} fill="#4c1d95" fontSize="13">Hypothetical source</text>
  </svg></div>;
}
export function PlumeWorkbench({ data }: { data: Overview }) {
  const [active,setActive]=useState(false);
  const [scenario,setScenario]=useState<PlumeScenario>({...DEFAULT_PLUME});
  const [distance,setDistance]=useState(1000);
  const [windCopied,setWindCopied]=useState(false);
  const issue=scenarioIssue(scenario);
  const weather=data.context.weather;
  const observedSpeed=weather?.wind_speed?.unit === "KILOMETERS_PER_HOUR" ? weather.wind_speed.value/3.6
    : weather?.wind_speed?.unit === "METERS_PER_SECOND" ? weather.wind_speed.value : null;
  const canCopy=observedSpeed!=null && observedSpeed<=15 && weather?.wind_from_degrees!=null;
  function change(key:keyof PlumeScenario,value:number) {setScenario(s=>({...s,[key]:value}));if(key==="windMps"||key==="windFromDeg")setWindCopied(false);}
  const control=(key:keyof PlumeScenario,label:string,min:number,max:number,step=1)=><label key={key}>{label}<span>{scenario[key]}</span><input type="range" aria-label={label} min={min} max={max} step={step} value={scenario[key]} onChange={e=>change(key,Number(e.target.value))}/></label>;
  return <section id="air-map" className="air-card air-wide plume-workbench" aria-label="Live Google Map and Gaussian plume scenario">
    <div className="air-panel-heading"><div><p className="kicker">Explore the area</p><h3>A map with room to investigate.</h3></div><span className="status-chip">Google Maps · NASA detections</span></div>
    <div className="plume-mode"><label><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Show illustrative Gaussian plume</label><p>Try a hypothetical release on the map. Source position, emissions and mixing are assumptions; this is not a detected plume, exposure estimate or forecast.</p></div>
    <ExploreMap data={data} scenario={scenario} showScenario={active}/>
    {active && <div className="scenario-content"><div className="scenario-banner"><strong>ILLUSTRATIVE SCENARIO · NOT OBSERVED POLLUTION</strong><p>Steady wind, flat terrain and a continuous inert tracer release. No buildings, terrain, deposition or chemistry. The assumed source is unrelated to NASA detections or resident reports.</p></div>
      <div className="scenario-columns"><div className="scenario-controls"><h4>Change the assumptions</h4>
        {control("emissionGps","Assumed release rate (g/s)",0,10,.1)}
        {control("windMps","Constant wind speed (m/s)",0,15,.1)}
        {control("windFromDeg","Wind comes from (degrees)",0,359)}
        {control("heightM","Effective release height (m)",10,150,5)}
        <button type="button" className="secondary" disabled={!canCopy} onClick={()=>{if(canCopy){setScenario(s=>({...s,windMps:Math.round(observedSpeed!*10)/10,windFromDeg:weather!.wind_from_degrees!}));setWindCopied(true);}}}>Copy retrieved surface wind</button>
        {windCopied ? <div className="air-attribution"><Image src="/attribution/google-maps.svg" alt="Google Maps" width={96} height={18} unoptimized/><small>Google Weather surface wind · observation {weather?.observed_at}. Rounded to 0.1 m/s and held constant here; it does not establish release-height wind or stability.</small></div> : <p className="air-help">Wind is hypothetical until you copy an available provider reading. Editing wind switches back to manual assumptions.</p>}
        <details><summary>Mixing and hypothetical source position</summary><p className="air-help">These linear spread assumptions are selected for illustration. No atmospheric stability class is inferred.</p>{control("lateralMPerKm","Horizontal spread at 1 km (m)",30,400,10)}{control("verticalMPerKm","Vertical spread at 1 km (m)",20,250,10)}{control("sourceEastM","Hypothetical source east offset (m)",-2000,2000,100)}{control("sourceNorthM","Hypothetical source north offset (m)",-2000,2000,100)}</details>
        <label>Inspect distance downwind<span>{distance/1000} km</span><input aria-label="Inspect distance downwind" type="range" min="100" max="3000" step="100" value={distance} onChange={e=>setDistance(Number(e.target.value))}/></label>
        <button type="button" className="secondary" onClick={()=>{setScenario({...DEFAULT_PLUME});setDistance(1000);setWindCopied(false);}}>Reset scenario</button>
      </div><div className="scenario-results">
        {issue ? <p role="status" className="scenario-unavailable">{issue}</p> : <><ScenarioCanvas scenario={scenario}/><div className="plume-scale"><span>0</span><i/><span>≥1,000 µg/m³</span></div><p className="air-help">Fixed logarithmic colour scale of hypothetical ground-level increment. Not AQI, probability, a safety boundary or measured ambient concentration. The first 50m downwind is excluded; upwind zero is a model assumption. The view is clipped to a 6km square; its edge is not a safety boundary.</p><ScenarioProfile scenario={scenario} distance={distance}/></>}
      </div></div>
      <details className="scenario-method"><summary>Equation, assumptions and limits</summary><p>At ground level with reflection: C = Q / (π u σy σz) × exp[−y²/(2σy²) − H²/(2σz²)]. Q is assumed g/s, u m/s and distances metres. Multiply g/m³ by 1,000,000 for µg/m³. σy and σz increase linearly with downwind distance using your chosen spread inputs. These spread settings are not calibrated local dispersion parameters.</p><p>No background pollutant reading is added. This browser-only educational calculation is not AERMOD, a validated local source model, the Google AQ forecast or our offline forecasting research. It provides no arrival time, health advice, incident proof or enforcement finding.</p><a href="https://www.epa.gov/sites/default/files/2015-05/documents/pepcourse-equations1-2.pdf">Gaussian equation reference: EPA training material ↗</a></details>
    </div>}
  </section>;
}
