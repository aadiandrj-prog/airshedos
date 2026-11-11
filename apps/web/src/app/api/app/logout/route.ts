import { NextRequest, NextResponse } from "next/server";
import { identityRuntime } from "../../../../server/auth";
import { logoutSession } from "../../../../server/logout";
export async function POST(request: NextRequest) {
  try { return await logoutSession(request, identityRuntime()); }
  catch { return NextResponse.json({ detail: "Sign-out unavailable. Please retry." }, { status: 503 }); }
}
