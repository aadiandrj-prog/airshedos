import { ResidentWorkspace } from "../../../components/resident/workspace";
import { ReportList } from "../../../components/resident/report-list";
export const dynamic = "force-dynamic";
export default function Reports() { return <ResidentWorkspace returnTo="/resident/reports" title="My reports">{() => <ReportList />}</ResidentWorkspace>; }
