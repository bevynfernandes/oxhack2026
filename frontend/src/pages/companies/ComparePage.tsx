import { MotionDisclosure, MotionLink as Link } from "../../motion";
import { useQueries } from "@tanstack/react-query";
import ResearchComparison from "../research/ResearchComparison";
import { useSearchParams } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import { date, QueryState } from "../../components/Common";
import {
  Coverage,
  metricPeriod,
  observationValue,
  outcomeNames,
  Outcomes,
  PublicationNotice,
} from "./shared";

/** Compare two or three exact profiles using the same source snapshot and definitions. */
export default function ComparePage() {
  const [params] = useSearchParams();
  return params.has("record") ? (
    <ResearchComparison />
  ) : (
    <PublishedComparison />
  );
}
function PublishedComparison() {
  const [params] = useSearchParams();
  const snapshot = params.get("snapshot") ?? "";
  const ids = params.getAll("company");
  const valid =
    Boolean(snapshot) &&
    ids.length >= 2 &&
    ids.length <= 3 &&
    new Set(ids).size === ids.length;
  const queries = useQueries({
    queries: (valid ? ids : []).map((company) => ({
      queryKey: ["company", snapshot, company],
      queryFn: async () =>
        unwrap(
          await api.GET(
            "/api/v1/company-snapshots/{snapshot_id}/companies/{company_id}",
            {
              params: { path: { snapshot_id: snapshot, company_id: company } },
            },
          ),
        ),
    })),
  });
  const profiles = queries.flatMap((query) => (query.data ? [query.data] : []));
  const measurements = profiles.map(
    (profile) => new Map(profile.metrics.map((row) => [row.metric_id, row])),
  );
  const staleMetrics = profiles.map(
    (profile) =>
      new Set(profile.coverage.flatMap((row) => row.stale_metric_ids)),
  );
  const complete =
    valid &&
    profiles.length === ids.length &&
    queries.every((query) => !query.error);
  const contextDiffers =
    new Set(
      profiles.map(
        ({ company }) =>
          `${company.segment}|${company.stage}|${company.business_model}`,
      ),
    ).size > 1 ||
    profiles.some(
      ({ company }) =>
        company.stage === null || company.business_model === null,
    );
  return (
    <>
      <Link to={`/explore?${params}`}>Change company selection</Link>
      <header className="page-heading">
        <h1>Compare companies</h1>
        <p>
          Read the same outcomes and metric definitions side by side. There is
          no composite winner.
        </p>
      </header>
      {!valid ? (
        <p role="alert">
          Choose two or three distinct companies from one published snapshot.
        </p>
      ) : (
        <QueryState
          pending={queries.some((query) => query.isPending)}
          error={queries.find((query) => query.error)?.error ?? null}
          retry={() => {
            void Promise.all(queries.map((query) => query.refetch()));
          }}
        />
      )}
      {complete && (
        <>
          <PublicationNotice publication={profiles[0].publication} />
          {contextDiffers && (
            <p className="notice">
              Stage or business model differs or is unknown. Check each
              company's context before interpreting differences.
            </p>
          )}
          <div
            className="table-scroll comparison-scroll"
            role="region"
            aria-label="Company comparison"
            tabIndex={0}
          >
            <table className="comparison-table">
              <caption>
                Same snapshot and metric definitions; unknowns remain unknown.
                Source dates and stale values are shown in place.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Assessment or metric</th>
                  {profiles.map((profile) => (
                    <th scope="col" key={profile.company.company_id}>
                      <Link
                        to={`/companies/${encodeURIComponent(snapshot)}/${encodeURIComponent(profile.company.company_id)}`}
                      >
                        {profile.company.display_name}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Company context</th>
                  {profiles.map(({ company }) => (
                    <td key={company.company_id}>
                      {company.segment}
                      <br />
                      {company.stage ?? "Stage unknown"}
                      <br />
                      {company.business_model ?? "Business model unknown"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Assessment date</th>
                  {profiles.map((profile) => (
                    <td key={profile.company.company_id}>
                      {date(profile.assessment.as_of)}
                    </td>
                  ))}
                </tr>
                {profiles[0].assessment.outcomes.map((outcome) => (
                  <tr key={outcome.outcome_id}>
                    <th scope="row">{outcomeNames[outcome.outcome_id]}</th>
                    {profiles.map((profile) => (
                      <td key={profile.company.company_id}>
                        <Outcomes
                          compact
                          outcomes={profile.assessment.outcomes.filter(
                            (row) => row.outcome_id === outcome.outcome_id,
                          )}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <th scope="row">Evidence coverage</th>
                  {profiles.map((profile) => (
                    <td key={profile.company.company_id}>
                      <Coverage rows={profile.coverage} />
                    </td>
                  ))}
                </tr>
                {profiles[0].definitions.map((definition) => (
                  <tr key={definition.metric_id}>
                    <th scope="row">
                      {definition.label}
                      <small>
                        {definition.scope} · {definition.unit}
                        {definition.currency ? ` · ${definition.currency}` : ""}
                      </small>
                      <MotionDisclosure summary={<>Definition</>}>
                        <p>{definition.definition}</p>
                        <p>{definition.applicability}</p>
                        <small>{definition.metric_id}</small>
                      </MotionDisclosure>
                    </th>
                    {profiles.map((profile, index) => {
                      const metric = measurements[index].get(
                        definition.metric_id,
                      );
                      const stale = staleMetrics[index].has(
                        definition.metric_id,
                      );
                      return (
                        <td key={profile.company.company_id}>
                          {metric ? (
                            <>
                              {observationValue(metric)}
                              {stale && (
                                <strong className="stale-label">
                                  Stale at assessment date
                                </strong>
                              )}
                              <small>{metricPeriod(metric)}</small>
                              {metric.reason && <p>{metric.reason}</p>}
                              <small>
                                Available {date(metric.available_at)} ·
                                Collected {date(metric.collected_at)}
                              </small>
                              <Link
                                to={`/companies/${encodeURIComponent(snapshot)}/${encodeURIComponent(profile.company.company_id)}#sources`}
                              >
                                Inspect sources
                              </Link>
                            </>
                          ) : (
                            "Metric unavailable"
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
