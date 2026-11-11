import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { NextResponse } from "next/server";
import { safeReturnTo, type IdentitySettings } from "./settings";
import { PostgresSessionStore } from "./session-store";

// Injectable transport is an internal test seam; no environment-selected fake provider.
export function managedClient(settings: IdentitySettings, store: PostgresSessionStore,
  customFetch?: typeof fetch) {
  return new Auth0Client({
    customFetch,
    domain: settings.domain, clientId: settings.clientId, clientSecret: settings.clientSecret,
    secret: settings.cookieSecret, appBaseUrl: settings.appBaseUrl,
    authorizationParameters: { audience: "urn:airshedos:pilot-api",
      scope: "openid profile offline_access access:airshedos" },
    sessionStore: store, enableAccessTokenEndpoint: false, enableConnectAccountEndpoint: false,
    enableTelemetry: false, logoutStrategy: "oidc", includeIdTokenHintInOIDCLogoutUrl: false,
    signInReturnToPath: "/resident", httpTimeout: 5000,
    session: { rolling: true, absoluteDuration: 28800, inactivityDuration: 1800,
      cookie: { name: settings.secure ? "__Host-airshedos" : "airshedos-local",
        secure: settings.secure, sameSite: "lax", path: "/" } },
    transactionCookie: { secure: settings.secure, sameSite: "lax", path: "/" },
    onCallback: async (error, context, session) => {
      if (error || !session) return NextResponse.redirect(new URL("/sign-in?status=failed", settings.appBaseUrl));
      store.allowNewLogin(session);
      return NextResponse.redirect(new URL(safeReturnTo(context.returnTo), settings.appBaseUrl));
    },
    beforeSessionSaved: async (session) => ({ ...session, user: { sub: session.user.sub } }),
  });
}
