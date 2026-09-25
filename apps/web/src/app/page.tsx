"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type Incident, type OfficerCase, type CorroborationAssessment } from "@/lib/api";
import { OfficerCommandCenter } from "@/components/officer-command-center";
import { CitizenEvidencePanel } from "@/components/citizen-evidence-panel";
import { EnvironmentPanel } from "@/components/environment-panel";

const percent = (value: number) => `${Math.round(value * 100)}%`;
const label = (value: string) => value.replaceAll("_", " ");
const timestamp = (value: string) =>
  new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value)) + " IST";

export default function CommandCenter() {
  const [officerCase, setOfficerCase] = useState<OfficerCase | null>(null);
  async function enterQueue(assessment: CorroborationAssessment, signal: AbortSignal) {
    try { const item = await api.case(assessment.id); if (signal.aborted) return false; setOfficerCase(item); return true; }
    catch { return false; }
  }
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [apiReady, setApiReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [actionError, setActionError] = useState("");
  const [targetId, setTargetId] = useState("");
  const selected = incidents.find((incident) => incident.id === selectedId);

  const load = useCallback(() => {
    return Promise.all([api.ready(), api.incidents()])
      .then(async ([ready, items]) => {
        if (ready.status !== "ready") throw new Error("API is not ready");
        const priority = { high: 3, moderate: 2, low: 1 };
        items.sort(
          (a, b) =>
            priority[b.severity] - priority[a.severity] ||
            b.confidence - a.confidence,
        );
        const detail = items.length ? await api.incident(items[0].id) : null;
        setIncidents(
          items.map((item) => (item.id === detail?.id ? detail : item)),
        );
        setSelectedId(detail?.id ?? null);
        setTargetId(
          detail?.affected_jurisdictions.find(
            (j) => j.id !== detail.jurisdiction.id,
          )?.id ?? "",
        );
        setApiReady(true);
      })
      .catch(() => {
        setApiReady(false);
        setError(
          "The command center could not reach the API. Check that the backend is running, then retry.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function refresh() {
    setLoading(true);
    setError("");
    setFeedback("");
    setActionError("");
    void load();
  }

  async function selectIncident(id: string) {
    setBusy(true);
    setFeedback("");
    setActionError("");
    try {
      const incident = await api.incident(id);
      setIncidents((items) =>
        items.map((item) => (item.id === id ? incident : item)),
      );
      setSelectedId(id);
      setTargetId(
        incident.affected_jurisdictions.find(
          (j) => j.id !== incident.jurisdiction.id,
        )?.id ?? "",
      );
    } catch {
      setActionError("Unable to load incident details. Please retry.");
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "acknowledge" | "share") {
    if (!selected) return;
    setBusy(true);
    setFeedback("");
    setActionError("");
    try {
      let updated: Incident;
      if (action === "acknowledge") {
        updated = await api.acknowledge(selected.id);
        setFeedback(
          "Incident acknowledged. Field verification is still required.",
        );
      } else {
        const result = await api.share(selected.id, {
          target_jurisdiction_id: targetId,
        });
        updated = result.incident;
        setFeedback(result.action.description);
      }
      setIncidents((items) =>
        items.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch {
      setActionError(
        "The action could not be saved. Check the API connection and retry.",
      );
    } finally {
      setBusy(false);
    }
  }

  const jurisdictions = new Set(
    incidents.flatMap((i) => i.affected_jurisdictions.map((j) => j.id)),
  );
  const updatedAt = incidents.length
    ? incidents.reduce((a, b) =>
        Date.parse(a.updated_at) > Date.parse(b.updated_at) ? a : b,
      ).updated_at
    : null;
  const shared = selected?.actions.some(
    (action) =>
      action.type === "share" && action.target_jurisdiction?.id === targetId,
  );

  return (
    <>
      <a className="skip-link" href="#officer-command">Skip to command center</a>
      <header className="masthead">
        <Link className="brand" href="/" aria-label="AirshedOS home">
          <span className="brand-mark" aria-hidden="true">
            ≋
          </span>
          <span>
            Airshed<span className="brand-light">OS</span>
            <small>Environmental intelligence</small>
          </span>
        </Link>
        <nav className="primary-nav" aria-label="Workspace navigation"><a href="#officer-command">Workspace</a><a href="#environment-context">Environment</a><a href="#field-evidence">Field evidence</a></nav>
        <span
          className={`system-status ${apiReady && !error ? "connected" : ""}`}
        >
          <i />
          {loading
            ? "Connecting to API"
            : apiReady && !error
              ? "API operational"
              : "API unavailable"}
        </span>
      </header>
      <main>
        <div className="page-heading">
          <div>
            <span className="eyebrow">
              National Capital Region / Operations
            </span>
            <h1>Air operations<span className="page-subtitle">Evidence into perspective.</span></h1>
          </div>
          <button
            className="secondary refresh"
            onClick={refresh}
            disabled={loading || busy}
          >
            ↻ Refresh
          </button>
        </div>
        <section className="demo-guide" aria-label="Demo journey">
          <span className="guide-label">Demo journey</span>
          <nav aria-label="Demo steps"><a href="#environment-context">1 · Provider context</a><a href="#field-evidence">2 · Synthetic image & interpretation</a><a href="#officer-command">3 · Review & simulated handoff</a></nav>
          <details className="guide-about"><summary>About this workflow</summary><p>Provider readings retain live/cached/unavailable status. Gemini provides an AI interpretation; AirshedOS applies deterministic corroboration rules. All handoffs are simulated.</p></details>
        </section>
        <OfficerCommandCenter incident={selected ?? null} selectedCase={officerCase} onCase={setOfficerCase} />
        <EnvironmentPanel />
        <CitizenEvidencePanel onCorroborated={enterQueue} />
        <div className="workspace-heading" id="incident-command">
          <span className="eyebrow">03 / DEMO INCIDENT WORKSPACE</span>
          <h2>From evidence to action.</h2>
          <p>
            A fictional operations scenario. All incident evidence and forecast
            values below are sample data.
          </p>
        </div>
        <div className="demo-banner">
          <span className="tag demo">DEMO · PHASE 1A</span>
          <p>
            Fictional environmental evidence and forecast. No live data or AI
            inference. Field verification required.
          </p>
        </div>
        {loading ? (
          <section className="state-panel" role="status">
            <h2>Loading incident evidence…</h2>
            <p>Connecting to the operations API. The demo server may take up to a minute to wake.</p>
          </section>
        ) : error ? (
          <section className="state-panel" role="alert">
            <h2>Connection unavailable</h2>
            <p>{error}</p>
            <button onClick={refresh}>Retry connection</button>
          </section>
        ) : (
          <>
            <section className="summary" aria-label="Operations summary">
              <div>
                <span>Active incidents</span>
                <strong>{incidents.length.toString().padStart(2, "0")}</strong>
              </div>
              <div>
                <span>High-priority incidents</span>
                <strong className="attention">
                  {incidents
                    .filter((i) => i.severity === "high")
                    .length.toString()
                    .padStart(2, "0")}
                </strong>
              </div>
              <div>
                <span>Jurisdictions involved</span>
                <strong>
                  {jurisdictions.size.toString().padStart(2, "0")}
                </strong>
              </div>
              <div>
                <span>Last updated</span>
                <strong className="updated">
                  {updatedAt ? timestamp(updatedAt) : "—"}
                </strong>
              </div>
            </section>
            {!selected ? (
              <section className="state-panel">
                <h2>No active incidents</h2>
                <p>The API returned no incidents. Refresh to check again.</p>
              </section>
            ) : (
              <>
                <div className="command-grid">
                  <div className="geography-column">

                    <section
                      className="forecast-card"
                      aria-labelledby="forecast-title"
                    >
                      <div className="section-label">
                        <h2 id="forecast-title">What may happen next</h2>
                        <span className="tag demo">ILLUSTRATIVE DEMO FORECAST</span>
                        <span className="tag high">
                          {selected.forecast.risk_level} risk
                        </span>
                      </div>
                      <div className="forecast-main">
                        <strong>
                          {percent(selected.forecast.spike_probability)}
                        </strong>
                        <div>
                          pollution-spike probability
                          <span>
                            Within {selected.forecast.horizon_hours} hours ·
                            demo forecast
                          </span>
                        </div>
                      </div>
                      <p>{selected.forecast.summary}</p>
                      <div className="forecast-direction">
                        ↗{" "}
                        {selected.forecast.predicted_direction ??
                          "Transport direction unavailable"}
                      </div>
                      <small>
                        Scenario generated{" "}
                        {timestamp(selected.forecast.generated_at)}
                      </small>
                    </section>
                  </div>
                  <section
                    className="incident-panel"
                    aria-labelledby="incident-list-title"
                  >
                    <div className="section-label">
                      <h2 id="incident-list-title">Priority incidents</h2>
                      <span className="count">{incidents.length}</span>
                    </div>
                    <div className="incident-list">
                      {incidents.map((incident) => (
                        <button
                          key={incident.id}
                          className={`incident-choice ${incident.id === selectedId ? "selected" : ""}`}
                          aria-pressed={incident.id === selectedId}
                          disabled={busy}
                          onClick={() => void selectIncident(incident.id)}
                        >
                          <span className="incident-choice-meta">
                            <span>{incident.id}</span>
                            <span className="tag high">
                              {incident.severity} priority
                            </span>
                          </span>
                          <strong>{incident.title}</strong>
                          <span>
                            {incident.jurisdiction.name} ·{" "}
                            {incident.jurisdiction.state}
                          </span>
                        </button>
                      ))}
                    </div>
                    <div className="incident-detail">
                      <div className="section-label">
                        <span className="eyebrow">INCIDENT BRIEF</span>
                        <span
                          className={`tag ${selected.status === "acknowledged" ? "supported" : "neutral"}`}
                        >
                          {label(selected.status)}
                        </span>
                      </div>
                      <h3>{selected.title} — field verification required.</h3>
                      <dl className="detail-facts">
                        <div>
                          <dt>Event type</dt>
                          <dd>{label(selected.event_type)}</dd>
                        </div>
                        <div>
                          <dt>Detected</dt>
                          <dd>{timestamp(selected.detected_at)}</dd>
                        </div>
                        <div>
                          <dt>Owning jurisdiction</dt>
                          <dd>
                            {selected.jurisdiction.name},{" "}
                            {selected.jurisdiction.state}
                          </dd>
                        </div>
                        <div>
                          <dt>Potentially affected</dt>
                          <dd>
                            {selected.affected_jurisdictions
                              .map((j) => j.name)
                              .join(" · ")}
                          </dd>
                        </div>
                      </dl>
                      <div className="recommended">
                        <span className="eyebrow">RECOMMENDED ACTION</span>
                        <p>{selected.recommended_action}</p>
                      </div>
                      <div className="actions">
                        <button
                          onClick={() => void act("acknowledge")}
                          disabled={busy || selected.status === "acknowledged"}
                        >
                          {selected.status === "acknowledged"
                            ? "✓ Acknowledged"
                            : busy
                              ? "Saving…"
                              : "Acknowledge"}
                        </button>
                        <div className="share-controls">
                          <label htmlFor="jurisdiction">
                            Share with jurisdiction
                          </label>
                          <div>
                            <select
                              id="jurisdiction"
                              value={targetId}
                              onChange={(event) =>
                                setTargetId(event.target.value)
                              }
                              disabled={busy}
                            >
                              {selected.affected_jurisdictions
                                .filter(
                                  (j) => j.id !== selected.jurisdiction.id,
                                )
                                .map((j) => (
                                  <option key={j.id} value={j.id}>
                                    {j.name}
                                  </option>
                                ))}
                            </select>
                            <button
                              className="secondary"
                              disabled={busy || !targetId || shared}
                              onClick={() => void act("share")}
                            >
                              {shared ? "Shared (demo)" : "Share"}
                            </button>
                          </div>
                        </div>
                        <small>
                          Actions are stored in memory. Sharing is simulated.
                        </small>
                      </div>
                      <div aria-live="polite">
                        {feedback && <p className="feedback">{feedback}</p>}
                      </div>
                      {actionError && (
                        <p role="alert" className="action-error">
                          {actionError}
                        </p>
                      )}
                    </div>
                  </section>
                </div>
                <section
                  className="evidence-panel"
                  aria-labelledby="evidence-title"
                >
                  <div className="evidence-header">
                    <div>
                      <span className="eyebrow">
                        WHY THIS REQUIRES ATTENTION
                      </span>
                      <h2 id="evidence-title">Evidence fusion</h2>
                      <p>
                        Independent signals support a hypothesis. They do not
                        establish the source.
                      </p>
                    </div>
                    <div className="confidence">
                      <span>INCIDENT CONFIDENCE</span>
                      <strong>
                        {percent(selected.confidence)}{" "}
                        <small>
                          {selected.confidence >= 0.8
                            ? "HIGH"
                            : selected.confidence >= 0.5
                              ? "MODERATE"
                              : "LOW"}
                        </small>
                      </strong>
                      <span>Illustrative score · not calibrated</span>
                    </div>
                  </div>
                  <div className="evidence-list">
                    {selected.evidence.map((signal, index) => (
                      <details key={signal.id} className="evidence-row">
                        <summary>
                          <span className="signal-number">0{index + 1}</span>
                          <span className="signal-title">{signal.source}</span>
                          <span className={`tag ${signal.status}`}>
                            {signal.confidence != null
                              ? `${percent(signal.confidence)} · `
                              : ""}
                            {label(signal.status)}
                          </span>
                          <span className="expand" aria-hidden="true">
                            +
                          </span>
                        </summary>
                        <div className="evidence-content">
                          <p>{signal.summary}</p>
                          <p className="provenance">
                            Source: {signal.provenance.source_id} ·{" "}
                            {signal.provenance.method}
                            <br />
                            {signal.observed_at
                              ? `Sample observed at ${timestamp(signal.observed_at)}`
                              : "No observation available"}
                            <br />
                            {signal.provenance.note}
                          </p>
                        </div>
                      </details>
                    ))}
                  </div>
                </section>
                {selected.actions.length > 0 && (
                  <section
                    className="activity"
                    aria-labelledby="activity-title"
                  >
                    <h2 id="activity-title">Action record</h2>
                    <ul>
                      {selected.actions.map((action) => (
                        <li key={action.id}>
                          <span className="tag neutral">{action.status}</span>
                          <div>
                            <p>{action.description}</p>
                            <time dateTime={action.created_at}>
                              {timestamp(action.created_at)}
                            </time>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
          </>
        )}
        <footer>
          AirshedOS{" "}
          <span>
            Phase 3C · Demo prototype · No causal
            attribution
          </span>
        </footer>
      </main>
    </>
  );
}
