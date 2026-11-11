import { ResidentWorkspace } from "../../../../components/resident/workspace";
import { ReportDetail } from "../../../../components/resident/report-detail";
export const dynamic = "force-dynamic";
export default async function Report({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <ResidentWorkspace returnTo={`/resident/reports/${reportId}`} title="Your report">{() => <ReportDetail reportId={reportId} />}</ResidentWorkspace>;
}
