import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, type DTO } from "../../api/client";
import {
  date,
  QueryState,
  Reasons,
  SourceLink,
  SyntheticNotice,
} from "../../components/Common";
import { companyDomain } from "../companies/identity";
import { metricPeriod, observationValue } from "../companies/shared";
import { researchResult } from "./client";

async function fetchReport(reportId: string) {
  return researchResult(
    await api.GET("/api/v1/research-reports/{report_id}", {
      params: { path: { report_id: reportId } },
    }),
  );
}
type Report = Awaited<ReturnType<typeof fetchReport>>;

const groupNames: Record<DTO<"SpecialistOutlook">["group_id"], string> = {
  adoption_retention: "Adoption & Retention",
  attention_sentiment: "Attention & Sentiment",
  financial_health: "Financial Health",
  industry_competition: "Industry & Competition",
  team_execution: "Team & Execution",
};
const dataNames = {
  available: "Available observations",
  insufficient_data: "Insufficient data",
  not_applicable: "Not applicable",
};
const forecastNames = {
  growth: "Growth",
  survival: "Survival",
  financial_health: "Financial Health",
};

/** Resolve public observation references without inferring values or freshness policy. */
function Measurements({
  report,
  ids,
  usable,
}: {
  report: Report;
  ids: string[];
  usable: string[];
}) {
  const saved = report.inventory.saved_context;
  const definitions = new Map(
    saved.definitions.map((row) => [row.metric_id, row]),
  );
  const savedMetrics = new Map(
    saved.metrics.map((row) => [row.observation_id, row]),
  );
  const freshMetrics = new Map(
    report.inventory.observations.map((row) => [row.observation_id, row]),
  );
  return ids.length ? (
    <dl className="research-metrics">
      {ids.map((id) => {
        const fresh = freshMetrics.get(id);
        const old = savedMetrics.get(id);
        if (!fresh && !old)
          return (
            <div key={id}>
              <dt>Unresolved measurement</dt>
              <dd>Unavailable</dd>
            </div>
          );
        const definition = old && definitions.get(old.metric_id);
        const sourceIds = fresh?.evidence_ids ?? old!.evidence_ids;
        return (
          <div key={id}>
            <dt>
              {fresh
                ? "Hacker News exact-domain story links"
                : (definition?.label ?? old!.metric_id)}
            </dt>
            <dd>
              <strong>
                {fresh
                  ? fresh.value === null
                    ? "Unavailable"
                    : fresh.value.toLocaleString("en-GB")
                  : observationValue(old!)}
              </strong>
              <small>
                {fresh
                  ? "Fresh collection · story links"
                  : "Saved context · " +
                    (definition?.unit ?? "Unit unavailable") +
                    (definition?.currency ? " · " + definition.currency : "")}
              </small>
              <small>
                {fresh
                  ? date(fresh.window.start) +
                    " to " +
                    date(fresh.window.end) +
                    " (end excluded)"
                  : metricPeriod(old!)}
              </small>
              <small>
                Available {date(fresh?.available_at ?? old!.available_at)} ·
                Collected {date(fresh?.collected_at ?? old!.collected_at)}
              </small>
              <p>{fresh?.definition ?? definition?.definition}</p>
              {old &&
                saved.coverage.some((row) =>
                  row.stale_metric_ids.includes(old.metric_id),
                ) && (
                  <small className="stale-label">
                    Stale in the saved analysis
                  </small>
                )}
              {old?.reason && <p>{old.reason}</p>}
              {fresh && <Reasons reasons={fresh.reason_codes} />}
              <small>
                {usable.includes(id)
                  ? "Usable observation at report cutoff; not model confidence."
                  : "Not marked usable at report cutoff; inspect source limitations."}
              </small>
              {sourceIds.map((sourceId) => {
                const source = [
                  ...saved.evidence,
                  ...report.inventory.evidence,
                ].find((row) => row.evidence_id === sourceId);
                return source ? (
                  <details key={sourceId}>
                    <summary>{source.provider} source</summary>
                    <p>
                      {source.assertion ??
                        "Restricted source contents are unavailable."}
                    </p>
                    {source.url && (
                      <SourceLink url={source.url}>Original source</SourceLink>
                    )}
                    <small>
                      Available {date(source.available_at)} · Collected{" "}
                      {date(source.collected_at)}
                    </small>
                  </details>
                ) : (
                  <small key={sourceId}>Source unavailable</small>
                );
              })}
            </dd>
          </div>
        );
      })}
    </dl>
  ) : (
    <p>
      No measurements are assigned to this section. This is an evidence gap, not
      a negative prediction.
    </p>
  );
}

/** Render the model-owned report in the approved hierarchy, including legacy reports. */
export function ResearchWorkspace({ report }: { report: Report }) {
  const saved = report.inventory.saved_context;
  const sections = report.outlook.specialists;
  const [active, setActive] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  const section = sections[active];
  const partial = report.inventory.observations.some((row) =>
    row.reason_codes.includes("provider_results_truncated"),
  );
  const sources = [...report.inventory.evidence, ...saved.evidence];
  const savedPath =
    "/companies/" +
    encodeURIComponent(report.assessment_publication_id) +
    "/" +
    encodeURIComponent(saved.company.company_id);
  return (
    <article className="prediction-workspace">
      <Link to="/">Companies</Link>
      <header className="workspace-header">
        <div>
          <p className="eyebrow">STARTUP OUTLOOK</p>
          <h1>{saved.company.display_name}</h1>
          <p>
            {companyDomain(saved.company.website_url) ?? "Website not recorded"}{" "}
            · {saved.company.segment}
          </p>
        </div>
        <div className="workspace-date">
          <strong>Research report</strong>
          <span>Cutoff {date(report.outlook.as_of)}</span>
          <span>Saved evidence {date(saved.publication.source.as_of)}</span>
          <Link to={"/research/jobs/" + encodeURIComponent(report.job_id)}>
            View research status
          </Link>
        </div>
      </header>
      <SyntheticNotice synthetic={report.inventory.synthetic} />
      {partial && (
        <p role="note" className="notice warning">
          Partial source results: the provider did not return an exhaustive
          result. The attention count remains unavailable.
        </p>
      )}
      <nav className="profile-sections" aria-label="Report sections">
        <a href="#startup-outlook">Outlook</a>
        <a href="#fundamental-drivers">Fundamental drivers</a>
        <a href="#research-sources">Sources & limitations</a>
      </nav>
      <section
        id="startup-outlook"
        className="workspace-outlook panel"
        aria-labelledby="outlook-title"
      >
        <p className="eyebrow">STARTUP OUTLOOK</p>
        <h2 id="outlook-title">Overall outlook unavailable</h2>
        <p>
          Models are not trained. Available evidence can be inspected below; it
          does not establish a probability of growth, survival or financial
          health.
        </p>
        <Reasons reasons={report.outlook.overall_reason_codes} />
        {report.outlook.forecasts ? (
          <div className="workspace-forecasts">
            {report.outlook.forecasts.map((forecast) => (
              <section key={forecast.outcome_id} className="workspace-forecast">
                <h3>
                  {forecastNames[forecast.outcome_id]}{" "}
                  <span>{forecast.horizon_months} months</span>
                </h3>
                <p className="forecast-value">Prediction unavailable</p>
                <p>Target definition pending · Model not trained</p>
                <Reasons reasons={forecast.reason_codes} />
              </section>
            ))}
          </div>
        ) : (
          <p className="notice" role="note">
            Legacy report: this saved report predates the three forecast
            outcomes. Its original analysis is preserved; no new forecasts have
            been added. <Link to={savedPath}>View original saved analysis</Link>
          </p>
        )}
      </section>
      <div className="workspace-grid">
        <section id="fundamental-drivers" aria-labelledby="drivers-title">
          <h2 id="drivers-title">Fundamental drivers</h2>
          <p className="disclaimer">
            Evidence availability and model readiness are separate.
          </p>
          <div className="workspace-drivers">
            {sections.map((row, index) => (
              <section className="workspace-driver" key={row.group_id}>
                <div>
                  <h3>{groupNames[row.group_id]}</h3>
                  <div className="driver-state">
                    <span>Data: {dataNames[row.data_status]}</span>
                    <span>Model: not trained</span>
                  </div>
                  <small>
                    {row.usable_metric_observation_ids.length} usable of{" "}
                    {row.metric_observation_ids.length} assigned observations
                  </small>
                </div>
                <button
                  className="secondary"
                  aria-label={"Inspect " + groupNames[row.group_id]}
                  onClick={() => {
                    setActive(index);
                    dialog.current?.showModal();
                  }}
                >
                  Inspect
                </button>
              </section>
            ))}
          </div>
        </section>
        <aside
          className="panel workspace-notes"
          aria-label="Coverage and validation"
        >
          <h2>What this report supports</h2>
          <p>
            Fresh research is a bounded Hacker News exact-domain link check.
            Other measurements are saved context.
          </p>
          <h3>Validation</h3>
          <p>
            No trained prediction, confidence interval or backtest is available.
          </p>
          <h3>Signals and risks</h3>
          <p>
            No new predictive narrative is supplied. Inspect the measured
            evidence and its limitations.
          </p>
          <Link to={savedPath}>Original saved evidence & risks</Link>
          <Reasons reasons={report.limitations} />
        </aside>
      </div>
      <section
        id="research-sources"
        className="company-section"
        aria-labelledby="sources-title"
      >
        <h2 id="sources-title">Sources & limitations</h2>
        {sources.length ? (
          <ul className="research-source-list">
            {sources.map((source) => (
              <li key={source.evidence_id}>
                <strong>{source.provider}</strong>
                <small>
                  {report.inventory.evidence.includes(source)
                    ? "Fresh collection"
                    : "Saved context"}{" "}
                  · {source.review_state.replaceAll("_", " ")}
                </small>
                <p>
                  {source.assertion ??
                    "Restricted source contents are unavailable."}
                </p>
                {source.url && (
                  <SourceLink url={source.url}>Original source</SourceLink>
                )}
                <small>
                  Published {date(source.published_at)} · Available{" "}
                  {date(source.available_at)} · Collected{" "}
                  {date(source.collected_at)}
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p>No source records supplied.</p>
        )}
        {report.outlook.unassigned_metric_observation_ids.length > 0 && (
          <details>
            <summary>Evidence outside the five driver groups</summary>
            <p>
              These observations have no approved group mapping. They are not
              silently assigned to a model.
            </p>
            <Measurements
              report={report}
              ids={report.outlook.unassigned_metric_observation_ids}
              usable={[]}
            />
          </details>
        )}
        <details>
          <summary>Report versions and provenance</summary>
          <dl className="metadata">
            {Object.entries({
              Report: report.report_id,
              "Research inventory": report.inventory.inventory_id,
              "Saved source": report.source_publication_id,
              "Saved assessment": report.assessment_publication_id,
              "Data version": report.data_version,
              "Model version": "Not trained",
              "Grouping policy": report.outlook.grouping_policy_version,
            }).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </details>
      </section>
      <dialog
        className="driver-dialog"
        ref={dialog}
        aria-labelledby="driver-dialog-title"
      >
        <div className="driver-dialog-header">
          <h2 id="driver-dialog-title">
            {section ? groupNames[section.group_id] : "Driver details"}
          </h2>
          <button
            className="secondary"
            autoFocus
            onClick={() => dialog.current?.close()}
          >
            Close
          </button>
        </div>
        <div
          role="tablist"
          aria-label="Fundamental drivers"
          className="driver-tabs"
          onKeyDown={(event) => {
            let next = active;
            if (event.key === "ArrowRight")
              next = (active + 1) % sections.length;
            else if (event.key === "ArrowLeft")
              next = (active + sections.length - 1) % sections.length;
            else if (event.key === "Home") next = 0;
            else if (event.key === "End") next = sections.length - 1;
            else return;
            event.preventDefault();
            setActive(next);
            tabs.current[next]?.focus();
          }}
        >
          {sections.map((row, index) => (
            <button
              key={row.group_id}
              ref={(element) => {
                tabs.current[index] = element;
              }}
              id={"driver-tab-" + row.group_id}
              role="tab"
              aria-selected={active === index}
              tabIndex={active === index ? 0 : -1}
              aria-controls="driver-panel"
              onClick={() => setActive(index)}
            >
              {groupNames[row.group_id]}
            </button>
          ))}
        </div>
        {section && (
          <div
            className="driver-panel"
            id="driver-panel"
            role="tabpanel"
            tabIndex={0}
            aria-labelledby={"driver-tab-" + section.group_id}
          >
            <p>Data: {dataNames[section.data_status]} · Model: not trained</p>
            <p>Prediction unavailable</p>
            <Reasons reasons={section.reason_codes} />
            <h3>Observed evidence</h3>
            <Measurements
              report={report}
              ids={section.metric_observation_ids}
              usable={section.usable_metric_observation_ids}
            />
          </div>
        )}
      </dialog>
    </article>
  );
}

export default function ResearchReportPage() {
  const { reportId = "" } = useParams();
  const query = useQuery({
    queryKey: ["research-report", reportId],
    queryFn: () => fetchReport(reportId),
  });
  return (
    <>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && <ResearchWorkspace key={reportId} report={query.data} />}
    </>
  );
}
