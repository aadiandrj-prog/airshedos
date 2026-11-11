import { createHash, randomBytes, randomUUID } from "node:crypto";
import { CompactEncrypt, compactDecrypt, decodeProtectedHeader } from "jose";
import { Pool, type PoolClient } from "pg";
import type { LogoutToken, SessionData, SessionDataStore } from "@auth0/nextjs-auth0/types";
import type { IdentitySettings } from "./settings";

const hash = (value: string) => createHash("sha256").update(value).digest("hex");
const hex64 = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);

export class PostgresSessionStore implements SessionDataStore {
  readonly pool: Pool;
  private permits = new Map<string, { subject: string; expires: number }>();
  private keys: Map<string, Uint8Array>;
  private keyId: string;
  constructor(readonly settings: IdentitySettings, pool?: Pool) {
    this.pool = pool ?? new Pool({ connectionString: settings.databaseUrl, max: 5,
      connectionTimeoutMillis: 5000, idleTimeoutMillis: 30000 });
    this.pool.on("error", () => { /* Requests fail closed; never log connection strings. */ });
    this.keys = new Map([settings.encryptionKey, settings.previousEncryptionKey].filter(
      (k): k is string => !!k).map((key) => [hash(key).slice(0, 16), Buffer.from(key, "hex")]));
    this.keyId = hash(settings.encryptionKey).slice(0, 16);
  }

  // Called ONLY by the SDK's successful, validated OIDC onCallback hook.
  allowNewLogin(session: SessionData) {
    for (const [key, permit] of this.permits) if (permit.expires < Date.now()) this.permits.delete(key);
    if (this.permits.size >= 256 || session.user.act) throw new Error("Sign-in unavailable");
    session.appBinding = randomBytes(32).toString("hex");
    session.csrf = randomBytes(32).toString("hex");
    this.permits.set(session.appBinding as string, { subject: session.user.sub,
      expires: Date.now() + 60000 });
  }

  private validate(session: SessionData) {
    if (!session.user.sub || session.user.sub.length > 255 || !hex64(session.appBinding)
        || !hex64(session.csrf)) throw new Error("Invalid session");
  }

  private async seal(session: SessionData) {
    this.validate(session);
    const data = await new CompactEncrypt(Buffer.from(JSON.stringify(session)))
      .setProtectedHeader({ alg: "dir", enc: "A256GCM", kid: this.keyId })
      .encrypt(this.keys.get(this.keyId)!);
    return Buffer.from(data);
  }

  async get(id: string): Promise<SessionData | null> {
    const row = (await this.pool.query(`SELECT s.subject, s.binding_hash, t.sealed_data
      FROM auth_sessions s JOIN auth_session_secrets t ON t.session_id=s.id
      JOIN users u ON u.id=s.user_id WHERE s.sdk_key_hash=$1 AND s.issuer=$2
      AND s.revoked_at IS NULL AND s.idle_expires_at>now() AND s.absolute_expires_at>now()
      AND u.active=true`, [hash(id), this.settings.issuer])).rows[0];
    if (!row) return null;
    try {
      const cipher = Buffer.from(row.sealed_data).toString();
      const kid = decodeProtectedHeader(cipher).kid;
      const key = typeof kid === "string" ? this.keys.get(kid) : undefined;
      if (!key) return null;
      const { plaintext } = await compactDecrypt(cipher, key, {
        keyManagementAlgorithms: ["dir"], contentEncryptionAlgorithms: ["A256GCM"] });
      const session = JSON.parse(Buffer.from(plaintext).toString()) as SessionData;
      this.validate(session);
      if (session.user.sub !== row.subject || hash(session.appBinding as string) !== row.binding_hash) return null;
      return session;
    } catch { return null; }
  }

  async set(id: string, session: SessionData): Promise<void> {
    this.validate(session);
    const binding = session.appBinding as string;
    const permit = this.permits.get(binding);
    this.permits.delete(binding); // Single-use login permit; retries need a new validated login.
    if (!permit || permit.expires < Date.now() || permit.subject !== session.user.sub)
      throw new Error("Validated new login required");
    const sealed = await this.seal(session);
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      await client.query(`INSERT INTO users(id,issuer,subject,active,created_at)
        VALUES($1,$2,$3,true,now()) ON CONFLICT(issuer,subject) DO NOTHING`,
      [randomUUID(), this.settings.issuer, session.user.sub]);
      const user = (await client.query(`SELECT id FROM users WHERE issuer=$1 AND subject=$2
        AND active=true FOR SHARE`, [this.settings.issuer, session.user.sub])).rows[0];
      if (!user) throw new Error("Account unavailable");
      const ceiling = session.internal.sessionExpiresAt ?? Math.floor(Date.now()/1000) + 28800;
      const row = (await client.query(`INSERT INTO auth_sessions
        (id,user_id,sdk_key_hash,binding_hash,issuer,subject,idp_sid_hash,
         created_at,idle_expires_at,absolute_expires_at,revoked_at)
        VALUES($1,$2,$3,$4,$5,$6,$7,now(),LEAST(now()+interval '30 minutes',to_timestamp($8)),
          LEAST(now()+interval '8 hours',to_timestamp($8)),NULL)
        ON CONFLICT DO NOTHING RETURNING id`, [randomUUID(), user.id, hash(id), hash(binding),
        this.settings.issuer, session.user.sub, session.internal.sid ? hash(session.internal.sid) : null,
        ceiling])).rows[0];
      if (!row) throw new Error("Session identifier already consumed");
      await client.query("INSERT INTO auth_session_secrets(session_id,sealed_data) VALUES($1,$2)",
        [row.id, sealed]);
      await client.query("COMMIT");
    } catch {
      await client.query("ROLLBACK");
      throw new Error("Sign-in storage unavailable");
    } finally { client.release(); }
  }

  async update(id: string, session: SessionData): Promise<boolean> {
    this.validate(session);
    const sealed = await this.seal(session);
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const row = (await client.query(`UPDATE auth_sessions s SET
        idle_expires_at=LEAST(s.absolute_expires_at,now()+interval '30 minutes')
        FROM users u WHERE s.sdk_key_hash=$1 AND s.binding_hash=$2 AND s.issuer=$3 AND s.subject=$4
        AND u.id=s.user_id AND u.active=true AND s.revoked_at IS NULL
        AND s.idle_expires_at>now() AND s.absolute_expires_at>now() RETURNING s.id`,
      [hash(id), hash(session.appBinding as string), this.settings.issuer, session.user.sub])).rows[0];
      if (!row) { await client.query("ROLLBACK"); return false; }
      const written = await client.query(`UPDATE auth_session_secrets SET sealed_data=$1
        WHERE session_id=$2`, [sealed, row.id]);
      if (written.rowCount !== 1) throw new Error("Session payload unavailable");
      await client.query("COMMIT");
      return true;
    } catch {
      await client.query("ROLLBACK");
      throw new Error("Session storage unavailable");
    } finally { client.release(); }
  }

  private async revoke(client: PoolClient, where: string, values: unknown[]) {
    await client.query(`WITH revoked AS (UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,now())
      WHERE ${where} RETURNING id) DELETE FROM auth_session_secrets
      WHERE session_id IN (SELECT id FROM revoked)`, values);
  }

  async delete(id: string): Promise<void> {
    const client = await this.pool.connect();
    try { await this.revoke(client, "sdk_key_hash=$1 AND issuer=$2", [hash(id),this.settings.issuer]); }
    finally { client.release(); }
  }

  async revokeBinding(binding: string): Promise<void> {
    if (!hex64(binding)) throw new Error("Invalid session");
    const client = await this.pool.connect();
    try { await this.revoke(client, "binding_hash=$1 AND issuer=$2", [hash(binding),this.settings.issuer]); }
    finally { client.release(); }
  }

  async deleteByLogoutToken(token: LogoutToken): Promise<void> {
    // The SDK validates signature/audience/events/nonce/issuer before this callback.
    if (token.iss !== this.settings.issuer || (!token.sub && !token.sid)) return;
    const client = await this.pool.connect();
    try { await this.revoke(client, `issuer=$1 AND ($2::text IS NULL OR subject=$2)
      AND ($3::text IS NULL OR idp_sid_hash=$3)`, [this.settings.issuer,
      token.sub ?? null, token.sid ? hash(token.sid) : null]); }
    finally { client.release(); }
  }
}
