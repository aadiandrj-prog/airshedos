import { redirect } from "next/navigation";
import Link from "next/link";
import { SessionActions } from "../components/session-actions";
import { Brand } from "../components/workspace-nav";
import { identityRuntime } from "./auth";
import type { components } from "../lib/api-schema";

export async function RouteShell({ side }: { side: "resident" | "authority" }) {
  let me: components["schemas"]["MeRead"] | undefined;
  let failure: "unconfigured" | "unavailable" | undefined;
  try {
    const identity = identityRuntime();
    if (!identity) failure = "unconfigured";
    const session = identity ? await identity.client.getSession() : null;
    if (identity && session) {
      const response = await fetch(new URL("/api/v2/me", identity.settings.backend), { cache: "no-store",
        signal: AbortSignal.timeout(10000), headers: { Authorization: `Bearer ${session.tokenSet.accessToken}`,
          "X-AirshedOS-Session": String(session.appBinding) } });
      if (response.ok) me = await response.json();
      else if (response.status !== 401) failure = "unavailable";
    }
  } catch {
    failure = "unavailable";
  }
  if (failure === "unconfigured") return <Shell title="Sign-in unavailable"><p>Managed sign-in is not configured in this deployment.</p></Shell>;
  if (failure) return <Shell title="Workspace unavailable"><p>The service could not verify access. Please retry.</p></Shell>;
  if (!me) redirect(`/sign-in?returnTo=/${side}`);
  return <Shell title={side === "resident" ? "Resident workspace" : "Authority workspace"}>
    {side === "resident" ? <p>You are signed in. Report submission and tracking will be added in the next phase.</p>
      : me.units.length ? <><p>Your approved review units:</p><ul>{me.units.map((unit) => <li key={unit.id}>{unit.name} — {unit.role === "UNIT_ADMIN" ? "Unit administrator" : "Reviewer"}</li>)}</ul><p>Case tools will be added in a later phase.</p></>
        : <p>No approved review-unit membership. An invitation request does not grant authority access.</p>}
    <nav aria-label="Workspaces"><Link href="/resident">Resident workspace</Link>{" · "}<Link href="/authority">Authority workspace</Link></nav>
    <SessionActions />
  </Shell>;
}

export function Shell({ title, children, side = "session" }: { title: string; children: React.ReactNode; side?: "resident" | "authority" | "session" }) {
  return <div className="pilot-ui">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="pilot-header"><Brand /><span className="workspace-type">{side === "authority" ? "Pilot review workspace" : side === "resident" ? "Resident workspace" : "Private reporting & review"}</span>
      <nav aria-label="Workspaces"><Link href="/resident/reports">Resident workspace</Link><Link href="/authority/cases">Authority workspace</Link></nav>
    </header>
    <main id="main-content" tabIndex={-1} className="pilot-main" data-side={side}>
      <div className="pilot-title"><p className="kicker">{side === "authority" ? "Assigned-unit casework" : side === "resident" ? "Your concerns, in one place" : "AirshedOS account"}</p><h1>{title}</h1></div>{children}
    </main><footer className="pilot-footer"><Brand /><p>Pilot reporting & review. No emergency response or official government dispatch.</p></footer>
  </div>;
}
