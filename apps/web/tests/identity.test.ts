import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { resolve } from "node:path";
import { after, test } from "node:test";
import { exportJWK, generateKeyPair, SignJWT } from "jose";
import { NextRequest, NextResponse } from "next/server";
import type { SessionData } from "@auth0/nextjs-auth0/types";
import { managedClient } from "../src/server/auth-client";
import { PostgresSessionStore } from "../src/server/session-store";
import { identitySettings, missingIdentityVariables, requiredIdentityVariables, safeReturnTo, type IdentitySettings } from "../src/server/settings";
import { boundedBody, needsAccessToken, permittedUpstream, validMutation } from "../src/server/security";
import { forwardApi } from "../src/server/gateway";
import { logoutSession } from "../src/server/logout";

const url = process.env.TEST_DATABASE_URL?.replace("postgresql+psycopg:", "postgresql:");
if (url) {
  const parsed = new URL(url);
  assert(["127.0.0.1", "localhost"].includes(parsed.hostname)
    && parsed.username === "seva_test" && parsed.pathname === "/seva_phase1_test",
  "Refusing any database except the named local synthetic test target");
}
const settings: IdentitySettings = { appBaseUrl: "https://app-fixture.invalid", backend: "https://api-fixture.invalid",
  issuer: "https://identity-fixture.invalid/", domain: "identity-fixture.invalid", clientId: "synthetic-bff",
  clientSecret: randomBytes(32).toString("hex"), cookieSecret: randomBytes(32).toString("hex"),
  encryptionKey: randomBytes(32).toString("hex"), databaseUrl: url ?? "", secure: true };
const stores: PostgresSessionStore[] = [];
const storeFor = (options = settings) => { const store = new PostgresSessionStore(options); stores.push(store); return store; };
const sha = (value: string) => createHash("sha256").update(value).digest("hex");
const data = (subject = "session-test-" + randomBytes(8).toString("hex")): SessionData => ({
  user: { sub: subject }, tokenSet: { accessToken: "synthetic-access-token-" + randomBytes(8).toString("hex"),
    refreshToken: "synthetic-refresh-token", expiresAt: Math.floor(Date.now()/1000) + 600 },
  internal: { sid: randomBytes(16).toString("hex"), createdAt: Math.floor(Date.now()/1000) },
});

test("missing identity diagnostics contain names only and require the API audience", () => {
  const privateValue = "synthetic-private-value-never-diagnosed";
  const env = Object.fromEntries(requiredIdentityVariables.map((name) => [name, privateValue]));
  delete env.AUTH0_AUDIENCE;
  delete env.SESSION_DATABASE_URL;
  const missing = missingIdentityVariables(env);
  assert.deepEqual(missing, ["SESSION_DATABASE_URL", "AUTH0_AUDIENCE"]);
  assert(!JSON.stringify(missing).includes(privateValue));
  assert.equal(identitySettings(env), null);
});
after(async () => { await Promise.all(stores.map((store) => store.pool.end())); });

test("return destinations and server-only configuration reject unsafe alternatives", () => {
  for (const value of ["https://evil.invalid", "//evil.invalid", "/\\evil.invalid", "%2f%2fevil.invalid", "/auth/callback", "\n/authority"])
    assert.equal(safeReturnTo(value), "/resident");
  assert.equal(safeReturnTo("/authority"), "/authority");
  const id = "11111111-1111-4111-8111-111111111111";
  assert.equal(safeReturnTo(`/authority/cases/${id}?unit=${id}`), `/authority/cases/${id}?unit=${id}`);
  for (const value of ["/authority/cases?next=//evil.invalid", `/authority/unit?unit=${id}&next=//evil.invalid`, "/authority/cases/%2f%2fevil.invalid"])
    assert.equal(safeReturnTo(value), "/resident");
  assert.equal(identitySettings({}), null);
  const env = { APP_BASE_URL: settings.appBaseUrl, BACKEND_API_BASE_URL: settings.backend,
    AUTH0_DOMAIN: settings.domain, AUTH0_CLIENT_ID: settings.clientId, AUTH0_CLIENT_SECRET: settings.clientSecret,
    AUTH0_SECRET: settings.cookieSecret, SESSION_ENCRYPTION_KEY: settings.encryptionKey,
    SESSION_DATABASE_URL: "postgresql://synthetic:synthetic@127.0.0.1/test", AUTH0_AUDIENCE: "urn:airshedos:pilot-api" };
  assert.equal(identitySettings(env)?.secure, true);
  assert.throws(() => identitySettings({ ...env, APP_BASE_URL: "http://public.invalid" }));
  assert.throws(() => identitySettings({ ...env, NODE_ENV: "production", AUTH_ALLOW_LOCAL_HTTP: "1", APP_BASE_URL: "http://localhost:3000" }));
});

test("CSRF, exact Origin, Fetch Metadata, paths and request bounds are enforced", async () => {
  const csrf = randomBytes(32).toString("hex");
  const req = (origin: string, nonce = csrf, site = "same-origin") => new Request(settings.appBaseUrl, {
    method: "POST", headers: { Origin: origin, "X-CSRF-Token": nonce, "Sec-Fetch-Site": site } });
  assert(validMutation(req(settings.appBaseUrl), settings.appBaseUrl, csrf));
  assert(!validMutation(req("https://evil.invalid"), settings.appBaseUrl, csrf));
  assert(!validMutation(req(settings.appBaseUrl, "0".repeat(64)), settings.appBaseUrl, csrf));
  assert(!validMutation(req(settings.appBaseUrl, csrf, "cross-site"), settings.appBaseUrl, csrf));
  assert(!validMutation(new Request(settings.appBaseUrl), settings.appBaseUrl, csrf));
  for (const path of ["https://evil.invalid", "../resident/reports", "resident/reports/../../me", "operator/grant", "resident/reports/arbitrary"])
    assert(!permittedUpstream("POST", path));
  assert(permittedUpstream("GET", "resident/reports"));
  assert(!permittedUpstream("GET", "resident/context"));
  assert(permittedUpstream("POST", "resident/context"));
  const contextPath = "authority/units/" + "1".repeat(36) + "/cases/" + "2".repeat(36) + "/live-context";
  assert(!permittedUpstream("GET", contextPath));
  assert(permittedUpstream("POST", contextPath));
  assert(!needsAccessToken("/api/app/logout"));
  assert(!needsAccessToken("/api/app/csrf"));
  assert(needsAccessToken("/api/app/v2/me"));
  await assert.rejects(boundedBody(new Request(settings.appBaseUrl, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: "x".repeat(8193) })));
});

test("SDK sessions are sealed in PG; second store reads, logout fences refresh and creation", { skip: !url }, async () => {
  const store = storeFor(), second = storeFor();
  const id = randomBytes(16).toString("hex"), session = data();
  await assert.rejects(store.set(id, session));
  store.allowNewLogin(session);
  await store.set(id, session);
  assert.equal((await second.get(id))?.user.sub, session.user.sub);
  const rows = await store.pool.query(`SELECT s.*,t.sealed_data FROM auth_sessions s
    JOIN auth_session_secrets t ON t.session_id=s.id WHERE sdk_key_hash=$1`, [sha(id)]);
  const cipher = Buffer.from(rows.rows[0].sealed_data).toString();
  assert(!cipher.includes(session.tokenSet.accessToken));
  assert(!cipher.includes(session.tokenSet.refreshToken!));
  assert.equal(cipher.split(".").length, 5);
  assert.equal(rows.rows[0].binding_hash, sha(String(session.appBinding)));
  await Promise.all([store.update(id, session), second.delete(id)]);
  assert.equal(await store.get(id), null);
  assert.equal(await second.update(id, session), false);
  await assert.rejects(store.set(id, session));
  const after = await store.pool.query("SELECT revoked_at FROM auth_sessions WHERE sdk_key_hash=$1", [sha(id)]);
  assert(after.rows[0].revoked_at);
});

test("expired sessions and key rotation fail safely without resurrecting tokens", { skip: !url }, async () => {
  const store = storeFor(), session = data(), id = randomBytes(16).toString("hex");
  store.allowNewLogin(session); await store.set(id, session);
  const rotated = storeFor({ ...settings, encryptionKey: randomBytes(32).toString("hex"),
    previousEncryptionKey: settings.encryptionKey });
  assert.equal((await rotated.get(id))?.user.sub, session.user.sub);
  const missingKey = storeFor({ ...settings, encryptionKey: randomBytes(32).toString("hex") });
  assert.equal(await missingKey.get(id), null);
  await store.pool.query("UPDATE auth_sessions SET idle_expires_at=now()-interval '1 second' WHERE sdk_key_hash=$1", [sha(id)]);
  assert.equal(await store.get(id), null);
  assert.equal(await store.update(id, session), false);
});

test("actual SDK, BFF and Python API share verified PostgreSQL identity and logout", { skip: !url }, async (context) => {
  const store = storeFor();
  const { privateKey, publicKey } = await generateKeyPair("RS256");
  const jwk = { ...await exportJWK(publicKey), kid: "fixture-key", use: "sig", alg: "RS256" };
  const listener = createServer();
  await new Promise<void>((done) => listener.listen(0, "127.0.0.1", done));
  const address = listener.address();
  assert(address && typeof address !== "string");
  const port = address.port;
  await new Promise<void>((done) => listener.close(() => done()));
  const apiRoot = resolve(process.cwd(), "../api");
  const api = spawn(process.env.SEVA_TEST_PYTHON ?? resolve(apiRoot, ".venv/bin/python"), ["tests/serve_identity_fixture.py", String(port)], {
    cwd: apiRoot, stdio: "ignore", env: { PATH: process.env.PATH, NODE_ENV: "test",
      TEST_DATABASE_URL: process.env.TEST_DATABASE_URL!, TEST_PUBLIC_JWK: JSON.stringify(jwk) } });
  context.after(async () => {
    if (api.exitCode === null) await new Promise<void>((done) => {
      api.once("exit", () => done()); api.kill("SIGTERM"); });
  });
  const backend = `http://127.0.0.1:${port}`;
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { ready = (await fetch(backend + "/health")).ok; } catch { /* Startup only. */ }
    if (ready || api.exitCode !== null) break;
    await new Promise((done) => setTimeout(done, 100));
  }
  assert(ready, "Synthetic identity-slice API must be alive");
  let nonce = "", challenge = "";
  const subject = "sdk-verified-" + randomBytes(8).toString("hex"), sid = randomBytes(16).toString("hex");
  const sign = (claims: Record<string, unknown>) => new SignJWT(claims).setProtectedHeader({ alg: "RS256", kid: "fixture-key" })
    .setIssuer(settings.issuer).setAudience(settings.clientId).setIssuedAt().setExpirationTime("10m").sign(privateKey);
  const accessToken = await new SignJWT({ sub: subject, client_id: settings.clientId,
    scope: "access:airshedos", jti: randomBytes(16).toString("hex") })
    .setProtectedHeader({ alg: "RS256", kid: "fixture-key", typ: "at+jwt" })
    .setIssuer(settings.issuer).setAudience("urn:airshedos:pilot-api")
    .setIssuedAt().setExpirationTime("10m").sign(privateKey);
  const transport: typeof fetch = async (input, init) => {
    const target = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const json = (content: unknown) => new Response(JSON.stringify(content), { headers: { "Content-Type": "application/json" } });
    if (target.pathname === "/.well-known/openid-configuration") return json({ issuer: settings.issuer,
      authorization_endpoint: settings.issuer + "authorize", token_endpoint: settings.issuer + "oauth/token",
      jwks_uri: settings.issuer + ".well-known/jwks.json", end_session_endpoint: settings.issuer + "oidc/logout",
      response_types_supported: ["code"], id_token_signing_alg_values_supported: ["RS256"],
      token_endpoint_auth_methods_supported: ["client_secret_post", "client_secret_basic"] });
    if (target.pathname === "/.well-known/jwks.json") return json({ keys: [jwk] });
    if (target.pathname === "/oauth/token") {
      const form = new URLSearchParams(String(init?.body));
      assert.equal(form.get("grant_type"), "authorization_code");
      assert.equal(createHash("sha256").update(form.get("code_verifier")!).digest("base64url"), challenge);
      return json({ access_token: accessToken, refresh_token: "synthetic-sdk-refresh",
        token_type: "Bearer", expires_in: 600, id_token: await sign({ sub: subject, sid, nonce }) });
    }
    throw new Error("Unexpected external request in deterministic SDK test");
  };
  const client = managedClient(settings, store, transport);
  const login = await client.middleware(new NextRequest(settings.appBaseUrl + "/auth/login?returnTo=/authority"));
  assert.equal(login.status, 307);
  const target = new URL(login.headers.get("location")!);
  nonce = target.searchParams.get("nonce")!; challenge = target.searchParams.get("code_challenge")!;
  assert(nonce && challenge && target.searchParams.get("code_challenge_method") === "S256");
  const cookies = login.cookies.getAll().map((c) => `${c.name}=${c.value}`).join("; ");
  const state = target.searchParams.get("state")!;
  const invalid = await client.middleware(new NextRequest(settings.appBaseUrl + "/auth/callback?code=fake&state=invalid", { headers: { Cookie: cookies } }));
  assert(invalid.headers.get("location")?.includes("status=failed"));
  const callback = await client.middleware(new NextRequest(settings.appBaseUrl + `/auth/callback?code=synthetic&state=${encodeURIComponent(state)}`, { headers: { Cookie: cookies } }));
  assert.equal(callback.headers.get("location"), settings.appBaseUrl + "/authority");
  const sessionCookie = callback.cookies.get("__Host-airshedos")!;
  assert(sessionCookie && sessionCookie.httpOnly && sessionCookie.secure && sessionCookie.path === "/");
  assert.equal(sessionCookie.domain, undefined);
  assert.equal(sessionCookie.sameSite, "lax");
  assert(!sessionCookie.value.includes(accessToken));
  const sessionRequest = new NextRequest(settings.appBaseUrl + "/resident", {
    headers: { Cookie: `${sessionCookie.name}=${sessionCookie.value}` } });
  const read = await client.getSession(sessionRequest);
  assert.equal(read?.user.sub, subject);
  assert.equal(read?.tokenSet.accessToken, accessToken);
  const gateway = { client, settings: { ...settings, backend } };
  const forged = new NextRequest(settings.appBaseUrl + "/api/app/v2/me", { headers: {
    Cookie: `${sessionCookie.name}=${sessionCookie.value}`, Authorization: "Bearer forged",
    "X-AirshedOS-Session": "0".repeat(64), "X-Role": "UNIT_ADMIN" } });
  for (const path of ["resident/context", `authority/units/${"1".repeat(36)}/cases/${"2".repeat(36)}/live-context`]) {
    for (const origin of [settings.appBaseUrl, "https://evil.invalid"]) {
      const request = new NextRequest(settings.appBaseUrl + "/api/app/v2/" + path, { method:"POST",
        headers:{Cookie:`${sessionCookie.name}=${sessionCookie.value}`, Origin:origin,"Content-Type":"application/json"}, body:"{}" });
      assert.equal((await forwardApi(request,path,gateway)).status,403);
    }
  }
  const identity = await forwardApi(forged, "me", gateway);
  assert.equal(identity.status, 200);
  const me = await identity.json();
  const ownId = (await store.pool.query("SELECT id FROM users WHERE issuer=$1 AND subject=$2", [settings.issuer, subject])).rows[0].id;
  assert.equal(me.id, ownId); assert.deepEqual(me.units, []);
  const direct = await fetch(backend + "/api/v2/me", { headers: { Authorization: "Bearer " + accessToken,
    "X-AirshedOS-Session": String(read?.appBinding) } });
  assert.equal(direct.status, 200);
  const unsafe = await forwardApi(new NextRequest(settings.appBaseUrl + "/api/app/v2/authority/action", {
    method: "POST", headers: { Cookie: `${sessionCookie.name}=${sessionCookie.value}`, Origin: settings.appBaseUrl,
      "X-CSRF-Token": "0".repeat(64), "Content-Type": "application/json" }, body: "{}" }),
    "authority/units/00000000-0000-4000-8000-000000000000/cases/00000000-0000-4000-8000-000000000000/review-events", gateway);
  assert.equal(unsafe.status, 403);
  const logout = await sign({ sub: subject, sid, jti: randomBytes(16).toString("hex"),
    events: { "http://schemas.openid.net/event/backchannel-logout": {} } });
  const response = await client.middleware(new NextRequest(settings.appBaseUrl + "/auth/backchannel-logout", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ logout_token: logout }) }));
  assert.equal(response.status, 204);
  assert.equal(await client.getSession(sessionRequest), null);
  assert.equal((await forwardApi(forged, "me", gateway)).status, 401);
  const revoked = await fetch(backend + "/api/v2/me", { headers: { Authorization: "Bearer " + accessToken,
    "X-AirshedOS-Session": String(read?.appBinding) } });
  assert.equal(revoked.status, 401);
  // A new validated login remains locally revocable with an expired access token
  // and a provider outage. No refresh is needed to obtain CSRF or execute logout.
  const login2 = await client.middleware(new NextRequest(settings.appBaseUrl + "/auth/login"));
  const target2 = new URL(login2.headers.get("location")!);
  nonce = target2.searchParams.get("nonce")!; challenge = target2.searchParams.get("code_challenge")!;
  const callback2 = await client.middleware(new NextRequest(settings.appBaseUrl +
    `/auth/callback?code=synthetic&state=${encodeURIComponent(target2.searchParams.get("state")!)}`, {
    headers: { Cookie: login2.cookies.getAll().map((c) => `${c.name}=${c.value}`).join("; ") } }));
  const cookie2 = callback2.cookies.get("__Host-airshedos")!;
  const request2 = new NextRequest(settings.appBaseUrl + "/resident", {
    headers: { Cookie: `${cookie2.name}=${cookie2.value}` } });
  const session2 = (await client.getSession(request2))!;
  await client.updateSession(request2, NextResponse.next(), { ...session2,
    tokenSet: { ...session2.tokenSet, expiresAt: 1 } });
  const unavailable = managedClient(settings, store, async () => { throw new Error("Synthetic provider outage"); });
  const localLogout = await logoutSession(new NextRequest(settings.appBaseUrl + "/api/app/logout", {
    method: "POST", headers: { Cookie: `${cookie2.name}=${cookie2.value}`, Origin: settings.appBaseUrl,
      "X-CSRF-Token": String(session2.csrf), "Content-Type": "application/json" }, body: "{}" }),
    { client: unavailable, store, settings });
  assert.equal(localLogout.status, 200);
  assert.deepEqual(await localLogout.json(), { redirect: "/sign-in?status=signed-out" });
  assert.equal(await client.getSession(request2), null);
  assert.equal((await fetch(backend + "/api/v2/me", { headers: { Authorization: "Bearer " + accessToken,
    "X-AirshedOS-Session": String(session2.appBinding) } })).status, 401);
});

test("public overview proxy restricts area, origin and body and never forwards identity", async () => {
  const { POST } = await import("../src/app/api/explore/[area]/route");
  const beforeApp = process.env.APP_BASE_URL, beforeBackend = process.env.BACKEND_API_BASE_URL;
  const originalFetch = globalThis.fetch;
  process.env.APP_BASE_URL = settings.appBaseUrl; process.env.BACKEND_API_BASE_URL = settings.backend;
  let calls = 0;
  globalThis.fetch = (async (input, init) => {
    calls++; assert.equal(String(input), settings.backend + "/api/v2/explore/areas/delhi/overview");
    assert.deepEqual(init?.headers, { "Content-Type": "application/json" });
    assert.equal(init?.body, "{}"); assert.equal(init?.cache, "no-store");
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  const request = (origin = settings.appBaseUrl, body = "{}") => new NextRequest(settings.appBaseUrl + "/api/explore/delhi", { method: "POST", headers: { Origin: origin, "Content-Type": "application/json", Authorization: "synthetic-browser-token", Cookie: "synthetic-private-session" }, body });
  const params = (area = "delhi") => ({ params: Promise.resolve({ area }) });
  try {
    assert.equal((await POST(request("https://other.invalid"), params())).status, 403);
    assert.equal((await POST(request(), params("world"))).status, 404);
    assert.equal((await POST(request(settings.appBaseUrl, '{"latitude":1}'), params())).status, 422);
    assert.equal(calls, 0);
    const result = await POST(request(), params()); assert.equal(result.status, 200);
    assert.equal(result.headers.get("Cache-Control"), "private, no-store"); assert.equal(calls, 1);
  } finally {
    globalThis.fetch = originalFetch;
    if (beforeApp === undefined) delete process.env.APP_BASE_URL; else process.env.APP_BASE_URL = beforeApp;
    if (beforeBackend === undefined) delete process.env.BACKEND_API_BASE_URL; else process.env.BACKEND_API_BASE_URL = beforeBackend;
  }
});
