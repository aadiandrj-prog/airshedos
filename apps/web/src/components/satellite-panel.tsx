"use client";

import { useEffect, useId, useState } from "react";
import { api, type SatelliteContext } from "@/lib/api";

const labels = { no2: "NO₂", co: "CO", aerosol_index: "UV Aerosol Index" };
const availability: Record<
  SatelliteContext["products"][number]["availability"],
  string
> = {
  available: "Available",
  no_scene: "No recent scene",
  quality_filtered: "Quality filtered",
  no_usable_pixels: "No usable pixels",
  not_configured: "Setup required",
  authentication_error: "Authentication required",
  configuration_error: "Project setup required",
  provider_error: "Query failed",
  timeout: "Request timed out",
  busy: "Source busy",
};
const sourceLabels = {
  live: "Fresh retrieval",
  cached: "Cached retrieval",
  unavailable: "Retrieval unavailable",
  not_configured: "Setup required",
  error: "Retrieval error",
};
function age(seconds: number) {
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${(seconds / 3600).toFixed(1)}h ago`;
}
function timestamp(value: string) {
  return (
    new Date(value).toLocaleString("en-IN", {
      timeZone: "UTC",
      hour12: false,
    }) + " UTC"
  );
}
function valueLabel(value: number) {
  return value !== 0 && Math.abs(value) < 0.01
    ? value.toExponential(3)
    : Number(value.toPrecision(5)).toString();
}

export function SatellitePanel({ lat, lng }: { lat: number; lng: number }) {
  const [context, setContext] = useState<SatelliteContext | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    api
      .satellite(lat, lng)
      .then((data) => {
        if (active) setContext(data);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [lat, lng]);

  return <SatelliteReadings context={context} error={error} />;
}

export function SatelliteReadings({ context, error = false }: { context: SatelliteContext | null; error?: boolean }) {
  const titleId = useId();
  return (
    <section className="satellite-panel" aria-labelledby={titleId}>
      <div className="environment-heading">
        <div>
          <span className="eyebrow">SATELLITE ATMOSPHERIC EVIDENCE</span>
          <h3 id={titleId}>Latest usable satellite observations</h3>
          <p>Sentinel-5P / TROPOMI · Regional atmospheric context</p>
        </div>
        {context && (
          <span className={`source-state ${context.provider_status.status}`}>
            {sourceLabels[context.provider_status.status]}
          </span>
        )}
      </div>
      <p className="satellite-disclaimer">
        Satellite atmospheric columns are regional context and are not
        equivalent to ground-level pollutant concentrations.
      </p>
      {!context && !error && (
        <p role="status" className="context-loading">
          Searching recent satellite observations… Other sources load
          independently.
        </p>
      )}
      {error && (
        <p role="alert" className="action-error">
          Satellite evidence could not be retrieved. Use Check conditions to
          retry.
        </p>
      )}
      {context && (
        <>
          <div className="context-meta">
            <span>
              {context.search_window.lookback_hours}h window ·{" "}
              {context.retrieval_radius_km} km radius ·{" "}
              {context.latitude.toFixed(4)}°, {context.longitude.toFixed(4)}°
            </span>
            <span>Window ends {timestamp(context.search_window.end)}</span>
          </div>
          <div className="satellite-grid">
            {context.products.map((product) => {
              const observation = product.observation;
              return (
                <article
                  className="satellite-product"
                  key={product.product}
                  aria-label={labels[product.product]}
                >
                  <div className="section-label">
                    <h4>{labels[product.product]}</h4>
                    <span className={`source-state ${product.status}`}>
                      {availability[product.availability]}
                    </span>
                  </div>
                  {observation ? (
                    <>
                      <p className="satellite-value">
                        {valueLabel(observation.value)}{" "}
                        <span>{observation.unit}</span>
                      </p>
                      <p className="source-caption">
                        Observed {age(observation.age_seconds)}
                      </p>
                      <p className="source-caveat">
                        {timestamp(observation.observed_at)}
                        <br />
                        Quality: usable ·{" "}
                        {product.cache_hit
                          ? "Cached retrieval"
                          : "Fresh retrieval"}
                      </p>
                    </>
                  ) : (
                    <p className="source-caveat">{product.message}</p>
                  )}
                  <details className="source-details">
                    <summary>
                      Source & quality <span aria-hidden="true">+</span>
                    </summary>
                    <dl>
                      <div>
                        <dt>Collection</dt>
                        <dd>{product.collection}</dd>
                      </div>
                      <div>
                        <dt>Band</dt>
                        <dd>{product.band}</dd>
                      </div>
                      <div>
                        <dt>Query time</dt>
                        <dd>
                          {product.latency_ms} ms{" "}
                          {product.cache_hit && "(original retrieval)"}
                        </dd>
                      </div>
                      <div>
                        <dt>Scenes</dt>
                        <dd>{product.scene_count ?? "Not retrieved"}</dd>
                      </div>
                      {observation && (
                        <>
                          <div>
                            <dt>Image</dt>
                            <dd>{observation.image_id}</dd>
                          </div>
                          <div>
                            <dt>Retrieved</dt>
                            <dd>{timestamp(observation.retrieved_at)}</dd>
                          </div>
                          <div>
                            <dt>Native footprint</dt>
                            <dd>
                              {observation.native_footprint ?? "Not supplied"}
                            </dd>
                          </div>
                          <div>
                            <dt>Local reduction</dt>
                            <dd>
                              Mean · {observation.quality.valid_grid_cells}{" "}
                              valid grid cells · {observation.grid_scale_m} m
                              grid (not sensor footprint)
                            </dd>
                          </div>
                        </>
                      )}
                    </dl>
                    {observation && (
                      <>
                        <p>{observation.quality.catalog_qa_rule}</p>
                        <p>{observation.quality.applied_filters.join("; ")}</p>
                        <p>{observation.quality.note}</p>
                      </>
                    )}
                  </details>
                </article>
              );
            })}
          </div>
          <p className="source-caveat">
            {context.temporal_note} An absent observation does not indicate
            clean air.
          </p>
          <a
            className="provider-credit"
            href="https://developers.google.com/earth-engine/datasets/tags/s5p"
            target="_blank"
            rel="noreferrer"
          >
            Copernicus Sentinel-5P via Google Earth Engine ↗
          </a>
        </>
      )}
    </section>
  );
}
