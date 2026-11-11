import { AuthorityWorkspace } from "../../../components/authority/workspace";
import { UnitAdministration } from "../../../components/authority/unit-admin";
export const dynamic = "force-dynamic";
export default async function Unit({ searchParams }: { searchParams: Promise<{ unit?: string }> }) {
  const { unit } = await searchParams;
  return <AuthorityWorkspace title="Unit administration" unitId={unit} returnTo="/authority/unit">{(selected) => selected.role === "UNIT_ADMIN"
    ? <UnitAdministration unitId={selected.id} /> : <p>No unit-administrator permission.</p>}</AuthorityWorkspace>;
}
