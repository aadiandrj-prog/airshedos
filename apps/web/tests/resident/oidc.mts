/** Local HTTPS OIDC provider fixture only. Never imported by the application. */
import { createServer } from "node:https";
import { readFileSync } from "node:fs";
import { createHash, randomBytes } from "node:crypto";
import { exportJWK, importPKCS8, importSPKI, SignJWT } from "jose";

const issuer = process.env.TEST_OIDC_ISSUER!;
const base = process.env.TEST_WEB_BASE!;
if (issuer !== "https://resident-fixture.invalid/" || !/^https?:\/\/127\.0\.0\.1:\d+$/.test(base)) throw new Error("Local fixture origins required");
const root = process.env.TEST_CERT_ROOT!;
const privateKey = await importPKCS8(readFileSync(root + "/server-key.pem", "utf8"), "RS256");
// Node extracts the certificate's public key; private material never leaves this test process.
const { createPublicKey } = await import("node:crypto");
const publicPem = createPublicKey(readFileSync(root + "/server-key.pem")).export({ type: "spki", format: "pem" }).toString();
const publicKey = await importSPKI(publicPem, "RS256");
const jwk = { ...await exportJWK(publicKey), kid: "resident-fixture-key", alg: "RS256", use: "sig" };
type Authorization = { challenge: string; nonce: string; state: string; redirect: string };
const requests = new Map<string, Authorization>();
const codes = new Map<string, Authorization & { subject: string; sid: string }>();
const refreshes = new Map<string, { subject: string; sid: string }>();
const clientId = "resident-fixture-client";
const secret = process.env.TEST_CLIENT_SECRET!;
const subjects: Record<string, string> = { "resident-a": process.env.TEST_SUBJECT_A!, "resident-b": process.env.TEST_SUBJECT_B!,
  "reviewer-a": process.env.TEST_REVIEWER_A!, "reviewer-two": process.env.TEST_REVIEWER_TWO!,
  "admin-a": process.env.TEST_ADMIN_A!, "reviewer-b": process.env.TEST_REVIEWER_B! };
const issue = (payload: Record<string, unknown>, audience: string, typ: string) => new SignJWT(payload)
  .setProtectedHeader({ alg: "RS256", kid: jwk.kid, typ }).setIssuer(issuer).setAudience(audience)
  .setIssuedAt().setExpirationTime("10m").sign(privateKey);
const server = createServer({ key: readFileSync(root + "/server-key.pem"), cert: readFileSync(root + "/server.pem") }, async (req, res) => {
  const url = new URL(req.url!, issuer);
  const json = (body: unknown, status=200) => { res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" }); res.end(JSON.stringify(body)); };
  try {
    if (url.pathname === "/.well-known/openid-configuration") return json({ issuer,
      authorization_endpoint: issuer + "authorize", token_endpoint: issuer + "oauth/token",
      jwks_uri: issuer + ".well-known/jwks.json", end_session_endpoint: issuer + "oidc/logout",
      response_types_supported: ["code"], id_token_signing_alg_values_supported: ["RS256"],
      token_endpoint_auth_methods_supported: ["client_secret_post", "client_secret_basic"] });
    if (url.pathname === "/.well-known/jwks.json") return json({ keys: [jwk] });
    if (url.pathname === "/authorize") {
      if (url.searchParams.get("client_id") !== clientId || url.searchParams.get("redirect_uri") !== base + "/auth/callback"
          || url.searchParams.get("code_challenge_method") !== "S256") return json({ error: "invalid_request" }, 400);
      const id = randomBytes(16).toString("hex");
      requests.set(id, { challenge: url.searchParams.get("code_challenge")!, nonce: url.searchParams.get("nonce")!,
        state: url.searchParams.get("state")!, redirect: base + "/auth/callback" });
      res.writeHead(200, { "Content-Type": "text/html", "Cache-Control": "no-store" });
      res.end(`<html><head><title>Synthetic identity fixture</title></head><body><h1>Local synthetic sign-in</h1><p>No real identity provider or user account is used.</p><form method="post" action="/fixture-login"><input type="hidden" name="request" value="${id}"><label>Synthetic resident<select name="resident"><option value="resident-a">Resident A</option><option value="resident-b">Resident B</option><option value="reviewer-a">Synthetic approved reviewer A</option><option value="reviewer-two">Synthetic second reviewer A</option><option value="admin-a">Synthetic unit admin A</option><option value="reviewer-b">Synthetic reviewer in other unit</option></select></label><button type="submit">Continue synthetic sign-in</button></form></body></html>`);
      return;
    }
    if (req.method === "POST" && ["/fixture-login", "/oauth/token"].includes(url.pathname)) {
      let body = "";
      for await (const chunk of req) { body += chunk; if (body.length > 16384) return json({ error: "invalid_request" }, 413); }
      const form = new URLSearchParams(body);
      if (url.pathname === "/fixture-login") {
        const authorization = requests.get(form.get("request")!); requests.delete(form.get("request")!);
        const subject = subjects[form.get("resident")!];
        if (!authorization || !subject) return json({ error: "invalid_request" }, 400);
        const code = randomBytes(24).toString("hex");
        codes.set(code, { ...authorization, subject, sid: randomBytes(16).toString("hex") });
        const target = new URL(authorization.redirect); target.searchParams.set("code", code); target.searchParams.set("state", authorization.state);
        res.writeHead(303, { Location: target.toString(), "Cache-Control": "no-store" }); res.end(); return;
      }
      const basic = req.headers.authorization?.startsWith("Basic ") ? Buffer.from(req.headers.authorization.slice(6), "base64").toString().split(":") : [];
      if ((form.get("client_id") ?? basic[0]) !== clientId || (form.get("client_secret") ?? basic[1]) !== secret) return json({ error: "invalid_client" }, 401);
      let identity: { subject: string; sid: string };
      let nonce: string | undefined;
      if (form.get("grant_type") === "refresh_token") {
        const existing = refreshes.get(form.get("refresh_token")!); refreshes.delete(form.get("refresh_token")!);
        if (!existing) return json({ error: "invalid_grant" }, 400);
        identity = existing;
      } else {
        const authorization = codes.get(form.get("code")!); codes.delete(form.get("code")!);
        const challenge = createHash("sha256").update(form.get("code_verifier") ?? "").digest("base64url");
        if (!authorization || authorization.challenge !== challenge || form.get("redirect_uri") !== authorization.redirect) return json({ error: "invalid_grant" }, 400);
        identity = authorization; nonce = authorization.nonce;
      }
      const refresh = randomBytes(32).toString("hex"); refreshes.set(refresh, identity);
      return json({ access_token: await issue({ sub: identity.subject, client_id: clientId,
        jti: randomBytes(16).toString("hex"), scope: "access:airshedos" }, "urn:airshedos:pilot-api", "at+jwt"),
        id_token: await issue({ sub: identity.subject, sid: identity.sid, ...(nonce ? { nonce } : {}) }, clientId, "JWT"),
        token_type: "Bearer", expires_in: 600, refresh_token: refresh });
    }
    if (url.pathname === "/oidc/logout") { res.writeHead(303, { Location: base }); res.end(); return; }
    return json({ error: "not_found" }, 404);
  } catch { return json({ error: "synthetic_provider_failure" }, 500); }
});
server.listen(Number(new URL(process.env.TEST_OIDC_TRANSPORT!).port), "127.0.0.1");
