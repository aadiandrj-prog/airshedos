import Link from "next/link";
import { Brand } from "./workspace-nav";

export function PublicHome() {
  return <div className="pilot-ui public-site">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="public-header"><Brand /><nav aria-label="Main navigation">
      <a href="#how-it-works">How it works</a><a href="#evidence">Evidence & limits</a>
      <Link href="/sign-in?returnTo=%2Fauthority%2Fcases">Authority sign in <span aria-hidden="true">↗</span></Link>
    </nav><Link className="public-sign-in" href="/resident/reports">My reports <span aria-hidden="true">↗</span></Link></header>
    <main id="main-content" className="public-main" tabIndex={-1}>
      <section className="public-hero">
        <div><p className="kicker"><span className="brand-dot" /> A shared place for local concerns</p>
          <h1>A clearer way to report local pollution.</h1>
          <div className="hero-actions"><Link className="pilot-button" href="/resident/reports/new">Report a concern <span aria-hidden="true">↗</span></Link><Link className="pilot-button secondary" href="/resident/reports">My reports</Link></div>
        </div><div className="hero-aside"><p>Describe what you noticed. Understand the available evidence. Follow the review in one place.</p><p className="muted">A resident account keeps your reports private. Approved reviewers work within their own review units.</p></div>
      </section>
      <section className="product-stage" aria-label="Synthetic example of a report timeline">
        <div className="stage-heading"><span className="status-chip">From concern to recorded review</span><span className="example-label">Illustrative journey · synthetic example</span></div>
        <div className="example-report"><div className="example-report-heading"><span className="preview-mark" aria-hidden="true">↗</span><div><p className="kicker">Resident report</p><h2>Smoke near a neighbourhood entrance</h2></div><span className="status-chip">Example only</span></div>
          <ol className="preview-timeline"><li><span aria-hidden="true">01</span><div><strong>Concern saved</strong><p>A receipt confirms the report is stored. A photo is optional.</p></div></li><li><span aria-hidden="true">02</span><div><strong>Review & follow-up</strong><p>An approved reviewer considers the report and available evidence.</p></div></li><li><span aria-hidden="true">03</span><div><strong>An update, in your account</strong><p>Only deliberately published messages reach your timeline.</p></div></li></ol>
          <p className="preview-footnote">This example contains no live case or air-quality reading. Review does not establish a legal violation.</p>
        </div>
        <p className="stage-caption">Private reporting. Advisory evidence. Human review.</p>
      </section>
      <section id="how-it-works" className="public-section pathways">
        <div className="section-intro"><p className="kicker">One platform · two workspaces</p><h2>A simple way to report.<br />A considered way to review.</h2><p>Each side sees the information and actions appropriate to its role.</p></div>
        <div className="pathway-grid"><article><span className="pathway-number">01 / Residents</span><h3>Start with what you noticed.</h3><p>Share a description and reported location, add an optional photo, and return to your own reports for updates or requests for more information.</p><Link href="/resident/reports/new">Report a concern <span aria-hidden="true">↗</span></Link></article>
          <article><span className="pathway-number">02 / Approved reviewers</span><h3>Keep the case in context.</h3><p>Review assigned-unit cases, inspect dated evidence, record follow-up and publish a separate, considered update to the resident.</p><Link href="/authority/cases">Open review workspace <span aria-hidden="true">↗</span></Link></article></div>
      </section>
      <section id="evidence" className="public-section evidence-story"><div><p className="kicker">Evidence with its limits</p><h2>Better context.<br />Room for uncertainty.</h2></div><div className="principle-list"><article><h3>A report comes first.</h3><p>Your concern is saved before analysis. Missing provider data does not invalidate a report.</p></article><article><h3>Interpretation supports review.</h3><p>AI and regional satellite context are advisory. Neither can prove a local source or a legal violation.</p></article><article><h3>Private by design.</h3><p>Individual reports are not a public feed. Retained photos are private, metadata-stripped derivatives with limited retention.</p></article></div></section>
      <section className="public-close"><p className="kicker">Begin with a concern</p><h2>What have you noticed?</h2><p>No photo required. Sign in to submit and follow your report.</p><Link className="pilot-button" href="/resident/reports/new">Report a concern <span aria-hidden="true">↗</span></Link></section>
    </main><footer className="pilot-footer"><Brand /><p>Pilot reporting & review. No emergency response or official government dispatch.</p><Link href="/authority">Authority workspace</Link></footer>
  </div>;
}
