import type { components } from "./api-schema";

export type Incident = components["schemas"]["PollutionIncident"];
export type ShareResponse = components["schemas"]["ShareResponse"];
export type ShareRequest = components["schemas"]["ShareRequest"];

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}). Please try again.`,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
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
