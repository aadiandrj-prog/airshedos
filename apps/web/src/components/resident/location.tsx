"use client";
import { useEffect, useRef, useState } from "react";
import { loadMaps } from "../../lib/maps";

export function ReportedLocation({ latitude, longitude, onChange, disabled }: {
  latitude: string; longitude: string; onChange: (lat: string, lng: string) => void; disabled: boolean;
}) {
  const [message, setMessage] = useState("");
  const [showMap, setShowMap] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const changed = useRef(onChange);
  useEffect(() => { changed.current = onChange; }, [onChange]);
  useEffect(() => {
    if (!showMap || disabled || !root.current || process.env.NEXT_PUBLIC_PILOT_MAPS_APPROVED !== "1") return;
    let stopped = false; let listener: google.maps.MapsEventListener | undefined;
    void loadMaps().then(() => {
      if (stopped || !root.current) return;
      const map = new google.maps.Map(root.current, { center: { lat: 28.61, lng: 77.21 }, zoom: 10,
        disableDefaultUI: true, zoomControl: true, gestureHandling: "cooperative" });
      listener = map.addListener("click", (event: google.maps.MapMouseEvent) => {
        if (!event.latLng) return;
        changed.current(event.latLng.lat().toFixed(6), event.latLng.lng().toFixed(6));
        setMessage("Map point selected as your reported location. It is not verified.");
      });
    }).catch(() => { if (!stopped) setMessage("Map unavailable. Enter coordinates manually; reporting still works."); });
    return () => { stopped = true; listener?.remove(); };
  }, [showMap, disabled]);
  return <fieldset disabled={disabled}><legend>02 · Reported coordinates</legend>
    <p className="resident-help">Approximate coordinates are acceptable. Enter them manually or choose a point. Device location and a map point are your declarations, not proof of where an event happened.</p>
    <div className="resident-columns">
      <label>Latitude<input required type="number" min="-90" max="90" step="any" inputMode="decimal" value={latitude} onChange={(e) => onChange(e.target.value, longitude)} /></label>
      <label>Longitude<input required type="number" min="-180" max="180" step="any" inputMode="decimal" value={longitude} onChange={(e) => onChange(latitude, e.target.value)} /></label>
    </div>
    <button className="secondary" type="button" onClick={() => {
      if (!navigator.geolocation) { setMessage("Location services unavailable. Enter coordinates manually."); return; }
      setMessage("Requesting device location with your permission…");
      navigator.geolocation.getCurrentPosition((position) => {
        onChange(position.coords.latitude.toFixed(6), position.coords.longitude.toFixed(6));
        setMessage("Device coordinates copied as your reported location. They do not verify the incident.");
      }, () => setMessage("Location access unavailable. Enter coordinates manually; reporting still works."),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 });
    }}>Use my device location (optional)</button>
    <button className="secondary" type="button" onClick={() => { setShowMap((value) => !value); if (process.env.NEXT_PUBLIC_PILOT_MAPS_APPROVED !== "1") setMessage("Map unavailable. Enter coordinates manually; reporting still works."); }}>{showMap ? "Hide optional map" : "Choose on an optional map"}</button>
    {showMap && <><p>Map view starts in the NCR. It sets no reported location until you select a point. You can pan elsewhere or use the fields above.</p><div ref={root} style={{ height: process.env.NEXT_PUBLIC_PILOT_MAPS_APPROVED === "1" ? 250 : undefined }} role="region" aria-label="Optional reported-location map" /></>}
    <p role="status">{message}</p>
  </fieldset>;
}
