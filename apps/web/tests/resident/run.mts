/** Explicit local browser harness: real SDK and PG, synthetic HTTPS OIDC, no dev-login route. */
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { get as httpsGet } from "node:https";
import { readFileSync } from "node:fs";
import { mkdtemp, realpath, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";

const db = process.env.TEST_DATABASE_URL;
if (!db) throw new Error("Explicit local TEST_DATABASE_URL required");
const parsed = new URL(db.replace("postgresql+psycopg:", "postgresql:"));
if (parsed.hostname !== "127.0.0.1" || parsed.username !== "seva_test" || parsed.pathname !== "/seva_phase1_test") throw new Error("Named disposable local database required");
const apiRoot = resolve(process.cwd(), "../api");
const python = process.env.SEVA_TEST_PYTHON ?? resolve(apiRoot, ".venv/bin/python");
const root = await realpath(await mkdtemp(join(tmpdir(), "airshedos-resident-")));
const children: ChildProcess[] = [];
const diagnostics = new Map<ChildProcess, string>();
const port = async () => {
  const server = createServer(); await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  const address = server.address(); if (!address || typeof address === "string") throw new Error("No local port");
  await new Promise<void>((done) => server.close(() => done())); return address.port;
};
const release = process.argv.includes("--release");
if (release) {
  // Standalone output inlines public settings at build time. Never inherit a real
  // Maps browser credential for this synthetic production rehearsal.
  const built = spawnSync("npm",["run","build"],{cwd:process.cwd(),stdio:"inherit",env:{...process.env,NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY:"",NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID:"",NEXT_PUBLIC_PILOT_MAPS_APPROVED:"0",NEXT_TELEMETRY_DISABLED:"1"}});
  if (built.status !== 0) throw new Error("Synthetic release build failed");
  const {cp} = await import("node:fs/promises");
  await cp(".next/static",".next/standalone/.next/static",{recursive:true});
  await cp("public",".next/standalone/public",{recursive:true});
}
const [oidcPort, apiPort, webPort, nextPort] = await Promise.all([port(), port(), port(), port()]);
const issuer = "https://resident-fixture.invalid/", transport = `https://127.0.0.1:${oidcPort}/`, base = `${release ? "https" : "http"}://127.0.0.1:${webPort}`;
const apiBase = `${release ? "https" : "http"}://127.0.0.1:${apiPort}`;
const prefix = randomBytes(6).toString("hex");
const identities = { TEST_REVIEWER_A: `reviewer-a-${prefix}`, TEST_REVIEWER_TWO: `reviewer-two-${prefix}`,
  TEST_ADMIN_A: `admin-a-${prefix}`, TEST_REVIEWER_B: `reviewer-b-${prefix}` };
const environment = { ...identities, SEVA_CAPTURE_FINAL: process.env.SEVA_CAPTURE_FINAL ?? "0", SEVA_CAPTURE_OVERVIEW: process.env.SEVA_CAPTURE_OVERVIEW ?? "0", SEVA_CAPTURE_STAGE: process.env.SEVA_CAPTURE_STAGE ?? "after", APP_MODE:"pilot", PATH: process.env.PATH, NODE_ENV: release ? "production" : "development", NEXT_TELEMETRY_DISABLED: "1", TEST_DATABASE_URL: db,
  NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY: "", NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID: "",
  SEVA_RECOVERY_EPOCH: randomUUID(), SEVA_TEST_RELEASE: release ? "1" : "0", SEVA_TEST_CONTINUOUS_WORKER:"1",
  TEST_OIDC_ISSUER: issuer, TEST_OIDC_TRANSPORT: transport, TEST_PRIVATE_ROOT: join(root, "private"), SSL_CERT_FILE: join(root, "ca.pem") };
function start(command: string, args: string[], cwd: string, env: NodeJS.ProcessEnv) {
  const child = spawn(command, args, { cwd, env, detached: true, stdio: ["ignore", "pipe", "pipe"] }); children.push(child);
  const collect = (chunk: Buffer) => {
    let value = chunk.toString();
    for (const [name, secret] of Object.entries(env)) if (/SECRET|KEY|DATABASE_URL/.test(name) && secret && secret.length > 6) value = value.replaceAll(secret, "[redacted]");
    value = value.replace(/([?&](?:code|state|nonce|session_state)=)[^&\s]+/g, "$1[redacted]");
    diagnostics.set(child, ((diagnostics.get(child) ?? "") + value).slice(-8000));
    if (value.includes("Synthetic authentication failure:")) process.stderr.write(value);
  };
  child.stdout?.on("data", collect); child.stderr?.on("data", collect);
  return child;
}
try {
  const cert = spawnSync(python, ["tests/resident_fixture.py", "certificates", "--root", root], { cwd: apiRoot, env: environment });
  if (cert.status !== 0) throw new Error("Local fixture certificate generation failed");
  const clientSecret = randomBytes(32).toString("hex");
  start(resolve("node_modules/.bin/tsx"), ["tests/resident/oidc.mts"], process.cwd(), {
    ...environment, TEST_CERT_ROOT: root, TEST_WEB_BASE: base, TEST_CLIENT_SECRET: clientSecret,
    TEST_SUBJECT_A: `resident-a-${prefix}`, TEST_SUBJECT_B: `resident-b-${prefix}` });
  start(python, ["tests/resident_fixture.py", "serve", "--port", String(apiPort)], apiRoot, environment);
  async function probe(url: string) {
    if (!release) { try { return (await fetch(url,{signal:AbortSignal.timeout(10000)})).ok; } catch { return false; } }
    return new Promise<boolean>((done) => {
      const req=httpsGet(url,{ca:readFileSync(join(root,"ca.pem")),timeout:10000},(response) => {
        response.resume(); done(response.statusCode === 200);
      });
      req.on("error",() => done(false)); req.on("timeout",() => {req.destroy(); done(false);});
    });
  }
  let apiAlive = false;
  for (let i=0;i<40;i++) {
    apiAlive = await probe(apiBase+"/health"); if(apiAlive) break;
    await new Promise((done) => setTimeout(done,250));
  }
  if (!apiAlive) throw new Error("Synthetic API startup failed");
  start(python,["tests/resident_fixture.py","work"],apiRoot,environment);
  if (release) {
    start(resolve("node_modules/.bin/tsx"),["tests/resident/tls-proxy.mts"],process.cwd(),{
      ...environment,TEST_CERT_ROOT:root,TEST_PROXY_PORT:String(webPort),TEST_PROXY_UPSTREAM:String(nextPort)});
  }
  const next = start(process.execPath, ["--import", resolve("tests/resident/transport.mjs"),
    ...(release ? [".next/standalone/server.js"] : ["node_modules/next/dist/bin/next","dev","--hostname","127.0.0.1","--port",String(webPort)])], process.cwd(), {
    ...environment, HOSTNAME:"127.0.0.1",PORT:String(nextPort), APP_MODE: "pilot", NODE_EXTRA_CA_CERTS: join(root, "ca.pem"), APP_BASE_URL: base,
    BACKEND_API_BASE_URL: apiBase, ...(release ? {} : {AUTH_ALLOW_LOCAL_HTTP:"1"}), AUTH0_DOMAIN: issuer,
    AUTH0_CLIENT_ID: "resident-fixture-client", AUTH0_CLIENT_SECRET: clientSecret,
    AUTH0_SECRET: randomBytes(32).toString("hex"), AUTH0_AUDIENCE: "urn:airshedos:pilot-api",
    SESSION_ENCRYPTION_KEY: randomBytes(32).toString("hex"), SESSION_DATABASE_URL: db.replace("postgresql+psycopg:", "postgresql:") });
  let ready = false;
  for (let attempt = 0; attempt < 40; attempt++) {
    try { ready = (await probe(apiBase+"/ready")) && (await probe(base+"/sign-in")); }
    catch { /* Local startup only. No requests to real providers. */ }
    if (ready || next.exitCode !== null) break;
    await new Promise((done) => setTimeout(done, 500));
  }
  if (!ready) { for (const child of children) process.stderr.write(diagnostics.get(child) ?? ""); throw new Error("Resident local fixture services failed to become ready"); }
  for (const config of (process.argv.includes("--all") ? ["playwright.resident.config.ts","playwright.authority.config.ts"] : [process.argv.includes("--authority") ? "playwright.authority.config.ts" : "playwright.resident.config.ts"])) {
  const runner = spawn(resolve("node_modules/.bin/playwright"), ["test", "--config", config, "--max-failures=1"], {
    stdio: "inherit", env: { ...environment, SEVA_TEST_PYTHON: python, RESIDENT_TEST_WEB_URL: base,
      TEST_SUBJECT_A: `resident-a-${prefix}`, TEST_SUBJECT_B: `resident-b-${prefix}` } });
  const result = await new Promise<number>((done) => runner.on("exit", (code) => done(code ?? 1)));
  if (result !== 0) for (const child of children) process.stderr.write(diagnostics.get(child) ?? "");
  if (result !== 0) { process.exitCode=result; break; }
  }
} finally {
  for (const child of children.reverse()) { try { if (child.pid) process.kill(-child.pid, "SIGTERM"); } catch { /* Already exited. */ } }
  await new Promise((done) => setTimeout(done, 500));
  await rm(root, { recursive: true, force: true });
}
