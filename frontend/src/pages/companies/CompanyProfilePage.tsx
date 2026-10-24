import { useEffect, useRef } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { date, QueryState, Reasons, SourceLink } from "../../components/Common";
import {
  Coverage,
  families,
  metricPeriod,
  observationValue,
  Outcomes,
  PublicationNotice,
  useCompany,
} from "./shared";

/** Explain one company's exact published assessment and inspectable evidence. */
export default function CompanyProfilePage() {
  const { snapshotId = "", companyId = "" } = useParams();
  const query = useCompany(snapshotId, companyId);
  const profile = query.data;
  const { hash } = useLocation();
  const sourceDetails = useRef<HTMLDetailsElement>(null);
  const openSources = () => {
    if (sourceDetails.current) sourceDetails.current.open = true;
  };
  useEffect(() => {
    if (hash === "#sources" && sourceDetails.current) {
      sourceDetails.current.open = true;
      sourceDetails.current.scrollIntoView();
    }
  }, [hash, profile]);
  const definitions = new Map(
    profile?.definitions.map((row) => [row.metric_id, row]),
  );
  const stale = new Set(
    profile?.coverage.flatMap((row) => row.stale_metric_ids),
  );
  return (
    <>
      <Link to={`/?${new URLSearchParams({ snapshot: snapshotId })}`}>
        Companies
      </Link>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {profile && (
        <>
          <header className="page-heading">
            <h1>{profile.company.display_name}</h1>
            <p>
              {profile.company.segment} ·{" "}
              {profile.company.stage ?? "Stage unknown"} ·{" "}
              {profile.company.business_model ?? "Business model unknown"}
            </p>
            <SourceLink url={profile.company.website_url}>
              Company website
            </SourceLink>
          </header>
          <PublicationNotice publication={profile.publication} />
          <section aria-labelledby="outlook-heading">
            <h2 id="outlook-heading">Company outlook</h2>
            <p>
              These sections describe available evidence. No validated company
              success probability is published.
            </p>
            <Outcomes outcomes={profile.assessment.outcomes} />
          </section>
          <section
            className="company-section"
            aria-labelledby="signals-heading"
          >
            <h2 id="signals-heading">Evidence, risks and unknowns</h2>
            <ul className="statement-list">
              {profile.assessment.statements.map((statement) => (
                <li key={statement.statement_id}>
                  <strong>
                    {
                      {
                        observation: "Observed evidence",
                        risk: "Supported risk",
                        evidence_gap: "Evidence gap",
                      }[statement.role]
                    }
                  </strong>
                  <p>{statement.text}</p>
                  {statement.evidence_ids.length > 0 && (
                    <a href="#sources" onClick={openSources}>
                      Inspect {statement.evidence_ids.length} supporting
                      source(s)
                    </a>
                  )}
                  {statement.missing_metric_ids.length > 0 && (
                    <small>
                      Unavailable for assessment:{" "}
                      {statement.missing_metric_ids
                        .map((id) => definitions.get(id)?.label ?? id)
                        .join(", ")}
                    </small>
                  )}
                </li>
              ))}
            </ul>
          </section>
          <section
            className="company-section"
            aria-labelledby="metrics-heading"
          >
            <h2 id="metrics-heading">Business evidence</h2>
            <p>
              Definitions and periods matter. A product or repository metric
              describes that scope, rather than company revenue or customers.
            </p>
            <Coverage rows={profile.coverage} />
            {families.map(([family, label]) => {
              const rows = profile.metrics.filter(
                (row) => definitions.get(row.metric_id)?.family === family,
              );
              return (
                <section key={family} aria-label={label}>
                  <h3>{label}</h3>
                  {rows.length === 0 ? (
                    <p>No metric definitions published for this family.</p>
                  ) : (
                    <div
                      className="table-scroll"
                      role="region"
                      aria-label={`${label} metrics`}
                      tabIndex={0}
                    >
                      <table>
                        <caption>
                          {label} measurements at the selected cutoff
                        </caption>
                        <thead>
                          <tr>
                            <th scope="col">Metric</th>
                            <th scope="col">Value</th>
                            <th scope="col">Period</th>
                            <th scope="col">Evidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((row) => {
                            const definition = definitions.get(row.metric_id)!;
                            return (
                              <tr key={row.observation_id}>
                                <th scope="row">
                                  {definition.label}
                                  <small>
                                    {definition.scope} · {definition.unit}
                                    {definition.currency
                                      ? ` · ${definition.currency}`
                                      : ""}
                                  </small>
                                  <details>
                                    <summary>
                                      Definition and applicability
                                    </summary>
                                    <p>{definition.definition}</p>
                                    <p>{definition.applicability}</p>
                                    <small>
                                      Freshness limit:{" "}
                                      {definition.maximum_age_days} days ·{" "}
                                      {definition.metric_id}
                                    </small>
                                  </details>
                                </th>
                                <td>
                                  {observationValue(row)}
                                  {stale.has(row.metric_id) && (
                                    <strong className="stale-label">
                                      Stale at assessment date
                                    </strong>
                                  )}
                                  {row.reason && <small>{row.reason}</small>}
                                </td>
                                <td>{metricPeriod(row)}</td>
                                <td>
                                  {row.evidence_ids.length > 0 ? (
                                    <a href="#sources" onClick={openSources}>
                                      {row.evidence_ids.length} source(s)
                                    </a>
                                  ) : (
                                    "No source measurement"
                                  )}
                                  <small>
                                    Available {date(row.available_at)}
                                    <br />
                                    Collected {date(row.collected_at)}
                                  </small>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              );
            })}
          </section>
          <section className="company-section" aria-labelledby="events-heading">
            <h2 id="events-heading">Company events</h2>
            {profile.events.length === 0 ? (
              <p>No company events published in this snapshot.</p>
            ) : (
              <ol className="event-list">
                {[...profile.events]
                  .sort((left, right) =>
                    (right.occurred_on ?? "").localeCompare(
                      left.occurred_on ?? "",
                    ),
                  )
                  .map((event) => (
                    <li key={event.event_id}>
                      <strong>
                        {event.occurred_on ?? "Occurrence date unknown"} ·{" "}
                        {event.kind.replaceAll("_", " ")} · {event.stage}
                      </strong>
                      <p>{event.description}</p>
                      <small>
                        Available {date(event.available_at)} · Collected{" "}
                        {date(event.collected_at)}
                      </small>
                      <a href="#sources" onClick={openSources}>
                        Inspect event sources
                      </a>
                    </li>
                  ))}
              </ol>
            )}
          </section>
          <details id="sources" className="company-section" ref={sourceDetails}>
            <summary>Sources and review status</summary>
            <p>
              Review status describes verification of a source claim, not the
              company's chance of success.
            </p>
            <ul className="source-list">
              {profile.evidence.map((source) => (
                <li key={source.evidence_id}>
                  <strong>
                    {source.provider} · {source.kind.replaceAll("_", " ")} ·{" "}
                    {source.review_state}
                  </strong>
                  <p>
                    {source.assertion ??
                      "Restricted source. Contents and attachment location are not public."}
                  </p>
                  {source.url && (
                    <SourceLink url={source.url}>Original source</SourceLink>
                  )}
                  <small>
                    Published {date(source.published_at)} · Available{" "}
                    {date(source.available_at)} · Collected{" "}
                    {date(source.collected_at)}
                  </small>
                  <small>
                    Availability basis:{" "}
                    {source.availability_basis.replaceAll("_", " ")} ·{" "}
                    {source.evidence_id}
                  </small>
                </li>
              ))}
            </ul>
          </details>
          <details>
            <summary>Ownership and assessment provenance</summary>
            <p>
              Effective family:{" "}
              {profile.family.family_id ?? "Unknown or conflicting"}
            </p>
            <Reasons reasons={profile.family.reason_codes} />
            <ul>
              {profile.relationships.map((row) => (
                <li key={row.relationship_id}>
                  {row.subject_kind}: {row.subject_id} · effective{" "}
                  {date(row.valid_from)} to{" "}
                  {row.valid_to ? date(row.valid_to) : "open end"}
                </li>
              ))}
            </ul>
            <dl className="metadata">
              <div>
                <dt>Assessment</dt>
                <dd>{profile.assessment.assessment_id}</dd>
              </div>
              <div>
                <dt>Policy</dt>
                <dd>{profile.assessment.policy_version}</dd>
              </div>
              <div>
                <dt>Recorded</dt>
                <dd>{date(profile.assessment.first_recorded_at)}</dd>
              </div>
              <div>
                <dt>Assessment mode</dt>
                <dd>{profile.assessment.mode}</dd>
              </div>
            </dl>
            <Reasons reasons={profile.assessment.limitations} />
            <Link to="/methodology">How to interpret these outcomes</Link>
          </details>
        </>
      )}
    </>
  );
}
