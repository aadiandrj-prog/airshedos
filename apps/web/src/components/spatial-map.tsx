"use client";

import { useEffect, useRef, useState } from "react";
import { EmptyState, LoadingState } from "./ui";
import { loadMaps, MAP_FAILURE } from "@/lib/maps";

export type MapPoint = {
  id: string; role: "REPORT" | "INCIDENT" | "FIRE_DETECTION" | "PROBE";
  lat: number; lng: number; label: string;
};
const glyph = { REPORT: "R", INCIDENT: "D", FIRE_DETECTION: "F", PROBE: "P" };
export function SpatialMap({ points, selectedId, onSelect }: {
  points: MapPoint[]; selectedId: string; onSelect: (id: string) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const markers = useRef<{ marker: google.maps.marker.AdvancedMarkerElement; point: MapPoint; badge: HTMLElement }[]>([]);
  const onSelectRef = useRef(onSelect);
  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  useEffect(() => {
    let active = true;
    let failed = false;
    let listener: google.maps.MapsEventListener | undefined;
    const fail = () => { failed = true; if (active) setStatus("unavailable"); };
    window.addEventListener(MAP_FAILURE, fail);
    const timer = setTimeout(fail, 12000);
    loadMaps().then(async () => {
      const { Map } = await google.maps.importLibrary("maps") as google.maps.MapsLibrary;
      await google.maps.importLibrary("marker");
      if (!active || failed || !element.current) return;
      map.current = new Map(element.current, {
        center: { lat: 28.4595, lng: 77.0266 }, zoom: 12, colorScheme: "DARK",
        mapId: process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID",
        streetViewControl: false, mapTypeControl: false, fullscreenControl: false,
        gestureHandling: "cooperative", maxZoom: 17, clickableIcons: false,
      });

      listener = map.current.addListener("tilesloaded", () => {
        if (active && !failed) { clearTimeout(timer); setStatus("ready"); }
      });
    }).catch(fail);
    return () => {
      active = false; clearTimeout(timer); listener?.remove();
      window.removeEventListener(MAP_FAILURE, fail);
      markers.current.forEach(({ marker }) => { marker.map = null; });
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (status !== "ready" || !map.current) return;
    const bounds = new google.maps.LatLngBounds();
    markers.current = points.map((point) => {
      const badge = document.createElement("span");
      badge.className = `spatial-marker ${point.role.toLowerCase()}`;
      badge.textContent = glyph[point.role];
      const marker = new google.maps.marker.AdvancedMarkerElement({
        map: map.current, position: { lat: point.lat, lng: point.lng },
        title: point.label, gmpClickable: true,
      });
      marker.append(badge);
      marker.addEventListener("gmp-click", () => onSelectRef.current(point.id));
      bounds.extend({ lat: point.lat, lng: point.lng });
      return { marker, point, badge };
    });
    if (points.length > 1) map.current.fitBounds(bounds, 48);
    else if (points[0]) {
      map.current.setCenter({ lat: points[0].lat, lng: points[0].lng });
      map.current.setZoom(13);
    }
    return () => {
      markers.current.forEach(({ marker }) => { marker.map = null; marker.remove(); });
      markers.current = [];
    };
  }, [points, status]);
  useEffect(() => {
    markers.current.forEach(({ marker, point, badge }) => {
      const selected = point.id === selectedId;
      badge.classList.toggle("selected", selected);
      marker.setAttribute("aria-pressed", String(selected));
    });
  }, [selectedId, points, status]);
  return <section id="spatial-context" tabIndex={-1} className="spatial-map" aria-label="Selected workflow map">
    <div className="map-heading"><div><span className="eyebrow">Spatial context</span><h3>Selected location & nearby evidence</h3></div><span className="map-compass" aria-label="National Capital Region">NCR</span></div>
    <div className="spatial-map-canvas" ref={element} aria-label="Google operational map" hidden={status === "unavailable"} />
    {status === "loading" && <LoadingState>Loading Google map… Textual evidence and review remain available.</LoadingState>}
    {status === "unavailable" && <div role="status" className="map-unavailable"><EmptyState title="Map unavailable.">Use the location and evidence list below; case review still works.</EmptyState></div>}
    {status === "ready" && <p className="map-status">Google map loaded. <span>R Report · D Demo · F Fire detection · P Probe</span></p>}
    <div className="map-text-points" aria-label="Map locations in text">
      {points.map((point) => <button type="button" key={point.id} aria-pressed={selectedId === point.id} onClick={() => onSelect(point.id)}>
        <strong>{point.label}</strong><span>{point.lat.toFixed(4)}, {point.lng.toFixed(4)}</span>
      </button>)}
    </div>
  </section>;
}
