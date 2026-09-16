import type { components } from "./api-schema";

export type OfficerCase = components["schemas"]["OfficerCase"];
export type CaseSummary = components["schemas"]["CaseSummary"];
export type ReviewState = components["schemas"]["ReviewState"];

export type ForecastContext =
  components["schemas"]["AirQualityForecastContext"];

export type CorroborationAssessment =
  components["schemas"]["CorroborationAssessment"];

export type CitizenAnalysis = components["schemas"]["CitizenAnalysisResponse"];

export type Incident = components["schemas"]["PollutionIncident"];
export type ShareResponse = components["schemas"]["ShareResponse"];
export type ShareRequest = components["schemas"]["ShareRequest"];
export type EnvironmentalContext =
  components["schemas"]["EnvironmentalContext"];
export type SatelliteContext =
  components["schemas"]["SatelliteAtmosphericContext"];
export type SourceStatus = components["schemas"]["EnvironmentalSourceStatus"];
export type Measurement = components["schemas"]["Measurement"];

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

async function request<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 10000,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}). Please try again.`,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  cases: () => request<CaseSummary[]>("/api/v1/review/cases"),
  case: (id: string) => request<OfficerCase>(`/api/v1/review/cases/${encodeURIComponent(id)}`),
  review: async (id: string, state: ReviewState, revision: number): Promise<OfficerCase> => {
    const response = await fetch(`${API_BASE}/api/v1/review/cases/${encodeURIComponent(id)}/review`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state, expected_revision: revision }), signal: AbortSignal.timeout(10000),
    });
    if (response.status === 409) throw new Error("Review changed or transition is no longer allowed. Refresh the case.");
    if (response.status === 404) throw new Error("Case expired or unavailable. Submit and corroborate a new report.");
    if (!response.ok) throw new Error("Review could not be saved. Please retry.");
    return response.json() as Promise<OfficerCase>;
  },
  forecast: async (
    lat: number,
    lng: number,
    signal: AbortSignal,
  ): Promise<ForecastContext> => {
    const response = await fetch(
      `${API_BASE}/api/v1/environment/forecast?${new URLSearchParams({ lat: String(lat), lng: String(lng) })}`,
      {
        cache: "no-store",
        signal: AbortSignal.any([signal, AbortSignal.timeout(70000)]),
      },
    );
    if (!response.ok) throw new Error("Provider forecast unavailable");
    return response.json() as Promise<ForecastContext>;
  },
  corroborate: async (
    reportId: string,
    signal: AbortSignal,
  ): Promise<CorroborationAssessment> => {
    const response = await fetch(
      `${API_BASE}/api/v1/citizen-reports/${encodeURIComponent(reportId)}/corroborate`,
      {
        method: "POST",
        cache: "no-store",
        signal: AbortSignal.any([signal, AbortSignal.timeout(70000)]),
      },
    );
    if (response.status === 404 || response.status === 410)
      throw new Error(
        "Report expired or unavailable. Analyze the image again to corroborate it.",
      );
    if (!response.ok)
      throw new Error(
        "Environmental corroboration could not complete. Please try again.",
      );
    return response.json() as Promise<CorroborationAssessment>;
  },
  analyzeCitizen: async (data: FormData): Promise<CitizenAnalysis> => {
    const response = await fetch(`${API_BASE}/api/v1/citizen-reports/analyze`, {
      method: "POST",
      body: data,
      cache: "no-store",
      signal: AbortSignal.timeout(65000),
    });
    if (!response.ok) {
      if (response.status === 413)
        throw new Error(
          "Image exceeds the upload limit. Choose a JPEG or PNG up to 5 MiB.",
        );
      if (response.status === 422)
        throw new Error(
          "Check the image format, size and coordinates. Use a valid JPEG or PNG up to 5 MiB and 16 MP.",
        );
      throw new Error(
        "The analysis service could not complete the request. Please try again.",
      );
    }
    return response.json() as Promise<CitizenAnalysis>;
  },
  environment: (lat: number, lng: number) =>
    request<EnvironmentalContext>(
      `/api/v1/environment/context?${new URLSearchParams({ lat: String(lat), lng: String(lng), include_satellite: "false" })}`,
      undefined,
      70000,
    ),
  satellite: (lat: number, lng: number) =>
    request<SatelliteContext>(
      `/api/v1/environment/satellite?${new URLSearchParams({ lat: String(lat), lng: String(lng) })}`,
      undefined,
      70000,
    ),
  ready: () => request<{ status: string }>("/ready"),
  incidents: () => request<Incident[]>("/api/v1/incidents"),
  incident: (id: string) =>
    request<Incident>(`/api/v1/incidents/${encodeURIComponent(id)}`),
  acknowledge: (id: string) =>
    request<Incident>(
      `/api/v1/incidents/${encodeURIComponent(id)}/acknowledge`,
      { method: "POST" },
    ),
  share: (id: string, payload: ShareRequest) =>
    request<ShareResponse>(
      `/api/v1/incidents/${encodeURIComponent(id)}/share`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    ),
};
