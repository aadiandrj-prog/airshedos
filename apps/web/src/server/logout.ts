import { NextRequest, NextResponse } from "next/server";
import type { Auth0Client } from "@auth0/nextjs-auth0/server";
import type { IdentitySettings } from "./settings";
import type { PostgresSessionStore } from "./session-store";
import { validMutation } from "./security";

export async function logoutSession(request: NextRequest,
  identity: { client: Auth0Client; settings: IdentitySettings; store: PostgresSessionStore } | null) {
  try {
    if (!identity) return NextResponse.json({ detail: "Sign-in is not configured" }, { status: 503 });
    const session = await identity.client.getSession(request);
    if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
    if (!validMutation(request, identity.settings.appBaseUrl, session.csrf))
      return NextResponse.json({ detail: "Request verification failed" }, { status: 403 });
    // Revoke before any provider discovery/network, including provider failure.
    await identity.store.revokeBinding(String(session.appBinding));
    let destination = "/sign-in?status=signed-out";
    try {
      const url = new URL("/auth/logout", identity.settings.appBaseUrl);
      url.searchParams.set("returnTo", identity.settings.appBaseUrl);
      const result = await identity.client.middleware(new NextRequest(url, {
        headers: { cookie: request.headers.get("cookie") ?? "" } }));
      const location = result.headers.get("location");
      if (location && new URL(location).origin === new URL(identity.settings.issuer).origin)
        destination = location;
    } catch { /* Local logout is already durable; upstream logout remains best effort. */ }
    const response = NextResponse.json({ redirect: destination }, {
      headers: { "Cache-Control": "private, no-store" } });
    response.cookies.set(identity.settings.secure ? "__Host-airshedos" : "airshedos-local", "", {
      httpOnly: true, secure: identity.settings.secure, sameSite: "lax", path: "/", maxAge: 0 });
    return response;
  } catch { return NextResponse.json({ detail: "Sign-out unavailable. Please retry." }, { status: 503 }); }
}
