export type IdentitySettings = {
  appBaseUrl: string; backend: string; issuer: string; domain: string;
  clientId: string; clientSecret: string; cookieSecret: string;
  encryptionKey: string; previousEncryptionKey?: string; databaseUrl: string;
  secure: boolean;
};

export const requiredIdentityVariables = ["APP_BASE_URL", "BACKEND_API_BASE_URL", "AUTH0_DOMAIN",
  "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "AUTH0_SECRET", "SESSION_ENCRYPTION_KEY",
  "SESSION_DATABASE_URL", "AUTH0_AUDIENCE"] as const;

export function missingIdentityVariables(env: Readonly<Record<string, string | undefined>> = process.env) {
  return requiredIdentityVariables.filter((key) => !env[key]);
}

export function identitySettings(env: Readonly<Record<string, string | undefined>> = process.env): IdentitySettings | null {
  if (missingIdentityVariables(env).length) return null;
  const app = new URL(env.APP_BASE_URL!);
  const backend = new URL(env.BACKEND_API_BASE_URL!);
  const domain = new URL(env.AUTH0_DOMAIN!.startsWith("https://")
    ? env.AUTH0_DOMAIN! : `https://${env.AUTH0_DOMAIN}`);
  const local = env.AUTH_ALLOW_LOCAL_HTTP === "1" && env.NODE_ENV !== "production";
  const validOrigin = (url: URL, allowLocal: boolean) => !url.username && !url.password
    && !url.search && !url.hash && url.pathname === "/"
    && (url.protocol === "https:" || (allowLocal && url.protocol === "http:"
      && ["127.0.0.1", "localhost"].includes(url.hostname)));
  if (!validOrigin(app, local) || !validOrigin(backend, local) || !validOrigin(domain, false) || domain.port
      || !/^[a-fA-F0-9]{64}$/.test(env.AUTH0_SECRET!)
      || !/^[a-fA-F0-9]{64}$/.test(env.SESSION_ENCRYPTION_KEY!)
      || env.AUTH0_SECRET === env.SESSION_ENCRYPTION_KEY
      || (env.SESSION_ENCRYPTION_PREVIOUS_KEY
        && !/^[a-fA-F0-9]{64}$/.test(env.SESSION_ENCRYPTION_PREVIOUS_KEY))
      || env.AUTH0_AUDIENCE !== "urn:airshedos:pilot-api") throw new Error("Invalid identity settings");
  const db = new URL(env.SESSION_DATABASE_URL!);
  if (!["postgresql:", "postgres:"].includes(db.protocol)
      || (!["127.0.0.1", "localhost", "[::1]"].includes(db.hostname)
        && db.searchParams.get("sslmode") !== "verify-full")) throw new Error("Invalid session database");
  return { appBaseUrl: app.origin, backend: backend.origin, issuer: domain.origin + "/",
    domain: domain.hostname, clientId: env.AUTH0_CLIENT_ID!, clientSecret: env.AUTH0_CLIENT_SECRET!,
    cookieSecret: env.AUTH0_SECRET!, encryptionKey: env.SESSION_ENCRYPTION_KEY!,
    previousEncryptionKey: env.SESSION_ENCRYPTION_PREVIOUS_KEY,
    databaseUrl: env.SESSION_DATABASE_URL!, secure: app.protocol === "https:" };
}

// Explicit routes only, never arbitrary prefixes, schemes, encoded paths or origins.
export function safeReturnTo(value: string | null | undefined): string {
  if (["/resident", "/authority", "/resident/reports", "/resident/reports/new"].includes(value ?? "")) return value!;
  if (value && /^\/resident\/reports\/[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$/.test(value)) return value;
  const uuid = "[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}";
  if (value && new RegExp(`^/authority/(?:unit|cases(?:/${uuid})?)(?:\\?unit=${uuid})?$`).test(value)) return value;
  return "/resident";
}
