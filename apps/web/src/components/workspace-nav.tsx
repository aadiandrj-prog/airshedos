"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Brand() { return <Link className="pilot-brand" href="/" aria-label="AirshedOS home"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>Airshed<span>OS</span></Link>; }
export function WorkspaceNav({ side, unitId, admin = false }: { side: "resident" | "authority"; unitId?: string; admin?: boolean }) {
  const path = usePathname();
  const workspaceLinks = side === "resident" ? [["/resident", "Introduction"],["/resident/reports/new", "Report a concern"],["/resident/reports", "My reports"]]
    : [[`/authority/cases?unit=${unitId}`, "Case queue"], ...(admin ? [[`/authority/unit?unit=${unitId}`, "Unit administration"]] : []), ["/resident/reports", "My resident reports"]];
  const links = [["/explore", "Explore local air"], ...workspaceLinks];
  return <nav className="workspace-nav" aria-label={side === "resident" ? "Resident navigation" : "Pilot review navigation"}>{links.map(([href,label]) => {
    const base = href.split("?")[0]; const current = base.endsWith("reports") ? path === base || path.startsWith(base+"/") && !path.endsWith("/new") : path === base || base.includes("cases") && path.startsWith(base+"/");
    return <Link key={href} href={href} aria-current={current ? "page" : undefined}>{label}<span aria-hidden="true">↗</span></Link>;
  })}</nav>;
}
