"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { loadMaps, MAP_FAILURE } from "../lib/maps";
import { drawPlume, offsetPoint, PLUME_EXTENT_M, scenarioIssue, type PlumeScenario } from "../lib/plume";
import type { components } from "../lib/api-schema";
type Overview = components["schemas"]["Overview"];
const enabled = process.env.NEXT_PUBLIC_EXPLORE_MAPS_ENABLED === "1";

export function ExploreMap({ data, scenario, showScenario }: { data: Overview; scenario: PlumeScenario; showScenario: boolean }) {
  const root = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const layer = useRef<google.maps.Data | null>(null);
  const overlay = useRef<google.maps.GroundOverlay | null>(null);
  const info = useRef<google.maps.InfoWindow | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(enabled ? "" : "Google Map is not enabled in this deployment. The forecast and detection list remain available.");
  const [firesVisible, setFiresVisible] = useState(true);
  const [message, setMessage] = useState("");
  const centre = useMemo(() => ({ lat: data.area.latitude, lng: data.area.longitude }), [data.area.latitude,data.area.longitude]);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const fail = () => { if (active) { setError("Google Map is unavailable. Check the browser Maps key or network; source readings and the detection list remain available."); setReady(false); } };
    window.addEventListener(MAP_FAILURE, fail);
    void loadMaps().then(() => {
      if (!active || !root.current) return;
      const instance = new google.maps.Map(root.current, {
        center: {lat:data.area.latitude,lng:data.area.longitude}, zoom:12,
        mapTypeControl:true, streetViewControl:false, fullscreenControl:true,
        zoomControl:true, keyboardShortcuts:true, gestureHandling:"cooperative",
      });
      map.current = instance; layer.current = new google.maps.Data({map:instance});
      info.current = new google.maps.InfoWindow();
      layer.current.setStyle(feature => {
        const kind = feature.getProperty("kind");
        return { icon:{path:google.maps.SymbolPath.CIRCLE,scale:kind === "source" ? 9 : 6,
          fillColor:kind === "fire" ? "#c2410c" : kind === "source" ? "#6d28d9" : "#0369a1",
          fillOpacity:1,strokeColor:"#ffffff",strokeWeight:2}, clickable:true, zIndex:kind === "source" ? 5 : 3 };
      });
      layer.current.addListener("click", (event: google.maps.Data.MouseEvent) => {
        const text=String(event.feature.getProperty("description") ?? "");
        setMessage(text);
        const content=document.createElement("p"); content.textContent=text; content.style.color="#0f172a";
        info.current?.setContent(content); info.current?.setPosition(event.latLng); info.current?.open({map:instance});
      });
      instance.addListener("tilesloaded", () => { if(active) setMessage("Google Map ready. Panning does not fetch new air readings."); });
      setReady(true);
    }).catch(fail);
    return () => {
      active=false; window.removeEventListener(MAP_FAILURE, fail);
      overlay.current?.setMap(null); overlay.current=null; info.current?.close();
      if(layer.current) { google.maps.event.clearInstanceListeners(layer.current); layer.current.setMap(null); }
      if(map.current) google.maps.event.clearInstanceListeners(map.current);
      map.current=null; layer.current=null;
    };
  }, [data.area.latitude,data.area.longitude]);
  useEffect(() => {
    if (!ready || !layer.current) return;
    const l=layer.current; l.forEach(f=>l.remove(f));
    l.add({geometry:new google.maps.Data.Point(centre),properties:{kind:"query",description:"Rounded query point. Provider readings refer to this point, not the current map viewport."}});
    if(firesVisible) for(const f of data.context.fires ?? []) l.add({
      geometry:new google.maps.Data.Point({lat:f.latitude,lng:f.longitude}),
      properties:{kind:"fire",description:`NASA FIRMS thermal detection · ${f.distance_from_query_km.toFixed(1)} km from query point · acquired ${f.observed_at}. Not source attribution.`},
    });
    if(showScenario && !scenarioIssue(scenario) && Math.abs(centre.lat)<=80) l.add({
      geometry:new google.maps.Data.Point(offsetPoint(centre.lat,centre.lng,scenario.sourceEastM,scenario.sourceNorthM)),
      properties:{kind:"source",description:"Hypothetical scenario source. Its position, release and height are assumptions, not a detected or reported source."},
    });
  },[ready,data,scenario,showScenario,firesVisible,centre]);
  useEffect(() => {
    overlay.current?.setMap(null); overlay.current=null;
    if(!ready || !map.current || !showScenario || scenarioIssue(scenario) || Math.abs(centre.lat)>80) return;
    const canvas=document.createElement("canvas"); drawPlume(canvas,scenario);
    const sw=offsetPoint(centre.lat,centre.lng,-PLUME_EXTENT_M,-PLUME_EXTENT_M);
    const ne=offsetPoint(centre.lat,centre.lng,PLUME_EXTENT_M,PLUME_EXTENT_M);
    const ground=new google.maps.GroundOverlay(canvas.toDataURL("image/png"),{south:sw.lat,west:sw.lng,north:ne.lat,east:ne.lng},{clickable:false,opacity:.85});
    ground.setMap(map.current!); overlay.current=ground;
    return () => { ground.setMap(null); if(overlay.current===ground) overlay.current=null; };
  },[ready,scenario,showScenario,centre]);
  return <div className="live-map-panel">
    <div className="air-map-controls"><button type="button" className="secondary" disabled={!ready} onClick={()=>{map.current?.panTo(centre);map.current?.setZoom(12);}}>Recenter map</button><label><input type="checkbox" checked={firesVisible} onChange={e=>setFiresVisible(e.target.checked)}/>NASA detections</label></div>
    <div ref={root} className="air-google-map" role="region" aria-label="Interactive Google Map of the query point, NASA detections and optional illustrative plume" tabIndex={0}/>
    {error ? <p role="status" className="air-map-status">{error}</p> : !ready ? <p role="status">Loading Google Map…</p> : <p role="status" className="air-map-status">{message || "Google Map loaded. Pan, zoom or select a marker."}</p>}
    <div className="map-layer-key"><span><i className="query-dot"/>Query point</span><span><i className="fire-dot"/>NASA thermal detection</span>{showScenario && <span><i className="scenario-dot"/>Hypothetical source / plume</span>}</div>
    <p className="air-help">The basemap is Google Maps. Readings stay attached to the selected query point; panning does not fetch readings or identify a pollution source. NASA LANCE / FIRMS supplies detection points. Purple plume colours are an illustrative calculation, not satellite observations.</p>
    {Math.abs(centre.lat)>80 && showScenario && <p className="air-help">The geographic plume overlay is unavailable above 80° latitude; the illustrative local-grid calculation remains available below.</p>}
  </div>;
}
