import { AuthorityWorkspace } from "../../../../components/authority/workspace";
import { CaseDetail } from "../../../../components/authority/case-detail";
export const dynamic = "force-dynamic";
export default async function Case({ params, searchParams }: { params: Promise<{ caseId: string }>; searchParams: Promise<{ unit?: string }> }) {
  const [{ caseId }, { unit }] = await Promise.all([params, searchParams]);
  return <AuthorityWorkspace title="Pilot case review" unitId={unit} returnTo={`/authority/cases/${caseId}`}>
    {(selected) => <CaseDetail key={`${selected.id}:${caseId}`} unitId={selected.id} caseId={caseId} admin={selected.role === "UNIT_ADMIN"} />}
  </AuthorityWorkspace>;
}
