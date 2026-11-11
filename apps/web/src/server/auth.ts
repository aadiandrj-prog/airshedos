import "server-only";
import type { Auth0Client } from "@auth0/nextjs-auth0/server";
import { identitySettings } from "./settings";
import { PostgresSessionStore } from "./session-store";
import { managedClient } from "./auth-client";

let instance: { client: Auth0Client; store: PostgresSessionStore;
  settings: NonNullable<ReturnType<typeof identitySettings>> } | undefined;

export function identityRuntime() {
  if (instance) return instance;
  const settings = identitySettings();
  if (!settings) return null;
  const store = new PostgresSessionStore(settings);
  const client = managedClient(settings, store);
  instance = { client, store, settings };
  return instance;
}
