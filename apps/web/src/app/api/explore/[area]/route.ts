import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const areas = new Set(["delhi", "gurugram", "noida"]);
const headers = { "Cache-Control": "private, no-store", Pragma: "no-cache" };

export async function POST(request: NextRequest, context: { params: Promise<{ area: string }> }) {
  const { area } = await context.params;
  if (!areas.has(area) || request.nextUrl.search) return NextResponse.json({ detail: "Area not supported" }, { status: 404, headers });
  try {
    const origin = new URL(process.env.APP_BASE_URL!);
    const backend = new URL(process.env.BACKEND_API_BASE_URL!);
    const local = process.env.NODE_ENV !== "production" && ["localhost", "127.0.0.1"].includes(backend.hostname);
    if (backend.username || backend.password || backend.search || backend.hash || backend.pathname !== "/"
        || (backend.protocol !== "https:" && !(local && backend.protocol === "http:"))) throw new Error();
    if (request.headers.get("origin") !== origin.origin
        || ![null, "same-origin"].includes(request.headers.get("sec-fetch-site")))
      return NextResponse.json({ detail: "Request origin rejected" }, { status: 403, headers });
    if (request.headers.get("content-type") !== "application/json" || request.headers.get("content-length") && Number(request.headers.get("content-length")) > 32)
      return NextResponse.json({ detail: "Empty JSON object required" }, { status: 422, headers });
    const reader = request.body?.getReader();
    let text = "";
    if (!reader) throw new Error();
    try {
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        text += new TextDecoder().decode(chunk.value);
        if (text.length > 32) { await reader.cancel(); throw new Error(); }
      }
    } finally { reader.releaseLock(); }
    const value = JSON.parse(text);
    if (!value || Array.isArray(value) || typeof value !== "object" || Object.keys(value).length)
      return NextResponse.json({ detail: "Empty JSON object required" }, { status: 422, headers });
    const response = await fetch(new URL(`/api/v2/explore/areas/${area}/overview`, backend), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      cache: "no-store", signal: AbortSignal.timeout(70000), redirect: "error",
    });
    return NextResponse.json(await response.json(), { status: response.status, headers });
  } catch {
    return NextResponse.json({ detail: "Area overview is temporarily unavailable. Please retry." }, { status: 503, headers });
  }
}
