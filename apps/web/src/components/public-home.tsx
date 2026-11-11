import Link from "next/link";
import { Brand } from "./workspace-nav";
import { AirOverview } from "./air-overview";
import "../app/explore/explore.css";

export function PublicHome() {
  return <div className="pilot-ui public-site">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="public-header"><Brand /><nav aria-label="Main navigation">
      <Link href="/explore">Explore local air</Link><a href="#how-it-works">How it works</a><Link href="/methodology">Methodology</Link>
      <Link href="/sign-in?returnTo=%2Fauthority%2Fcases">Authority sign in <span aria-hidden="true">↗</span></Link>
    </nav><Link className="public-sign-in" href="/resident/reports">My reports <span aria-hidden="true">↗</span></Link></header>
    <main id="main-content" className="public-main" tabIndex={-1}>
      <section className="public-hero">
        <div><p className="kicker"><span className="brand-dot" /> Environment. Evidence. Community.</p>
          <h1>Understand <span className="hero-gradient-word">local air.</span><br />Report what you notice.</h1>
          <div className="hero-actions"><Link className="pilot-button" href="/explore">Explore local air <span aria-hidden="true">↗</span></Link><Link className="pilot-button secondary" href="/resident/reports/new">Report a concern</Link></div>
        </div><div className="hero-aside"><p>Your surroundings tell a story. See the conditions, understand the sources, and make your observations count.</p><p className="muted">A resident account keeps your reports private. Approved reviewers work within their own review units.</p></div>
      </section>
      <section className="product-stage live-stage" aria-label="Explore environmental conditions">
        <div className="stage-heading"><span className="status-chip">Local air explorer</span><span className="example-label">On-demand data · no account required</span></div>
        <AirOverview embedded />
      </section>
      <div className="source-ribbon" aria-label="Environmental data providers"><p>Environmental context from</p><span>Google Maps Platform</span><span>NASA LANCE / FIRMS</span><Link href="/methodology">Understand the sources ↗</Link></div>
      <section id="how-it-works" className="public-section pathways">
        <div className="section-intro"><p className="kicker">One platform · two workspaces</p><h2>Two workspaces.<br />One shared purpose.</h2><p>Each side sees the information and actions appropriate to its role.</p></div>
        <div className="pathway-grid"><article><span className="pathway-number">01 / Residents</span><div className="pathway-glyph" aria-hidden="true">⌖</div><h3>Start with what you noticed.</h3><p>Share a description and reported location, add an optional photo, and return to your own reports for updates or requests for more information.</p><Link href="/resident/reports/new">Report a concern <span aria-hidden="true">↗</span></Link></article>
          <article><span className="pathway-number">02 / Approved reviewers</span><div className="pathway-glyph" aria-hidden="true">↗</div><h3>Keep the case in context.</h3><p>Review assigned-unit cases, inspect dated evidence, record follow-up and publish a separate, considered update to the resident.</p><Link href="/authority/cases">Open review workspace <span aria-hidden="true">↗</span></Link></article></div>
      </section>
      <section className="public-section capability-section"><div className="section-intro"><p className="kicker">More than a number</p><h2>Look closer.<br />Keep the bigger picture.</h2><p>Explore environmental context, then move into a private workflow when there is something to report.</p></div><div className="capability-grid"><article><span aria-hidden="true">⌖</span><h3>Conditions near you</h3><p>Use an approximate location or choose an area. See AQI, pollutant concentrations, wind and humidity with their source times.</p><Link href="/explore">Explore conditions ↗</Link></article><article><span aria-hidden="true">↗</span><h3>A clearer outlook</h3><p>Inspect hourly provider forecasts and separate window peaks. Missing hours and incomplete coverage stay visible.</p><Link href="/explore">Inspect the outlook ↗</Link></article><article><span aria-hidden="true">◎</span><h3>Nearby fire context</h3><p>See satellite detections relative to the query point, with acquisition times and an equivalent list. No detection is not an all-clear.</p><Link href="/explore">View fire context ↗</Link></article><article><span aria-hidden="true">≡</span><h3>A concern with continuity</h3><p>A saved report, private follow-up and deliberate reviewer updates. Provider failures do not erase a report.</p><Link href="/resident/reports">Open my reports ↗</Link></article></div></section>
      <section id="evidence" className="public-section evidence-story"><div><p className="kicker">Evidence with its limits</p><h2>Better context.<br />Room for uncertainty.</h2></div><div className="principle-list"><article><h3>A report comes first.</h3><p>Your concern is saved before analysis. Missing provider data does not invalidate a report.</p></article><article><h3>Interpretation supports review.</h3><p>AI and regional satellite context are advisory. Neither can prove a local source or a legal violation.</p></article><article><h3>Private by design.</h3><p>Individual reports are not a public feed. Retained photos are private, metadata-stripped derivatives with limited retention.</p></article></div></section>
      <section className="public-close"><p className="kicker">Begin with a concern</p><h2>What have you noticed?</h2><p>No photo required. Sign in to submit and follow your report.</p><Link className="pilot-button" href="/resident/reports/new">Report a concern <span aria-hidden="true">↗</span></Link></section>
    </main><footer className="pilot-footer"><Brand /><p>Pilot reporting & review. No emergency response or official government dispatch.</p><nav aria-label="Footer"><Link href="/methodology">Methodology</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link></nav></footer>
  </div>;
}
