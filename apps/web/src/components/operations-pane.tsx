import type { Incident } from "@/lib/api";

/** Phase 1A schematic, deliberately isolated for a future map implementation. */
export function OperationsPane({ incident }: { incident: Incident }) {
  return (
    <section className="operations-pane" aria-labelledby="operations-title">
      <div className="pane-heading">
        <div>
          <span className="eyebrow">GEOGRAPHIC OPERATIONS</span>
          <h2 id="operations-title">Delhi–Haryana border</h2>
        </div>
        <span className="tag neutral">Schematic</span>
      </div>
      <svg
        className="map"
        viewBox="0 0 720 450"
        role="img"
        aria-labelledby="map-title map-desc"
      >
        <title id="map-title">
          Incident location and possible transport direction
        </title>
        <desc id="map-desc">
          Illustrative geography, not to scale. Incident at {incident.latitude},{" "}
          {incident.longitude}. Possible movement:{" "}
          {incident.forecast.predicted_direction ?? "unavailable"}.
        </desc>
        <defs>
          <pattern
            id="grid"
            width="36"
            height="36"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 36 0 L 0 0 0 36"
              fill="none"
              stroke="#d7e1df"
              strokeWidth="0.8"
            />
          </pattern>
          <linearGradient id="transport">
            <stop stopColor="#d79537" stopOpacity="0.3" />
            <stop offset="1" stopColor="#d79537" stopOpacity="0.04" />
          </linearGradient>
          <marker
            id="arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L0,6 L7,3 z" fill="#a46715" />
          </marker>
        </defs>
        <rect width="720" height="450" fill="#edf2f0" />
        <rect width="720" height="450" fill="url(#grid)" />
        <path
          d="M0 335 Q150 235 240 256 T420 195 T720 100"
          fill="none"
          stroke="white"
          strokeWidth="16"
        />
        <path
          d="M160 450 L236 337 L300 240 L362 154 L410 0"
          fill="none"
          stroke="white"
          strokeWidth="10"
        />
        <path
          d="M430 0 Q380 95 432 166 T398 299 T477 450"
          fill="none"
          stroke="#98ada8"
          strokeDasharray="7 7"
          strokeWidth="2"
        />
        <text x="82" y="103" className="map-state">
          HARYANA
        </text>
        <text x="493" y="75" className="map-state">
          DELHI
        </text>
        <text x="87" y="348" className="map-place">
          Gurugram
        </text>
        <text x="475" y="145" className="map-place">
          South West Delhi
        </text>
        {incident.forecast.predicted_direction && (
          <>
            <path
              d="M277 279 Q360 170 542 173 L525 88 Q350 123 277 279"
              fill="url(#transport)"
            />
            <path
              d="M296 261 Q387 169 511 137"
              fill="none"
              stroke="#a46715"
              strokeWidth="2"
              strokeDasharray="6 5"
              markerEnd="url(#arrow)"
            />
            <text x="341" y="219" className="map-annotation">
              Possible transport
            </text>
          </>
        )}
        <circle cx="277" cy="279" r="33" fill="#b95b30" opacity="0.09" />
        <circle cx="277" cy="279" r="19" fill="#b95b30" opacity="0.16" />
        <circle
          cx="277"
          cy="279"
          r="8"
          fill="#af4b24"
          stroke="white"
          strokeWidth="3"
        />
        <rect x="307" y="265" width="139" height="37" rx="5" fill="#172f34" />
        <text x="322" y="289" fill="white" fontSize="14" fontWeight="600">
          {incident.id}
        </text>
        <text x="649" y="349" className="map-annotation">
          N
        </text>
        <path
          d="M654 379 L654 359 M649 365 L654 359 L659 365"
          stroke="#526b65"
          fill="none"
          strokeWidth="2"
        />
        <text x="28" y="423" className="map-annotation">
          Illustrative geography · not to scale
        </text>
      </svg>
      <div className="map-footer">
        <span>
          <i className="legend-dot" />
          Probable incident
        </span>
        <span>
          <i className="legend-line" />
          Possible movement
        </span>
      </div>
      <div className="coordinates">
        <span>
          {incident.latitude.toFixed(4)}° N, {incident.longitude.toFixed(4)}° E
        </span>
        <span>Location from demo fixture</span>
      </div>
    </section>
  );
}
