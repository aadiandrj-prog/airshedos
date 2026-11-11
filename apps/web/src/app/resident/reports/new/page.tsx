import { ResidentWorkspace } from "../../../../components/resident/workspace";
import { ReportForm } from "../../../../components/resident/report-form";
export const dynamic = "force-dynamic";
export default function NewReport() { return <ResidentWorkspace returnTo="/resident/reports/new" title="Report a concern">{(id) => <ReportForm userId={id} />}</ResidentWorkspace>; }
