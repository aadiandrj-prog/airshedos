import Link from "next/link";
import { AirOverview } from "../../components/air-overview";
import { Brand } from "../../components/workspace-nav";
import "./explore.css";
export const metadata = { title: "Explore local air | AirshedOS", description: "Air quality, weather, NASA FIRMS detections and separate forecast summaries near your approximate location or supported Delhi NCR areas." };
export default function Explore() {
  return <div className="pilot-ui public-site"><a className="skip-link" href="#main-content">Skip to content</a><header className="public-header"><Brand /><nav aria-label="Main navigation"><Link href="/explore" aria-current="page">Explore local air</Link><Link href="/methodology">Methodology</Link><Link href="/resident/reports/new">Report a concern</Link><Link href="/resident/reports">My reports</Link></nav></header><main id="main-content" className="air-main" tabIndex={-1}><AirOverview /></main></div>;
}
