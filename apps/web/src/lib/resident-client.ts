import type { components } from "./api-schema";

export type Submission = components["schemas"]["ResidentSubmission"];
export type Receipt = components["schemas"]["ResidentReceipt"];
export type Detail = components["schemas"]["ResidentReportDetail"];
export type Stage = components["schemas"]["MediaRead"];
export function processingLabel(value: string) {
  return ({ PENDING: "Analysis pending", RUNNING: "Analysis running", SUCCEEDED: "Advisory checks available",
    PARTIAL: "Analysis incomplete", FAILED: "Analysis unavailable", CANCELLED: "Processing stopped" } as Record<string,string>)[value] ?? "Analysis unavailable";
}
export function reporterStatusLabel(value: string) {
  return ({ RECEIVED: "Report received", IN_REVIEW: "In review", FOLLOW_UP_PLANNED: "Follow-up planned",
    UPDATE_AVAILABLE: "Update available", CLOSED: "Review ended" } as Record<string,string>)[value] ?? value.replaceAll("_", " ").toLowerCase();
}
export const DRAFT_PREFIX = "airshedos:resident:attempt:";
export type Attempt = { ownerId: string; key: string; createdAt: string; body?: Submission };

export function clearResidentAttempts() {
  try { for (const key of Object.keys(sessionStorage)) if (key.startsWith(DRAFT_PREFIX)) sessionStorage.removeItem(key); }
  catch { /* Browser storage is optional; current-page retries still work. */ }
}

export function readAttempt(ownerId: string): Attempt | null {
  try {
    for (const key of Object.keys(sessionStorage)) if (key.startsWith(DRAFT_PREFIX) && key !== DRAFT_PREFIX + ownerId) sessionStorage.removeItem(key);
    const raw = sessionStorage.getItem(DRAFT_PREFIX + ownerId);
    if (!raw || raw.length > 32000) return null;
    const saved = JSON.parse(raw) as Attempt;
    const age = Date.now() - Date.parse(saved.createdAt);
    if (saved.ownerId !== ownerId || !/^[a-f0-9-]{36}$/.test(saved.key) || !Number.isFinite(age) || age > 86400000 || age < -60000) {
      clearResidentAttempts(); return null;
    }
    return saved;
  } catch { return null; }
}

export function keepAttempt(attempt: Attempt, keepText: boolean) {
  try { sessionStorage.setItem(DRAFT_PREFIX + attempt.ownerId, JSON.stringify({
    ownerId: attempt.ownerId, key: attempt.key, createdAt: attempt.createdAt,
    ...(keepText ? { body: attempt.body } : {}) }));
    window.setTimeout(() => {
      try {
        const raw = sessionStorage.getItem(DRAFT_PREFIX + attempt.ownerId);
        if (raw && JSON.parse(raw).key === attempt.key) sessionStorage.removeItem(DRAFT_PREFIX + attempt.ownerId);
      } catch { /* Storage may be disabled. */ }
    }, Math.max(0, Date.parse(attempt.createdAt) + 86400000 - Date.now()));
  } catch { /* No auto-submission fallback. */ }
}

export class ResidentFailure extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function residentRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.method === "POST") {
    const response = await fetch("/api/app/csrf", { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) throw new ResidentFailure(response.status, "Sign-in could not be verified. Please sign in again.");
    const { csrf } = await response.json();
    headers.set("X-CSRF-Token", csrf);
  }
  let response: Response;
  try { response = await fetch(`/api/app/v2/resident/${path}`, { ...init, headers, credentials: "same-origin",
    cache: "no-store", signal: AbortSignal.timeout(20000) }); }
  catch { throw new ResidentFailure(0, "We could not confirm the save. Check or retry the same report."); }
  if (!response.ok) throw new ResidentFailure(response.status,
    response.status === 401 || response.status === 403 ? "Your session ended. Please sign in again."
      : response.status === 429 ? "The pilot limit has been reached. Please try later."
      : response.status === 404 ? "This item is unavailable or outside your account."
      : response.status === 409 ? "This attempt may already be saved. Check its status."
      : "The save could not be confirmed. Please check or retry.");
  return response;
}

export async function uploadPhoto(file: File): Promise<Stage> {
  if (!["image/jpeg", "image/png"].includes(file.type) || file.size > 4_000_000)
    throw new ResidentFailure(422, "Use a JPEG/PNG photo up to 4,000,000 bytes, or send text only.");
  const data = new FormData();
  data.append("image", file, "report-image"); // Do not forward the resident's original filename.
  data.append("retention_consent", "true");
  return (await residentRequest("media", { method: "POST", body: data })).json();
}

export function retryHeaders(attempt: { key: string; createdAt: string }) {
  return { "Content-Type": "application/json", "Idempotency-Key": attempt.key,
    "Idempotency-Key-Created-At": attempt.createdAt };
}

export function displayedTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
