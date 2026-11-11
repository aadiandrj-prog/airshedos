import { NextRequest, NextResponse } from "next/server";
import { identityRuntime } from "./server/auth";
import { safeReturnTo } from "./server/settings";
import { needsAccessToken } from "./server/security";

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  let response: NextResponse;
  try {
    const runtime = identityRuntime();
    if (path.startsWith("/auth/")) {
      if (!["/auth/login", "/auth/callback", "/auth/backchannel-logout"].includes(path))
        response = NextResponse.json({ detail: "Not found" }, { status: 404 });
      else if (!runtime) response = NextResponse.json({ detail: "Sign-in is not configured" }, { status: 503 });
      else if ((path === "/auth/backchannel-logout" && request.method !== "POST")
          || (path !== "/auth/backchannel-logout" && request.method !== "GET"))
        response = NextResponse.json({ detail: "Method not allowed" }, { status: 405 });
      else {
        const target = new URL(request.url);
        if (path === "/auth/login") {
          const returnTo = safeReturnTo(target.searchParams.get("returnTo"));
          target.search = ""; // No query-supplied scope, redirect_uri, role or account-link options.
          target.searchParams.set("returnTo", returnTo);
        }
        response = await runtime.client.middleware(path === "/auth/login"
          ? new NextRequest(target, { headers: request.headers }) : request);
      }
    } else if (runtime && (path.startsWith("/resident") || path.startsWith("/authority")
        || path.startsWith("/api/app"))) {
      response = await runtime.client.middleware(request);
      if (needsAccessToken(path) && await runtime.client.getSession(request))
        await runtime.client.getAccessToken(request, response);
    } else response = NextResponse.next();
  } catch {
    response = NextResponse.json({ detail: "Sign-in service unavailable. Please retry." }, { status: 503 });
  }
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("X-Content-Type-Options", "nosniff");
  return response;
}

export const config = { matcher: ["/auth/:path*", "/resident/:path*", "/authority/:path*",
  "/api/app/:path*", "/sign-in"] };
