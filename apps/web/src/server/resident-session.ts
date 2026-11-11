import "server-only";
import { identityRuntime } from "./auth";
import type { components } from "../lib/api-schema";

export async function residentSession(): Promise<
  { state: "ready"; me: components["schemas"]["MeRead"] } | { state: "unconfigured" | "unavailable" | "anonymous" }> {
  try {
    const runtime = identityRuntime();
    if (!runtime) return { state: "unconfigured" };
    const session = await runtime.client.getSession();
    if (!session) return { state: "anonymous" };
    const response = await fetch(new URL("/api/v2/me", runtime.settings.backend), {
      cache: "no-store", signal: AbortSignal.timeout(10000), headers: {
        Authorization: `Bearer ${session.tokenSet.accessToken}`, "X-AirshedOS-Session": String(session.appBinding) } });
    if (response.status === 401) return { state: "anonymous" };
    if (!response.ok) return { state: "unavailable" };
    return { state: "ready", me: await response.json() };
  } catch { return { state: "unavailable" }; }
}
