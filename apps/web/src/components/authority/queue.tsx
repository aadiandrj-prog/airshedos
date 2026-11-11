"use client";
import { useDeadline } from "./expiry";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authorityRequest, reviewLabel, type Queue } from "../../lib/authority-client";
import { displayedTime } from "../../lib/resident-client";
import { loadMaps } from "../../lib/maps";

const mapsApproved = process.env.NEXT_PUBLIC_PILOT_MAPS_APPROVED === "1";

function QueueMap({ unitId, items }: { unitId: string; items: Queue["items"] }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null); const [error, setError] = useState(mapsApproved ? "" : "Map unavailable. The equivalent case list remains available below.");
  useEffect(() => {
    if (!mapsApproved) return;
    let active = true; const markers: google.maps.marker.AdvancedMarkerElement[] = [];
    void loadMaps().then(() => {
      if (!active || !root.current) return;
      const points = items.filter((item) => item.latitude != null && item.longitude != null);
      if (!points.length) return;
      const map = new google.maps.Map(root.current, { center: { lat: points[0].latitude!, lng: points[0].longitude! },
        zoom: 11, mapId: process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID", disableDefaultUI: true, zoomControl: true });
      const bounds = new google.maps.LatLngBounds();
      for (const point of points) {
        const position = { lat: point.latitude!, lng: point.longitude! }; bounds.extend(position);
        const marker = new google.maps.marker.AdvancedMarkerElement({ map, position, title: `Open pilot case ${point.id}` });
        marker.addListener("click", () => router.push(`/authority/cases/${point.id}?unit=${unitId}`)); markers.push(marker);
      }
      if (points.length > 1) map.fitBounds(bounds);
    }).catch(() => { if (active) setError("Map unavailable. The equivalent case list remains available below."); });
    return () => { active = false; for (const marker of markers) marker.map = null; };
  }, [items, unitId, router]);
  return <section className="optional-map" aria-label="Optional case map"><p>Resident-declared points for this filtered page only. No inferred jurisdiction or dispatch.</p>
    {error && <p role="status">{error}</p>}<div ref={root} aria-label="Map of this page of permitted cases" role="region" style={{ height: error ? undefined : 260 }} /></section>;
}
export function CaseQueue({ unitId }: { unitId: string }) {
  const [data, setData] = useState<Queue | null>(null); const [error, setError] = useState("");
  const [state, setState] = useState(""); const [assignment, setAssignment] = useState(""); const [q, setQ] = useState("");
  const [filters, setFilters] = useState(""); const [offset, setOffset] = useState(0); const [map, setMap] = useState(false);
  const [reload, setReload] = useState(0);
  const load = useCallback(async () => (await authorityRequest(unitId, `cases?limit=20&offset=${offset}${filters}`)).json(), [unitId, offset, filters]);
  useEffect(() => { let active = true; void load().then((value) => { if (active) { setData(value); setError(""); } })
    .catch((failure) => { if (active) { setData(null); setError(failure.message); } }); return () => { active = false; }; }, [load, reload]);
  useDeadline(data?.items.map((item) => item.content_expires_at).sort()[0], () => { setData(null); setMap(false); setError("Report content expired. Apply the filters again to load the current permitted queue."); });
  return <div className="resident-stack">
    <form className="queue-filters" onSubmit={(event) => { event.preventDefault(); const params = new URLSearchParams(); if (state) params.set("state", state);
      if (assignment) params.set("assignment", assignment); if (q.trim()) params.set("q", q.trim()); setData(null); setOffset(0); setFilters(params.size ? "&" + params.toString() : ""); setReload((value) => value + 1); }}>
      <label>Review state<select disabled={!data && !error} aria-label="Review state" value={state} onChange={(e) => setState(e.target.value)}><option value="">All review states</option>
        {["NEW", "UNDER_REVIEW", "ACKNOWLEDGED", "MONITORING", "CLOSED_NO_ACTION"].map((value) => <option key={value} value={value}>{reviewLabel(value)}</option>)}
      </select></label><label>Ownership<select disabled={!data && !error} aria-label="Ownership" value={assignment} onChange={(e) => setAssignment(e.target.value)}>
        <option value="">All permitted cases</option><option value="mine">Assigned to me</option><option value="unassigned">Unassigned to a reviewer</option>
      </select></label><label>Search report description<input disabled={!data && !error} value={q} maxLength={100} onChange={(e) => setQ(e.target.value)} /></label><button type="submit" disabled={!data && !error}>Apply queue filters</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p role="status">Loading the permitted queue…</p>}
    {data && <><p role="status">{data.total} matching cases in this unit. Showing {data.items.length} from offset {offset}.</p>
      <p className="queue-summary">{Object.entries(data.state_counts).map(([key, count]) => `${reviewLabel(key)}: ${count}`).join(" · ")}</p>
      {!!data.items.length && <button type="button" onClick={() => setMap(!map)}>{map ? "Hide optional case map" : "Show optional case map"}</button>}
      {map && <QueueMap unitId={unitId} items={data.items} />}
      <ol className="case-list" aria-label="Permitted case list">{data.items.map((item) => <li key={item.id}>
        <Link href={`/authority/cases/${item.id}?unit=${unitId}`}>Open case {item.id}</Link>
        <p>{item.reported_place ?? "Place label unavailable"} · {reviewLabel(item.review_state)} · Revision {item.revision}</p>
        <p>Accepted {displayedTime(item.created_at)}. Human review remains available while analysis is pending.</p>
      </li>)}</ol>
      {!data.items.length && <p>No cases match these filters.</p>}
      <div><button type="button" disabled={offset === 0} onClick={() => { setData(null); setOffset(Math.max(0, offset - 20)); }}>Previous queue page</button>{" "}
        <button type="button" disabled={offset + 20 >= data.total || offset + 20 > 1000} onClick={() => { setData(null); setOffset(offset + 20); }}>Next queue page</button></div>
    </>}
  </div>;
}
