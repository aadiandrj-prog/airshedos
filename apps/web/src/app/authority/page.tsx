import Link from "next/link";
import { AuthorityWorkspace } from "../../components/authority/workspace";
export const dynamic = "force-dynamic";
export default function Authority() { return <AuthorityWorkspace title="Pilot review workspace" returnTo="/authority">{(unit) => <>
  <p>Review assigned-unit reports, record findings and deliberately publish separate resident updates. Pending analysis does not prevent manual review.</p>
  <Link href={`/authority/cases?unit=${unit.id}`}>Open case queue</Link>
</>}</AuthorityWorkspace>; }
