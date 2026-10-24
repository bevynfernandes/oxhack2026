import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import { date, QueryState, SyntheticNotice } from "../../components/Common";

/** Start with one company; open an exact saved publication without simulating research. */
export default function CompanyHomePage() {
  const location = useLocation();
  const legacySelection = new URLSearchParams(location.search).has("snapshot");
  const [search, setSearch] = useState("");
  const choices = useQuery({
    queryKey: ["company-publications"],
    queryFn: async () => unwrap(await api.GET("/api/v1/company-snapshots")),
  });
  const latest = choices.data?.items
    .slice()
    .sort(
      (a, b) =>
        b.assessment.recorded_at.localeCompare(a.assessment.recorded_at) ||
        a.assessment.publication_id.localeCompare(b.assessment.publication_id),
    )[0];
  const snapshot = latest?.assessment.publication_id ?? "";
  const companies = useQuery({
    queryKey: ["companies", snapshot],
    enabled: Boolean(snapshot),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/company-snapshots/{snapshot_id}/companies", {
          params: { path: { snapshot_id: snapshot } },
        }),
      ),
  });
  const rows = companies.data?.items.filter(({ company }) =>
    `${company.display_name} ${company.segment}`
      .toLocaleLowerCase()
      .includes(search.trim().toLocaleLowerCase()),
  );
  if (legacySelection)
    return <Navigate to={`/explore${location.search}`} replace />;
  return (
    <div className="company-home">
      <header className="home-heading">
        <p className="eyebrow">STARTUP RESEARCH</p>
        <h1>Look beyond the hype.</h1>
        <p>
          Choose a company. Explore the evidence behind its growth, business
          health and outlook.
        </p>
      </header>
      <section
        className="company-search-panel"
        aria-labelledby="choose-company"
      >
        <div className="section-heading">
          <h2 id="choose-company">Which company are you researching?</h2>
          <span className="eyebrow">Saved analyses</span>
        </div>
        <label className="home-search">
          Search companies
          <input
            type="search"
            placeholder="Search by company or sector…"
            value={search}
            maxLength={120}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <QueryState
          pending={choices.isPending}
          error={choices.error}
          retry={() => void choices.refetch()}
        />
        {latest && (
          <>
            <SyntheticNotice synthetic={latest.source.synthetic} />
            <QueryState
              pending={companies.isPending}
              error={companies.error}
              retry={() => void companies.refetch()}
            />
          </>
        )}
        {choices.data?.items.length === 0 && (
          <p role="status">No company assessments have been published yet.</p>
        )}
        {rows && (
          <>
            <p className="disclaimer" role="status">
              {rows.length} {rows.length === 1 ? "company" : "companies"}{" "}
              available · Evidence as of {date(latest!.source.as_of)}
            </p>
            {rows.length === 0 && (
              <p>No companies match your search. Try another name or sector.</p>
            )}
            <ul className="company-results">
              {rows.map(({ company }) => (
                <li key={company.company_id}>
                  <div className="company-monogram" aria-hidden="true">
                    {company.display_name.slice(0, 1)}
                  </div>
                  <div>
                    <h3>{company.display_name}</h3>
                    <p>{company.segment}</p>
                  </div>
                  <Link
                    className="company-open"
                    aria-label={`View analysis for ${company.display_name}`}
                    to={`/companies/${encodeURIComponent(snapshot)}/${encodeURIComponent(company.company_id)}`}
                  >
                    View analysis <span aria-hidden="true">↗</span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="home-secondary">
          <span>Looking for more context?</span>
          <Link to="/explore">Browse publications & compare companies</Link>
        </div>
      </section>
      <div className="research-guide" aria-label="What the analysis covers">
        <div>
          <span>01</span>
          <h2>Understand the outlook</h2>
          <p>
            Read the published assessment and what the evidence can support.
          </p>
        </div>
        <div>
          <span>02</span>
          <h2>Examine the fundamentals</h2>
          <p>Explore traction, commercial health, execution and financing.</p>
        </div>
        <div>
          <span>03</span>
          <h2>Check the evidence</h2>
          <p>Follow sources and see what is missing, stale or uncertain.</p>
        </div>
      </div>
      <p className="home-footnote">
        Saved evidence assessments. Success probabilities are not yet validated;
        unavailable data stays visible.
      </p>
    </div>
  );
}
