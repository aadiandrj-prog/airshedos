"use client";
import { useDeadline } from "../authority/expiry";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { displayedTime, processingLabel, residentRequest } from "../../lib/resident-client";
import type { components } from "../../lib/api-schema";

export function ReportList() {
  const [data, setData] = useState<components["schemas"]["ResidentList"] | null>(null);
  const [error, setError] = useState(""); const [offset, setOffset] = useState(0);
  const load = useCallback(async () => (await residentRequest(`reports?limit=20&offset=${offset}`)).json(), [offset]);
  const failed = () => setError("Your reports could not load. Check your sign-in and retry.");
  useEffect(() => {
    let active = true;
    void load().then((value) => { if (active) { setData(value); setError(""); } })
      .catch(() => { if (active) setError("Your reports could not load. Check your sign-in and retry."); });
    return () => { active = false; };
  }, [load]);
  useDeadline(data?.items.map((item) => item.content_expires_at).sort()[0], () => { setData(null); setError("A report expired. Reload your current permitted reports."); });
  return <section className="resident-stack">
    <Link href="/resident/reports/new">Report a new concern</Link>
    {error && <><p role="alert">{error}</p><Link href="/sign-in?returnTo=%2Fresident%2Freports">Sign in again</Link><button type="button" onClick={() => void load().then((value) => { setData(value); setError(""); }).catch(failed)}>Retry loading reports</button></>}
    {!data && !error && <p role="status">Loading your reports…</p>}
    {data && <><p>{data.total} saved report{data.total === 1 ? "" : "s"} in your account. Open a report to see its published updates.</p>
      {!data.items.length && <p>No reports on this page.</p>}
      <ul className="report-history">{data.items.map((report) => <li className="resident-card" key={report.id}>
        <Link href={`/resident/reports/${report.id}`}>Report {report.receipt_id}</Link>
        <p>Received {displayedTime(report.accepted_at)}</p><p><span className="status-chip">{processingLabel(report.processing)}</span></p>
      </li>)}</ul>
      <div><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous page</button>{" "}
        <button type="button" disabled={offset + 20 >= data.total} onClick={() => setOffset(offset + 20)}>Next page</button></div>
    </>}
  </section>;
}
