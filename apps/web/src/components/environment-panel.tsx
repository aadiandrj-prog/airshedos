"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  type EnvironmentalContext,
  type Measurement,
  type SourceStatus,
} from "@/lib/api";

import { SatellitePanel } from "./satellite-panel";

const DEFAULT_POINT = { lat: 28.4595, lng: 77.0266 };
const states: Record<SourceStatus["status"], string> = {
  live: "Live data",
  cached: "Cached data",
  unavailable: "Unavailable",
  not_configured: "Not configured",
  error: "Provider error",
};
const unitLabels: Record<string, string> = {
  CELSIUS: "°C",
  FAHRENHEIT: "°F",
  KILOMETERS_PER_HOUR: "km/h",
  MILES_PER_HOUR: "mph",
  MILLIBARS: "mbar",
  MILLIMETERS: "mm",
  INCHES: "in",
  MICROGRAMS_PER_CUBIC_METER: "µg/m³",
  PARTS_PER_BILLION: "ppb",
  KELVIN: "K",
  MEGAWATTS: "MW",
};
function quantity(value: Measurement | null | undefined) {
  return value
    ? `${value.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${unitLabels[value.unit] ?? value.unit}`
    : "Not supplied";
}
function time(value: string) {
  return (
    new Intl.DateTimeFormat("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Kolkata",
    }).format(new Date(value)) + " IST"
  );
}
function State({ source }: { source: SourceStatus }) {
  return (
    <span className={`source-state ${source.status}`}>
      {states[source.status]}
    </span>
  );
}
function SourceDetails({
  source,
  observed,
}: {
  source: SourceStatus;
  observed?: string;
}) {
  return (
    <details className="source-details">
      <summary>
        Source & timing <span aria-hidden="true">+</span>
      </summary>
      <p>{source.message}</p>
      <dl>
        <div>
          <dt>Provider</dt>
          <dd>{source.provider}</dd>
        </div>
        {observed && (
          <div>
            <dt>Observed</dt>
            <dd>{time(observed)}</dd>
          </div>
        )}
        {source.retrieved_at && (
          <div>
            <dt>Retrieved</dt>
            <dd>{time(source.retrieved_at)}</dd>
          </div>
        )}
        <div>
          <dt>Request time</dt>
          <dd>{source.latency_ms} ms</dd>
        </div>
      </dl>
    </details>
  );
}

export function EnvironmentPanel() {
  const [point, setPoint] = useState({ ...DEFAULT_POINT, sequence: 0 });
  const [lat, setLat] = useState(String(DEFAULT_POINT.lat));
  const [lng, setLng] = useState(String(DEFAULT_POINT.lng));
  const [context, setContext] = useState<EnvironmentalContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api
      .environment(DEFAULT_POINT.lat, DEFAULT_POINT.lng)
      .then((data) => {
        if (active) setContext(data);
      })
      .catch(() => {
        if (active)
          setError(
            "Environmental context could not be retrieved. Check the API connection and try again.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function probe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPoint((previous) => ({
      lat: Number(lat),
      lng: Number(lng),
      sequence: previous.sequence + 1,
    }));
    setLoading(true);
    setError("");
    setContext(null);
    try {
      setContext(await api.environment(Number(lat), Number(lng)));
    } catch {
      setError(
        "Environmental context could not be retrieved. Check the API connection and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  const available = context
    ? Object.values(context.source_statuses).filter(
        (s) => s.status === "live" || s.status === "cached",
      ).length
    : 0;
  const aq = context?.air_quality;
  const weather = context?.weather;
  const fires = context?.fires;

  return (
    <section
      className="environment-panel"
      id="environment-context"
      aria-labelledby="environment-title"
    >
      <div className="environment-heading">
        <div>
          <span className="eyebrow">01 / LIVE ENVIRONMENTAL CONTEXT</span>
          <h2 id="environment-title">The air, in context.</h2>
          <p>
            Independent observations for a geographic point. These do not
            corroborate the fictional incident below.
          </p>
        </div>
        <span className="context-availability" aria-live="polite">
          {loading
            ? "Checking sources"
            : context
              ? `${available} of 3 sources available`
              : "Connection unavailable"}
        </span>
      </div>
      <form className="probe-form" onSubmit={(event) => void probe(event)}>
        <div className="probe-location">
          <span className="crosshair" aria-hidden="true">
            ⌖
          </span>
          <div>
            <strong>Environmental probe</strong>
            <span>Default: Gurugram, Delhi NCR</span>
          </div>
        </div>
        <label>
          Latitude
          <input
            name="latitude"
            type="number"
            min="-90"
            max="90"
            step="any"
            required
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            disabled={loading}
          />
        </label>
        <label>
          Longitude
          <input
            name="longitude"
            type="number"
            min="-180"
            max="180"
            step="any"
            required
            value={lng}
            onChange={(e) => setLng(e.target.value)}
            disabled={loading}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Checking…" : "Check conditions"}
          <span aria-hidden="true"> ↗</span>
        </button>
      </form>
      {loading && (
        <p className="context-loading" role="status">
          Requesting air quality, weather, and nearby active-fire detections…
        </p>
      )}
      {error && (
        <p className="action-error" role="alert">
          {error}
        </p>
      )}
      {context && (
        <>
          <div className="context-meta">
            <span>
              Query: {context.latitude.toFixed(4)}°,{" "}
              {context.longitude.toFixed(4)}°
            </span>
            <span>
              Checked {time(context.generated_at)} · current conditions only
            </span>
          </div>
          <div className="environment-grid">
            <article
              className="source-card"
              aria-labelledby="air-quality-title"
            >
              <div className="section-label">
                <span className="source-icon" aria-hidden="true">
                  ≋
                </span>
                <State source={context.source_statuses.air_quality} />
              </div>
              <h3 id="air-quality-title">Air quality</h3>
              {aq ? (
                <>
                  <div className="metric-value">
                    {aq.indexes[0]?.value ?? "—"}
                    <span>
                      {aq.indexes[0]?.display_name ??
                        aq.indexes[0]?.code ??
                        "Index unavailable"}
                    </span>
                  </div>
                  <p className="source-caption">
                    {aq.indexes[0]?.category ?? "Category not supplied"}
                  </p>
                  <div className="metric-list">
                    {aq.indexes.map((index) => (
                      <div key={index.code}>
                        <span>
                          {index.display_name ?? index.code}
                          <small>
                            {index.code} · dominant:{" "}
                            {index.dominant_pollutant ?? "not supplied"}
                          </small>
                        </span>
                        <strong>{index.value ?? "—"}</strong>
                      </div>
                    ))}
                    {aq.pollutants.map((pollutant) => (
                      <div key={pollutant.code}>
                        <span>{pollutant.name ?? pollutant.code}</span>
                        <strong>{quantity(pollutant.concentration)}</strong>
                      </div>
                    ))}
                  </div>
                  <p className="source-caveat">{aq.provenance.note}</p>
                  <p className="google-attribution" translate="no">
                    Google Maps
                  </p>
                  <p className="source-caveat">
                    Source: Includes air quality data from Google
                  </p>
                </>
              ) : (
                <div className="source-empty">
                  <strong>—</strong>
                  <p>
                    {context.source_statuses.air_quality.status ===
                    "not_configured"
                      ? "Connect Google Air Quality to read local indexes and pollutant concentrations."
                      : "No usable air-quality observation is available."}
                  </p>
                </div>
              )}
              <SourceDetails
                source={context.source_statuses.air_quality}
                observed={aq?.observed_at}
              />
              <a
                className="provider-credit"
                href="https://developers.google.com/maps/documentation/air-quality/overview"
                target="_blank"
                rel="noreferrer"
              >
                Google Air Quality ↗
              </a>
            </article>
            <article className="source-card" aria-labelledby="weather-title">
              <div className="section-label">
                <span className="source-icon" aria-hidden="true">
                  ↗
                </span>
                <State source={context.source_statuses.weather} />
              </div>
              <h3 id="weather-title">Weather</h3>
              {weather ? (
                <>
                  <div className="metric-value">
                    {quantity(weather.temperature)}
                    <span>Temperature</span>
                  </div>
                  <div className="metric-list">
                    <div>
                      <span>Relative humidity</span>
                      <strong>
                        {weather.relative_humidity_percent != null
                          ? `${weather.relative_humidity_percent}%`
                          : "Not supplied"}
                      </strong>
                    </div>
                    <div>
                      <span>Wind speed</span>
                      <strong>{quantity(weather.wind_speed)}</strong>
                    </div>
                    <div>
                      <span>Wind from</span>
                      <strong>
                        {weather.wind_from_degrees != null
                          ? `${weather.wind_from_degrees}°`
                          : "Not supplied"}
                        {weather.wind_cardinal
                          ? ` · ${weather.wind_cardinal.toLowerCase().replaceAll("_", " ")}`
                          : ""}
                      </strong>
                    </div>
                    <div>
                      <span>Sea-level pressure</span>
                      <strong>{quantity(weather.sea_level_pressure)}</strong>
                    </div>
                    <div>
                      <span>Precipitation estimate</span>
                      <strong>{quantity(weather.precipitation_qpf)}</strong>
                    </div>
                    <div>
                      <span>Rain probability</span>
                      <strong>
                        {weather.precipitation_probability_percent != null
                          ? `${weather.precipitation_probability_percent}%`
                          : "Not supplied"}
                      </strong>
                    </div>
                    <div>
                      <span>Cloud cover</span>
                      <strong>
                        {weather.cloud_cover_percent != null
                          ? `${weather.cloud_cover_percent}%`
                          : "Not supplied"}
                      </strong>
                    </div>
                  </div>
                  <p className="source-caveat">
                    Wind direction is where wind comes from: 0° N, 90° E, 180°
                    S, 270° W.
                  </p>
                  <p className="google-attribution" translate="no">
                    Google Maps
                  </p>
                </>
              ) : (
                <div className="source-empty">
                  <strong>—</strong>
                  <p>
                    {context.source_statuses.weather.status === "not_configured"
                      ? "Connect Google Weather to read wind, temperature, humidity, and precipitation."
                      : "Weather is unavailable. Other sources remain independent."}
                  </p>
                </div>
              )}
              <SourceDetails
                source={context.source_statuses.weather}
                observed={weather?.observed_at}
              />
              <a
                className="provider-credit"
                href="https://developers.google.com/maps/documentation/weather/overview"
                target="_blank"
                rel="noreferrer"
              >
                Google Weather ↗
              </a>
            </article>
            <article className="source-card" aria-labelledby="fires-title">
              <div className="section-label">
                <span className="source-icon" aria-hidden="true">
                  ◈
                </span>
                <State source={context.source_statuses.fires} />
              </div>
              <h3 id="fires-title">Nearby fire detections</h3>
              {fires ? (
                <>
                  <div className="metric-value">
                    {fires.length}
                    <span>Within {context.fire_search_radius_km} km</span>
                  </div>
                  <p className="source-caption">
                    {fires.length
                      ? `Closest detection: ${fires[0].distance_from_query_km.toFixed(2)} km`
                      : "No nearby active-fire detections returned."}
                  </p>
                  <ul className="fire-list">
                    {fires.slice(0, 5).map((fire) => (
                      <li key={fire.source_id}>
                        <strong>
                          Nearby active-fire detection{" "}
                          <span>
                            {fire.distance_from_query_km.toFixed(2)} km
                          </span>
                        </strong>
                        <span>
                          {time(fire.observed_at)} ·{" "}
                          {fire.satellite ?? "Satellite unspecified"} /{" "}
                          {fire.instrument ?? "Instrument unspecified"}
                        </span>
                        <span>
                          Confidence:{" "}
                          {fire.confidence === "h"
                            ? "high"
                            : fire.confidence === "n"
                              ? "nominal"
                              : fire.confidence === "l"
                                ? "low"
                                : "not supplied"}{" "}
                          · FRP: {quantity(fire.fire_radiative_power)}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {fires.length > 5 && (
                    <p className="source-caveat">
                      Showing the 5 closest of {fires.length} detections.
                    </p>
                  )}
                  <p className="source-caveat">
                    {context.fire_dataset.replaceAll("_", " ")} · today and
                    previous UTC day. Thermal detections do not establish a
                    pollution source.
                  </p>
                </>
              ) : (
                <div className="source-empty">
                  <strong>—</strong>
                  <p>
                    {context.source_statuses.fires.status === "not_configured"
                      ? "Connect NASA FIRMS to check nearby thermal detections within the configured radius."
                      : "No valid detection response. An unavailable source does not mean zero fires."}
                  </p>
                </div>
              )}
              <SourceDetails source={context.source_statuses.fires} />
              <a
                className="provider-credit"
                href="https://firms.modaps.eosdis.nasa.gov/"
                target="_blank"
                rel="noreferrer"
              >
                NASA FIRMS ↗
              </a>
            </article>
          </div>
          <div className="context-footnote">
            <span>OBSERVATION ≠ ATTRIBUTION</span>
            <p>
              Sources update at different times. AirshedOS does not infer
              causation, confirm an incident, or calculate a live forecast.
            </p>
          </div>
        </>
      )}
      <SatellitePanel key={point.sequence} lat={point.lat} lng={point.lng} />
    </section>
  );
}
