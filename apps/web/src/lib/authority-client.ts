import type { components } from "./api-schema";
export type Workspace = components["schemas"]["AuthorityWorkspace"];
export type Queue = components["schemas"]["AuthorityList"];
export type Reviewer = { id: string; role: string; label: string };
export type Fragment = { id: string; source: string; policy_version: string; state: string;
  payload: Record<string, unknown> | null; expires_at: string; observed_at: string | null;
  retrieved_at: string; attribution: string };
export type Evidence = { id: string; version: number; input_policy: string; created_at: string; expires_at: string; fragments: Fragment[] };
export class AuthorityFailure extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function authorityRequest(unit: string, path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.method === "POST") {
    const csrf = await fetch("/api/app/csrf", { cache: "no-store", credentials: "same-origin" });
    if (!csrf.ok) throw new AuthorityFailure(csrf.status, "Your session could not be verified. Please sign in again.");
    headers.set("X-CSRF-Token", (await csrf.json()).csrf); headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try { response = await fetch(`/api/app/v2/authority/units/${unit}/${path}`, { ...init, headers,
    cache: "no-store", credentials: "same-origin", signal: AbortSignal.timeout(path.endsWith("/enrichments") || path.endsWith("/live-context") ? 70000 : 20000) }); }
  catch { throw new AuthorityFailure(0, "The action could not be confirmed. Reload the current case before trying again."); }
  if (!response.ok) throw new AuthorityFailure(response.status,
    response.status === 409 ? "This case changed or the action conflicts with its current state. Reload and review before trying again."
    : response.status === 401 || response.status === 403 ? "Your session or permission no longer allows this action."
    : response.status === 404 ? "This case or unit is unavailable to your account."
    : response.status === 429 ? "The configured pilot limit has been reached. Manual review is still available."
    : response.status === 422 ? "Check the required text, reason and current state before trying again."
    : "The service could not complete this action. The saved report remains available; reload before retrying.");
  return response;
}
export function reviewLabel(value: string) {
  return ({ NEW:"Awaiting review", UNDER_REVIEW:"Under review", ACKNOWLEDGED:"Acknowledged internally",
    MONITORING:"Monitoring", CLOSED_NO_ACTION:"Closed — review ended", REOPEN:"Reopen for review" } as Record<string,string>)[value] ?? value;
}
