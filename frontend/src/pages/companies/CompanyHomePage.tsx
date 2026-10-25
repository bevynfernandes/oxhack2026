import {
  MotionAmbient,
  MotionButton,
  MotionInput,
  MotionLink as Link,
  MotionSurface,
} from "../../motion";
import armillaryUrl from "../../theme/assets/armillary.svg";
import laurelsUrl from "../../theme/assets/laurels.svg";
import rocketUrl from "../../theme/assets/rocket-line-drawing.svg";
import { useMutation, useQuery, useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { companyDomain, matchesCompanySearch } from "./identity";
import { api, unwrap } from "../../api/client";
import { date, QueryState } from "../../components/Common";
import CompanySpinner from "../../components/CompanySpinner";
import { previewCompany, searchCompanies } from "../research/client";

const PAGE_SIZE = 2;

/** Start with one company; open an exact saved publication without simulating research. */
export default function CompanyHomePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const legacySelection = new URLSearchParams(location.search).has("snapshot");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const preview = useMutation({
    retry: false,
    mutationFn: previewCompany,
    onSuccess: (identity) =>
      navigate("/research/identities/" + identity.identity_id),
  });
  const lookup = useMutation({
    retry: false,
    mutationFn: searchCompanies,
    onSuccess: (result) => {
      if (
        result.candidates.length === 1 &&
        result.candidates[0].source === "input"
      )
        preview.mutate(result.candidates[0].website);
    },
  });
  const searching = lookup.isPending || preview.isPending;
  const choices = useQuery({
    queryKey: ["company-publications"],
    queryFn: async () => unwrap(await api.GET("/api/v1/company-snapshots")),
    retry: false,
  });
  const publications = choices.data?.items ?? [];
  const companyQueries = useQueries({
    queries: publications.map((publication) => {
      const snapshot = publication.assessment.publication_id;
      return {
        queryKey: ["companies", snapshot],
        queryFn: async () =>
          unwrap(
            await api.GET("/api/v1/company-snapshots/{snapshot_id}/companies", {
              params: { path: { snapshot_id: snapshot } },
            }),
          ),
      };
    }),
  });
  const rows =
    publications.length > 0
      ? companyQueries
          .flatMap((query, index) =>
            (query.data?.items ?? []).map((row) => ({
              ...row,
              publication: publications[index],
              snapshot: publications[index].assessment.publication_id,
            })),
          )
          .filter(({ company }) => matchesCompanySearch(company, search))
      : undefined;
  if (legacySelection)
    return <Navigate to={`/explore${location.search}`} replace />;
  return (
    <div className="terminal-home">
      <div className="home-pattern-region home-pattern-region-left">
        <MotionAmbient
          mode="drift"
          className="home-pattern-layer home-pattern-primary"
        >
          <img src={laurelsUrl} alt="" />
        </MotionAmbient>
      </div>
      <div className="home-pattern-region home-pattern-region-right">
        <MotionAmbient
          mode="counter-drift"
          className="home-pattern-layer home-pattern-secondary"
        >
          <img src={laurelsUrl} alt="" />
        </MotionAmbient>
      </div>
      <MotionSurface className="home-motion-surface home-motion-hero">
        <header className="home-terminal-heading">
          <div>
            <p className="eyebrow">SOFTWARE & SAAS RESEARCH</p>
            <h1>Company research workspace</h1>
            <p>
              Research a company by name or website, then inspect its outlook,
              fundamentals and source evidence.
            </p>
          </div>
          <span className="directory-status">
            <span className="status-dot" />
            Public company research
          </span>
          <div className="home-space-scene" aria-hidden="true">
            <MotionAmbient mode="orbit" className="home-orbit">
              <img src={armillaryUrl} alt="" />
            </MotionAmbient>
            <MotionAmbient mode="flyby" className="home-rocket">
              <img src={rocketUrl} alt="" />
            </MotionAmbient>
          </div>
        </header>
      </MotionSurface>
      <div className="home-terminal-grid">
        <MotionSurface className="home-motion-surface home-motion-directory">
          <section className="home-directory" aria-labelledby="choose-company">
            <div className="home-directory-heading">
              <h2 id="choose-company">Research a company</h2>
              <span>NAME / DOMAIN</span>
            </div>
            <form
              className="terminal-search company-research-form"
              onSubmit={(event) => {
                event.preventDefault();
                const query = search.trim();
                if (query.length < 2 || searching) return;
                const host = companyDomain(
                  query.includes("://") ? query : `https://${query}`,
                );
                // Exact websites use standalone discovery, independent of saved publications.
                if (host?.includes(".")) preview.mutate(query);
                else lookup.mutate(query);
              }}
            >
              <label htmlFor="company-domain-search">Search companies</label>
              <div className="terminal-search-row">
                <MotionInput
                  id="company-domain-search"
                  aria-label="Search companies"
                  aria-describedby="company-domain-search-help"
                  type="search"
                  placeholder="Company name or domain, e.g. posthog.com"
                  value={search}
                  maxLength={200}
                  disabled={searching}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(0);
                    lookup.reset();
                    preview.reset();
                  }}
                />
                <MotionButton
                  type="submit"
                  disabled={search.trim().length < 2 || searching}
                >
                  {searching ? (
                    <span className="loading-label">
                      <CompanySpinner
                        size="small"
                        website={preview.variables ?? search}
                      />
                      Finding company…
                    </span>
                  ) : (
                    "Research company"
                  )}
                </MotionButton>
              </div>
              <p
                id="company-domain-search-help"
                className="company-search-help"
              >
                Enter a name or website. You’ll confirm the company before
                research begins.
              </p>
            </form>
            {(lookup.error || preview.error) && (
              <p role="alert">{(lookup.error ?? preview.error)?.message}</p>
            )}
            {lookup.data && lookup.data.candidates[0]?.source !== "input" && (
              <section
                aria-label="Company website candidates"
                aria-live="polite"
              >
                <p>
                  {lookup.data.candidates.length
                    ? "Choose the correct website. Directory matches are candidates; check the identity preview before research."
                    : "No reliable website match was found. Enter the company's exact website domain."}
                </p>
                {lookup.data.source_url && (
                  <p>
                    <a
                      href={lookup.data.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {lookup.data.source_attribution}
                    </a>
                    . Names must match a listed domain; aliases and small
                    businesses may require their exact website.
                  </p>
                )}
                <ul className="company-results company-candidates">
                  {lookup.data.candidates.map((candidate) => (
                    <li key={candidate.domain}>
                      <div>
                        <strong>{candidate.domain}</strong>
                        <p>{candidate.name}</p>
                      </div>
                      <MotionButton
                        disabled={searching}
                        onClick={() => preview.mutate(candidate.website)}
                      >
                        Inspect {candidate.domain}
                      </MotionButton>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {choices.error ? (
              <div>
                <p role="status">
                  Saved company assessments are unavailable. You can still
                  research a company using the search above.
                </p>
                <MotionButton onClick={() => void choices.refetch()}>
                  Retry saved assessments
                </MotionButton>
              </div>
            ) : (
              <QueryState
                pending={choices.isPending}
                error={null}
                retry={() => void choices.refetch()}
              />
            )}
            {companyQueries.map((query, index) => (
              <QueryState
                key={publications[index].assessment.publication_id}
                pending={query.isPending}
                error={query.error}
                retry={() => void query.refetch()}
              />
            ))}

            {choices.data?.items.length === 0 && (
              <p role="status">
                No company assessments have been published yet.
              </p>
            )}
            {rows && (
              <>
                <h3 className="saved-research-heading">Saved research</h3>
                <p className="directory-count" role="status">
                  {rows.length} {rows.length === 1 ? "company" : "companies"}{" "}
                  available across configured publications
                </p>
                {rows.length === 0 && (
                  <p>
                    No companies match your search in saved research. Enter the
                    company’s website and select Research company to research it
                    for the first time.
                  </p>
                )}
                <ul className="company-results">
                  {rows
                    .slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
                    .map(({ company, snapshot, publication }) => (
                      <li key={snapshot + company.company_id}>
                        <div className="company-monogram" aria-hidden="true">
                          {company.display_name.slice(0, 1)}
                        </div>
                        <div>
                          <h3>{company.display_name}</h3>
                          <p>
                            {company.segment} · {date(publication.source.as_of)}
                          </p>

                          <small>
                            <span>
                              {companyDomain(company.website_url) ??
                                "Website not recorded"}
                            </span>
                            {publication.source.synthetic &&
                              " · Synthetic test data"}
                          </small>
                        </div>
                        <div className="company-result-actions">
                          <Link
                            className="button"
                            aria-label={`Open dossier for ${company.display_name}`}
                            to={`/companies/${encodeURIComponent(snapshot)}/${encodeURIComponent(company.company_id)}`}
                          >
                            Open dossier
                          </Link>
                          <Link
                            to={
                              "/research/new?" +
                              new URLSearchParams({
                                domain:
                                  companyDomain(company.website_url) ?? "",
                                company: company.company_id,
                                publication: snapshot,
                              }).toString()
                            }
                            aria-label={
                              "Research company " + company.display_name
                            }
                          >
                            Research company
                          </Link>
                        </div>
                      </li>
                    ))}
                </ul>
                {rows.length > PAGE_SIZE && (
                  <nav className="directory-pages" aria-label="Company pages">
                    <MotionButton
                      className="secondary"
                      disabled={page === 0}
                      onClick={() => setPage(page - 1)}
                    >
                      Previous
                    </MotionButton>
                    <span>
                      Page {page + 1} of {Math.ceil(rows.length / PAGE_SIZE)}
                    </span>
                    <MotionButton
                      className="secondary"
                      disabled={(page + 1) * PAGE_SIZE >= rows.length}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </MotionButton>
                  </nav>
                )}
              </>
            )}
          </section>
        </MotionSurface>
        <MotionSurface className="home-motion-surface home-motion-fundamentals">
          <aside className="home-fundamentals">
            <span className="micro-label">INSIDE THE DOSSIER</span>
            <h2>
              One company.
              <br />
              Five fundamental views.
            </h2>
            <p>
              See the evidence behind each area, then inspect its sources in a
              side panel.
            </p>
            <ol>
              {[
                "Adoption & Retention",
                "Attention & Sentiment",
                "Financial Health",
                "Industry & Competition",
                "Team & Execution",
              ].map((name, index) => (
                <li key={name}>
                  <span>0{index + 1}</span>
                  {name}
                </li>
              ))}
            </ol>

            <div className="home-model-note">
              Local model inference
              <br />
              <strong>Predictions currently unavailable</strong>
            </div>
          </aside>
        </MotionSurface>
      </div>
    </div>
  );
}
