"use client";
import { useCallback, useEffect, useState } from "react";
import { authorityRequest } from "../../lib/authority-client";

type Member = { id: string; role: string; state: string };
type Proposal = { id: string; state: string; expires_at: string };
export function UnitAdministration({ unitId }: { unitId: string }) {
  const [members, setMembers] = useState<Member[]>([]); const [proposals, setProposals] = useState<Proposal[]>([]);
  const [subject, setSubject] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const [m,p] = await Promise.all([authorityRequest(unitId,"memberships"),authorityRequest(unitId,"membership-proposals")]); return [await m.json(),await p.json()] as [Member[],Proposal[]]; }, [unitId]);
  const refresh = () => void load().then(([m,p]) => { setMembers(m); setProposals(p); }).catch((failure) => setMessage(failure.message));
  useEffect(() => { let active = true; void load().then(([m,p]) => { if (active) { setMembers(m); setProposals(p); } }).catch((failure) => { if (active) setMessage(failure.message); }); return () => { active = false; }; }, [load]);
  async function act(path: string, body: object) { setBusy(true); setMessage(""); try { await authorityRequest(unitId,path,{method:"POST",body:JSON.stringify(body)});
    setMessage("Recorded for this unit. Membership proposals still require separate operator approval."); refresh(); } catch (failure) { setMessage((failure as Error).message); } finally { setBusy(false); } }
  return <section><h2>Membership administration</h2><p>Proposals concern an existing verified identity. They grant no access and send no invitation message. Only the operator can approve access or create a unit/admin.</p>
    <form onSubmit={(event) => { event.preventDefault(); void act("membership-proposals",{ target_subject:subject, role:"REVIEWER" }); }}>
      <label>Verified identity subject<input required maxLength={255} value={subject} onChange={(e) => setSubject(e.target.value)} disabled={busy} autoComplete="off" /></label>
      <button disabled={busy} type="submit">Propose reviewer membership</button></form>
    <p role="status" aria-label="Membership administration status">{message}</p><button type="button" onClick={refresh} disabled={busy}>Refresh membership state</button>
    <h3>Unit memberships</h3><ul>{members.map((m) => <li key={m.id}>{m.id.slice(0,8)} · {m.role} · {m.state}
      {m.role === "REVIEWER" && m.state === "ACTIVE" && <button type="button" disabled={busy} onClick={() => void act(`memberships/${m.id}/suspend`,{})}>Suspend reviewer {m.id.slice(0,8)}</button>}</li>)}</ul>
    <h3>Recent proposals</h3><ul>{proposals.map((p) => <li key={p.id}>{p.id.slice(0,8)} · {p.state}</li>)}</ul>
  </section>;
}
