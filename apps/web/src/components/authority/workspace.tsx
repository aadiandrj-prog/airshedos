import { WorkspaceNav } from "../workspace-nav";
import { redirect } from "next/navigation";
import { residentSession } from "../../server/resident-session";
import { Shell } from "../../server/route-shell";
import { SessionActions } from "../session-actions";
import type { components } from "../../lib/api-schema";
import "../resident/resident.css";

type Unit = components["schemas"]["UnitRead"];
export async function AuthorityWorkspace({ title, unitId, returnTo, children }: {
  title: string; unitId?: string; returnTo: string;
  children: (unit: Unit, ownId: string) => React.ReactNode;
}) {
  const context = await residentSession();
  if (context.state === "unconfigured") return <Shell title="Sign-in unavailable"><p>Managed sign-in is not configured in this deployment.</p></Shell>;
  if (context.state === "unavailable") return <Shell title="Workspace unavailable"><p>The service could not verify access. Please retry.</p></Shell>;
  if (context.state === "anonymous") redirect(`/sign-in?returnTo=${encodeURIComponent(returnTo)}`);
  if (context.state !== "ready") return null;
  const units = context.me.units;
  const selected = unitId ? units.find((unit) => unit.id === unitId) : units[0];
  return <Shell title={title} side="authority"><div className="authority-layout">
    <aside className="authority-rail">
      <p className="pilot-notice">Pilot review tools. No official government partnership or dispatch service.</p>
      {selected && <><form className="unit-switch" action="/authority/cases" method="get"><label>Review unit<select aria-label="Review unit" name="unit" defaultValue={selected.id}>
        {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
      </select></label><button type="submit">Open selected unit</button></form>
      <p className="unit-role">Selected unit: <strong>{selected.name}</strong><br />{selected.role === "UNIT_ADMIN" ? "Unit administrator" : "Reviewer"}</p>
      <WorkspaceNav side="authority" unitId={selected.id} admin={selected.role === "UNIT_ADMIN"} /></>}
      <SessionActions />
    </aside>
    <div className="resident-workspace authority-content">{selected ? children(selected, context.me.id)
      : <p role="status">{units.length ? "This unit is unavailable to your account." : "No approved review-unit membership. An invitation request does not grant authority access."}</p>}
    </div>
  </div></Shell>;
}
