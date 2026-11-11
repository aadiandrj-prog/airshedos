import { NextResponse } from "next/server";
import { identityRuntime } from "../../../../server/auth";

export const dynamic = "force-dynamic";
export async function GET() {
  try {
    const identity = identityRuntime();
    if (!identity) return NextResponse.json({ detail: "Sign-in is not configured" }, { status: 503 });
    const session = await identity.client.getSession();
    if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
    return NextResponse.json({ csrf: session.csrf }, { headers: { "Cache-Control": "private, no-store" } });
  } catch { return NextResponse.json({ detail: "Sign-in unavailable" }, { status: 503 }); }
}
