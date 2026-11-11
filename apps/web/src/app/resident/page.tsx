import Link from "next/link";
import { ResidentWorkspace } from "../../components/resident/workspace";
export const dynamic = "force-dynamic";
export default function Resident() { return <ResidentWorkspace returnTo="/resident" title="Resident workspace">{() => <div className="resident-stack">
  <section className="resident-intro"><p className="kicker">Start with what you noticed</p><h2>Report a concern. Stay informed.</h2>
    <p>Share a description and reported location. A photo and device location are optional; approximate manually entered coordinates are welcome.</p>
    <div className="intro-actions"><Link className="pilot-button" href="/resident/reports/new">Report a concern</Link><Link className="pilot-button secondary" href="/resident/reports">View my reports</Link></div>
  </section><section className="resident-intro"><h2>What happens next?</h2><p>Your receipt confirms that the report was saved. Analysis can remain pending. An approved reviewer can ask for more information or publish an update to your timeline.</p><p className="pilot-notice">This pilot does not establish a violation or provide emergency response or official government dispatch.</p></section>
  <section className="resident-intro"><h2>Your information stays private</h2><p>Report content is retained for up to 90 days; private cleaned photos for up to 30 days, subject to earlier expiry or deletion. No original uploads are stored.</p><p className="resident-help">Hosting and notices must be approved before real collection.</p></section>
</div>}</ResidentWorkspace>; }
