import { MotionLink as Link } from "../../motion";

/** Explain the product's current, user-visible capabilities without making forecast claims. */
export default function AboutPage() {
  return (
    <article className="about-page">
      <header className="page-heading">
        <p className="eyebrow">ABOUT SIGNALSHIFT</p>
        <h1>Startup research with its evidence attached</h1>
        <p>
          SignalShift researches Software and SaaS companies using dated public
          evidence. It shows what was found, where it came from and what remains
          unknown. Validated startup-growth and survival predictions are not yet
          available.
        </p>
      </header>

      <section aria-labelledby="functions-heading">
        <h2 id="functions-heading">What you can do</h2>
        <ul>
          <li>
            <strong>Research a company:</strong> search by company name or exact
            website domain, inspect the discovered identity and confirm it
            before collection starts.
          </li>
          <li>
            <strong>Watch research progress:</strong> see each configured source
            finish, fail, return partial evidence or remain unavailable.
          </li>
          <li>
            <strong>Read a research report:</strong> inspect measurements,
            company claims, events, source links, collection dates, evidence
            gaps and limitations.
          </li>
          <li>
            <strong>Inspect five evidence areas:</strong> adoption and
            retention, attention and sentiment, financial health, industry and
            competition, and team and execution.
          </li>
          <li>
            <strong>Refresh research:</strong> start a new collection without
            changing an older immutable report.
          </li>
          <li>
            <strong>Export a report:</strong> download the displayed report as
            JSON.
          </li>
          <li>
            <strong>Open a saved dossier:</strong> read evidence previously
            published for a company at a fixed historical date.
          </li>
          <li>
            <strong>Keep a local research library:</strong> revisit reports,
            saved dossiers and research jobs opened in this browser.
          </li>
          <li>
            <strong>Save decision context:</strong> add browser-local notes,
            watchlist status and a manual review date to a dossier.
          </li>
          <li>
            <strong>Save research filters:</strong> store a text or watchlist
            filter in this browser and restore it later.
          </li>
        </ul>
      </section>

      <section aria-labelledby="sources-heading">
        <h2 id="sources-heading">Sources the research worker can check</h2>
        <p>
          Website pages, GitHub, npm, public hiring pages, Hacker News, news
          articles, SEC records and Companies House records. A source can be
          unavailable, incomplete or inapplicable to a company; the report keeps
          those limits visible.
        </p>
      </section>

      <section aria-labelledby="comparison-heading">
        <h2 id="comparison-heading">What the Research library does</h2>
        <p>
          It remembers visited reports, saved dossiers and research jobs in this
          browser. You can search them, show only watchlisted records, save
          those filters and remove local links. This history is not attached to
          an account and does not sync between devices.
        </p>
        <p>
          Select two or three completed reports or saved dossiers to compare
          evidence, dates, definitions, coverage and missing information. The
          published-company section also compares two or three companies from
          the same saved assessment snapshot. Neither comparison ranks a winner
          or treats different measurements as equivalent.
        </p>
        <Link to="/explore">Open the Research library</Link>
      </section>

      <section aria-labelledby="results-heading">
        <h2 id="results-heading">What the results currently mean</h2>
        <p>
          The report is an evidence assessment, not a success score. Package
          downloads can describe SDK demand, public mentions can describe
          attention and filings can provide supported public-company facts.
          These signals do not by themselves prove customers, retention,
          profitability, growth or survival.
        </p>
        <p>
          Growth, Survival and Overall remain unavailable when the required
          historical labels, compatible measurements and validated models are
          absent. Missing evidence is not treated as failure or a zero score.
        </p>
      </section>

      <section aria-labelledby="secondary-heading">
        <h2 id="secondary-heading">Secondary tools</h2>
        <ul>
          <li>
            <Link to="/traction">Traction research</Link> compares published
            package-download forecasts. It is separate from company-success
            research.
          </li>
          <li>
            <Link to="/data-health">Data health</Link> shows connector
            readiness, freshness and missing-data diagnostics.
          </li>
        </ul>
      </section>
    </article>
  );
}
