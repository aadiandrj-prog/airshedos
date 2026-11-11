import "server-only";
import type { Auth0Client } from "@auth0/nextjs-auth0/server";
import { identitySettings, missingIdentityVariables } from "./settings";
import { PostgresSessionStore } from "./session-store";
import { managedClient } from "./auth-client";

let instance: { client: Auth0Client; store: PostgresSessionStore;
  settings: NonNullable<ReturnType<typeof identitySettings>> } | undefined;
let lastConfigurationIssue: string | undefined;

function configurationIssue(code: string, fields: readonly string[] = []) {
  const diagnostic = JSON.stringify({ code, fields });
  if (diagnostic !== lastConfigurationIssue) {
    // Deliberately omit exception messages, settings, URLs and credential values.
    console.error("AirshedOS identity configuration:", diagnostic);
    lastConfigurationIssue = diagnostic;
  }
}

export function identityRuntime() {
  if (instance) return instance;
  const missing = missingIdentityVariables();
  if (missing.length) {
    configurationIssue("IDENTITY_ENV_MISSING", missing);
    return null;
  }
  let settings: ReturnType<typeof identitySettings>;
  try { settings = identitySettings(); }
  catch {
    configurationIssue("IDENTITY_ENV_INVALID");
    throw new Error("Identity configuration invalid");
  }
  if (!settings) return null;
  try {
    const store = new PostgresSessionStore(settings);
    const client = managedClient(settings, store);
    instance = { client, store, settings };
  } catch {
    configurationIssue("IDENTITY_INITIALISATION_FAILED");
    throw new Error("Identity initialisation unavailable");
  }
  lastConfigurationIssue = undefined;
  return instance;
}
