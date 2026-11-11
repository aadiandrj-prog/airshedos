import { NextRequest, NextResponse } from "next/server";
import { identityRuntime } from "../../../../../server/auth";
import { forwardApi } from "../../../../../server/gateway";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  try { return await forwardApi(request, (await context.params).path.join("/"), identityRuntime()); }
  catch { return NextResponse.json({ detail: "Service unavailable" }, { status: 503,
    headers: { "Cache-Control": "private, no-store" } }); }
}
export const GET = handle;
export const POST = handle;
