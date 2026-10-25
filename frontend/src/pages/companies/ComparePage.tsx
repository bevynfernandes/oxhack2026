import { MotionDisclosure, MotionLink as Link } from "../../motion";
import { useQueries } from "@tanstack/react-query";
import ResearchComparison from "../research/ResearchComparison";
import {
  FORECAST_SOURCE,
  PRELOADED_FORECASTS,
} from "../research/preloadedForecasts";
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
  const records = params.getAll("record");
  const saved = records.map((path) =>
    /^\/companies\/([^/]+)\/([^/]+)$/.exec(path),
  );
  const samePublication =
    records.length >= 2 &&
    saved.every((match) => match && match[1] === saved[0]?.[1]);
  return params.has("record") && !samePublication ? (
    <ResearchComparison />
  ) : (
    <PublishedComparison
      selection={
        samePublication
          ? {
              snapshot: saved[0]![1],
              ids: saved.map((match) => match![2]),
            }
          : undefined
      }
    />
  );
}
function PublishedComparison({
  selection,
}: {
  selection?: { snapshot: string; ids: string[] };
}) {
  const [params] = useSearchParams();
  const snapshot = selection?.snapshot ?? params.get("snapshot") ?? "";
  const ids = selection?.ids ?? params.getAll("company");
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
  const definitions = [
    ...new Map(
      profiles.flatMap((profile) =>
        profile.definitions.map((row) => [row.metric_id, row] as const),
      ),
    ).values(),
  ];
  const aiScores = profiles.map((profile) =>
    profile.publication.source.snapshot_id === FORECAST_SOURCE
      ? PRELOADED_FORECASTS[profile.company.company_id]
      : undefined,
  );
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
      <header className="page-heading comparison-heading">
        <span className="micro-label">SIDE BY SIDE / COMPANY INTELLIGENCE</span>
        <h1>Compare companies</h1>
        <p>
          One view of every measurement, AI outlook and local model result.
          Missing data stays visible; no composite winner is implied.
        </p>
        {complete && (
          <p className="comparison-count">
            {profiles.length} companies · {definitions.length} source metrics ·
            Same dated publication
          </p>
        )}
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
          <MotionDisclosure summary="Source snapshot & limitations">
            <PublicationNotice publication={profiles[0].publication} />
          </MotionDisclosure>
          {contextDiffers && (
            <p className="notice comparison-context-note">
              Stage or business model differs or is unknown. Check each
              company's context before interpreting differences.
            </p>
          )}
          <div
            className="table-scroll comparison-scroll complete-comparison"
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
                {aiScores.some(Boolean) && (
                  <>
                    <tr className="comparison-group">
                      <th colSpan={profiles.length + 1}>
                        AI outlook indices{" "}
                        <small>
                          Prepared AI estimates / 100 · not calibrated
                          probabilities
                        </small>
                      </th>
                    </tr>
                    {(
                      [
                        ["growth", "Growth outlook · 24 months"],
                        ["survival", "Survival outlook · 24 months"],
                        ["financial_health", "Financial health · 12 months"],
                      ] as const
                    ).map(([outcome, label]) => (
                      <tr key={outcome}>
                        <th scope="row">{label}</th>
                        {profiles.map((profile, index) => {
                          const card = aiScores[index]?.find(
                            (row) => row.outcome === outcome,
                          );
                          return (
                            <td key={profile.company.company_id}>
                              {card ? (
                                <>
                                  <strong className="comparison-score">
                                    {card.score}
                                    <span> / 100</span>
                                  </strong>
                                  <p>{card.rationale}</p>
                                  <small>{card.caveat}</small>
                                </>
                              ) : (
                                "Not available"
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </>
                )}
                {profiles.some((profile) => profile.dimension_models) && (
                  <>
                    <tr className="comparison-group">
                      <th colSpan={profiles.length + 1}>
                        Local model results{" "}
                        <small>
                          Computed from source inputs · experimental proxies
                        </small>
                      </th>
                    </tr>
                    {(
                      [
                        ["adoption_retention", "SDK demand index"],
                        ["attention_sentiment", "Title sentiment index"],
                        ["financial_health", "Financial model"],
                        ["industry_competition", "Competition model"],
                        ["team_execution", "Execution model"],
                      ] as const
                    ).map(([group, label]) => (
                      <tr key={group}>
                        <th scope="row">{label}</th>
                        {profiles.map((profile) => {
                          const model =
                            profile.dimension_models?.dimensions.find(
                              (row) => row.group_id === group,
                            );
                          return (
                            <td key={profile.company.company_id}>
                              {model?.score != null ? (
                                <strong className="comparison-score">
                                  {model.score.toFixed(1)}
                                  <span> / 100</span>
                                </strong>
                              ) : (
                                <strong>Unavailable</strong>
                              )}
                              <small>
                                {model?.eligibility.replaceAll("_", " ") ??
                                  "Model not available"}
                              </small>
                              {model && (
                                <MotionDisclosure summary="Model details">
                                  <p>{model.target}</p>
                                  <ul>
                                    {model.limitations.map((limit) => (
                                      <li key={limit}>{limit}</li>
                                    ))}
                                  </ul>
                                </MotionDisclosure>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </>
                )}
                <tr className="comparison-group">
                  <th colSpan={profiles.length + 1}>
                    Company context & original assessments
                  </th>
                </tr>
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
                <tr className="comparison-group">
                  <th colSpan={profiles.length + 1}>
                    All source measurements{" "}
                    <small>
                      {definitions.length} metrics · includes missing and
                      unavailable values
                    </small>
                  </th>
                </tr>
                {definitions.map((definition) => (
                  <tr
                    key={definition.metric_id}
                    data-metric-id={definition.metric_id}
                  >
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
                              <strong className="comparison-value">
                                {observationValue(metric)}
                              </strong>
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
