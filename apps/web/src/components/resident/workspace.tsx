import { redirect } from "next/navigation";
import { WorkspaceNav } from "../workspace-nav";
import { residentSession } from "../../server/resident-session";
import { Shell } from "../../server/route-shell";
import { SessionActions } from "../session-actions";
import "./resident.css";

export async function ResidentWorkspace({ returnTo, title, children }: {
  returnTo: string; title: string; children: (userId: string) => React.ReactNode;
}) {
  const context = await residentSession();
  if (context.state === "unconfigured") return <Shell title="Sign-in unavailable"><p>Managed sign-in is not configured in this deployment.</p></Shell>;
  if (context.state === "unavailable") return <Shell title="Workspace unavailable"><p>The service could not verify access. Please retry.</p></Shell>;
  if (context.state === "anonymous") redirect(`/sign-in?returnTo=${encodeURIComponent(returnTo)}`);
  if (context.state !== "ready") return null;
  return <Shell title={title} side="resident"><div className="resident-workspace">
    <WorkspaceNav side="resident" />
    {children(context.me.id)}<SessionActions />
  </div></Shell>;
}
