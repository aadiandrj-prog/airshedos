import { NextRequest, NextResponse } from "next/server";
import type { Auth0Client } from "@auth0/nextjs-auth0/server";
import type { IdentitySettings } from "./settings";
import { boundedBody, boundedBytes, permittedUpstream, validMutation } from "./security";

const privateHeaders = { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" };

export async function forwardApi(request: NextRequest, path: string,
  identity: { client: Auth0Client; settings: IdentitySettings } | null) {
  if (!permittedUpstream(request.method, path))
    return NextResponse.json({ detail: "Not found" }, { status: 404, headers: privateHeaders });
  try {
    if (!identity) return NextResponse.json({ detail: "Sign-in is not configured" }, { status: 503, headers: privateHeaders });
    const session = await identity.client.getSession(request);
    if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401, headers: privateHeaders });
    let body: Buffer | undefined;
    let contentType = "application/json";
    const extraHeaders: Record<string, string> = {};
    if (request.method === "POST") {
      if (!validMutation(request, identity.settings.appBaseUrl, session.csrf))
        return NextResponse.json({ detail: "Request verification failed" }, { status: 403, headers: privateHeaders });
      try {
        if (path === "resident/media") {
          contentType = request.headers.get("content-type") ?? "";
          if (!/^multipart\/form-data;.*boundary=/i.test(contentType) || contentType.length > 200)
            throw new Error("Invalid multipart request");
          body = await boundedBytes(request, 4_000_000 + 65536);
        } else body = await boundedBody(request);
      }
      catch { return NextResponse.json({ detail: "Invalid request" }, { status: 400, headers: privateHeaders }); }
      if (path === "resident/reports" || path.endsWith("/replies")) {
        for (const name of ["Idempotency-Key", "Idempotency-Key-Created-At"]) {
          const value = request.headers.get(name);
          if (!value || value.length > 64)
            return NextResponse.json({ detail: "Retry reference required" }, { status: 400, headers: privateHeaders });
          extraHeaders[name] = value;
        }
      }
    }
    const target = new URL(`/api/v2/${path}`, identity.settings.backend);
    for (const [key, value] of request.nextUrl.searchParams) {
      const allowed = ["limit", "offset", "q", "state", "assignment", "before_revision"];
      if (!allowed.includes(key) || value.length > 100)
        return NextResponse.json({ detail: "Invalid query" }, { status: 400, headers: privateHeaders });
      target.searchParams.append(key, value);
    }
    // Construct credentials from server session only. Forward no browser identity headers/cookies.
    const upstream = await fetch(target, { method: request.method, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(path.endsWith("/enrichments") || path.endsWith("/live-context") ? 65000 : 10000), headers: { Authorization: `Bearer ${session.tokenSet.accessToken}`,
        "X-AirshedOS-Session": String(session.appBinding), "Content-Type": contentType, ...extraHeaders },
      body: body ? new Uint8Array(body) : undefined });
    const content = new Uint8Array(await upstream.arrayBuffer());
    if (content.byteLength > 4_000_000) throw new Error("Response too large");
    return new NextResponse(content, { status: upstream.status, headers: { ...privateHeaders,
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
      ...(upstream.headers.get("Idempotent-Replayed") === "true" ? { "Idempotent-Replayed": "true" } : {}) } });
  } catch {
    return NextResponse.json({ detail: "Service unavailable. Please retry." }, { status: 503, headers: privateHeaders });
  }
}

