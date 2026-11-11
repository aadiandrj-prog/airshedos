import { AuthorityWorkspace } from "../../../components/authority/workspace";
import { CaseQueue } from "../../../components/authority/queue";
export const dynamic = "force-dynamic";
export default async function Cases({ searchParams }: { searchParams: Promise<{ unit?: string }> }) {
  const { unit } = await searchParams;
  return <AuthorityWorkspace title="Case queue" unitId={unit} returnTo="/authority/cases">{(selected) => <CaseQueue key={selected.id} unitId={selected.id} />}</AuthorityWorkspace>;
}
