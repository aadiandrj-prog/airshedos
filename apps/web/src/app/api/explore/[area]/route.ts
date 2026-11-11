import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const areas = new Set(["delhi", "gurugram", "noida", "nearby"]);
const headers = { "Cache-Control": "private, no-store", Pragma: "no-cache" };
const invalid = () => NextResponse.json({ detail: "Valid bounded location request required" }, { status: 422, headers });

export async function POST(request: NextRequest, context: { params: Promise<{ area: string }> }) {
  const { area } = await context.params;
  if (!areas.has(area) || request.nextUrl.search)
    return NextResponse.json({ detail: "Area not supported" }, { status: 404, headers });
  try {
    const origin = new URL(process.env.APP_BASE_URL!);
    const backend = new URL(process.env.BACKEND_API_BASE_URL!);
    const local = process.env.NODE_ENV !== "production" && ["localhost", "127.0.0.1"].includes(backend.hostname);
    if (backend.username || backend.password || backend.search || backend.hash || backend.pathname !== "/"
        || (backend.protocol !== "https:" && !(local && backend.protocol === "http:"))) throw new Error();
    if (request.headers.get("origin") !== origin.origin
        || ![null, "same-origin"].includes(request.headers.get("sec-fetch-site")))
      return NextResponse.json({ detail: "Request origin rejected" }, { status: 403, headers });
    if (request.headers.get("content-type") !== "application/json"
        || Number(request.headers.get("content-length")) > 128) return invalid();
    const reader = request.body?.getReader();
    if (!reader) return invalid();
    let value: unknown;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const bytes = await Promise.race([
        (async () => {
          const chunks: Uint8Array[] = []; let length = 0;
          for (;;) {
            const chunk = await reader.read(); if (chunk.done) break;
            length += chunk.value.length;
            if (length > 128) throw new Error();
            chunks.push(chunk.value);
          }
          return Buffer.concat(chunks);
        })(),
        new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error()), 5000); }),
      ]);
      value = JSON.parse(bytes.toString("utf8"));
    } catch { return invalid(); }
    finally { clearTimeout(timer); await reader.cancel().catch(() => {}); reader.releaseLock(); }
    if (!value || Array.isArray(value) || typeof value !== "object") return invalid();
    const body = value as Record<string, unknown>;
    let outgoing = "{}";
    if (area === "nearby") {
      const { latitude, longitude } = body;
      if (Object.keys(body).length !== 2 || typeof latitude !== "number" || typeof longitude !== "number"
          || !Number.isFinite(latitude) || !Number.isFinite(longitude)
          || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return invalid();
      outgoing = JSON.stringify({ latitude: Math.round(latitude * 200) / 200, longitude: Math.round(longitude * 200) / 200 });
    } else if (Object.keys(body).length) return invalid();
    const response = await fetch(new URL(`/api/v2/explore/areas/${area}/overview`, backend), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: outgoing,
      cache: "no-store", signal: AbortSignal.timeout(70000), redirect: "error",
    });
    return NextResponse.json(await response.json(), { status: response.status, headers });
  } catch {
    return NextResponse.json({ detail: "Area overview is temporarily unavailable. Please retry." }, { status: 503, headers });
  }
}
