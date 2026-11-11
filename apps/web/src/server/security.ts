import { timingSafeEqual } from "node:crypto";

export function needsAccessToken(path: string) {
  return path.startsWith("/resident") || path.startsWith("/authority")
    || path.startsWith("/api/app/v2/");
}

export function validMutation(request: Request, origin: string, csrf: unknown) {
  const supplied = request.headers.get("x-csrf-token");
  return request.headers.get("origin") === origin
    && [null, "same-origin", "none"].includes(request.headers.get("sec-fetch-site"))
    && typeof csrf === "string" && !!supplied && supplied.length === csrf.length
    && /^[a-f0-9]{64}$/.test(supplied)
    && timingSafeEqual(Buffer.from(supplied), Buffer.from(csrf));
}

const id = "[a-fA-F0-9-]{36}";
export function permittedUpstream(method: string, path: string) {
  const gets = ["me", "resident/reports", `resident/reports/${id}`, `resident/media/${id}`,
    `resident/submissions/${id}`,
    `authority/units/${id}/cases`, `authority/units/${id}/map`,
    `authority/units/${id}/cases/${id}`, `authority/units/${id}/cases/${id}/export`,
    `authority/units/${id}/cases/${id}/media/${id}`, `authority/units/${id}/memberships`,
    `authority/units/${id}/reviewers`, `authority/units/${id}/membership-proposals`,
    `authority/units/${id}/cases/${id}/history`, `authority/units/${id}/cases/${id}/evidence/${id}`,
    `authority/units/${id}/cases/${id}/export-v2`];
  const posts = ["resident/reports", "resident/media", "resident/context", `resident/reports/${id}/information-requests/${id}/replies`,
    `authority/units/${id}/cases/${id}/review-events`,
    ...["assignments", "internal-notes", "reporter-updates", "information-requests", "field-follow-ups", "external-references", "enrichments", "live-context"].map((action) => `authority/units/${id}/cases/${id}/${action}`),
    `authority/units/${id}/cases/${id}/field-follow-ups/${id}/events`,
    `authority/units/${id}/membership-proposals`, `authority/units/${id}/memberships/${id}/suspend`];
  return (method === "GET" ? gets : method === "POST" ? posts : [])
    .some((pattern) => new RegExp(`^${pattern}$`).test(path));
}

export async function boundedBody(request: Request, maximum = 8192) {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json"))
    throw new Error("JSON required");
  return boundedBytes(request, maximum);
}

export async function boundedBytes(request: Request, maximum: number) {
  const reader = request.body?.getReader();
  if (!reader) throw new Error("Body required");
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > maximum) { await reader.cancel(); throw new Error("Body too large"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks);
}
