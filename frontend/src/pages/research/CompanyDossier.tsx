import ResearchTools from "./ResearchTools";
import DecisionBrief from "./DecisionBrief";
import SignalCharts from "./SignalCharts";
import { evidenceSummary } from "./summary";
import { CitedResearchAnalysis } from "./ResearchWorkflow";
import { MappingControls, MappedDimensionEvidence } from "./EvidenceMapping";
import { CashFlowResearch } from "./CashFlowResearch";
import {
  MotionSelection,
  MotionIndicator,
  MotionDisclosure,
  MotionLink as Link,
  MotionButton,
  MotionDialog,
  type MotionDialogHandle,
} from "../../motion";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useLocation } from "react-router-dom";
import type { DTO } from "../../api/client";
import {
  date,
  Reasons,
  SourceLink,
  SyntheticNotice,
} from "../../components/Common";
import { SourceProgress } from "./ResearchJobPage";
import Icon from "../../components/WorkspaceIcon";
import { companyDomain } from "../companies/identity";
import type { useCompany } from "../companies/shared";
import type { fetchResearchReport, fetchStandaloneReport } from "./client";
import {
  metricPeriod,
  observationValue,
  Outcomes,
  outcomeNames,
  Coverage,
  PublicationNotice,
} from "../companies/shared";

type Profile = NonNullable<ReturnType<typeof useCompany>["data"]>;
type Report = Awaited<ReturnType<typeof fetchResearchReport>>;
type StandaloneReport = Awaited<ReturnType<typeof fetchStandaloneReport>>;
type Group = DTO<"SpecialistOutlook">["group_id"];
const groups: {
  id: Group;
  name: string;
  description: string;
  icon: "chart" | "globe" | "finance" | "shield" | "people";
}[] = [
  {
    id: "adoption_retention",
    name: "Adoption & Retention",
    description:
      "Customer growth, product adoption and evidence of recurring use.",
    icon: "chart",
  },
  {
    id: "attention_sentiment",
    name: "Attention & Sentiment",
    description:
      "Public attention, independent coverage and supported sentiment.",
    icon: "globe",
  },
  {
    id: "financial_health",
    name: "Financial Health",
    description:
      "Commercial performance, financial resilience and capital context.",
    icon: "finance",
  },
  {
    id: "industry_competition",
    name: "Industry & Competition",
    description:
      "Market demand, competitive pressure and long-term positioning.",
    icon: "shield",
  },
  {
    id: "team_execution",
    name: "Team & Execution",
    description: "Product delivery, relevant experience and team continuity.",
    icon: "people",
  },
];
const forecastNames = {
  growth: "Growth outlook",
  survival: "Survival outlook",
  financial_health: "Financial health",
};
const dataNames = {
  available: "Evidence available",
  insufficient_data: "Evidence gap",
  not_applicable: "Not applicable",
};
type Panel =
  { kind: "driver"; index: number } | { kind: "sources"; index: number };
type Measurement = {
  id: string;
  label: string;
  value: string;
  unit: string;
  period: string;
  available: string;
  collected: string;
  definition: string;
  reason: string | null;
  evidence: string[];
  fresh: boolean;
  retained?: boolean;
};

/** Keep keyboard focus inside the open evidence drawer. */
function containFocus(event: KeyboardEvent<HTMLDialogElement>) {
  if (event.key !== "Tab") return;
  const elements = [
    ...event.currentTarget.querySelectorAll<HTMLElement>(
      'button:not([disabled]):not([tabindex="-1"]), a[href], summary, [tabindex="0"]',
    ),
  ].filter(
    (element) =>
      element.tabIndex >= 0 &&
      !element.matches(":disabled") &&
      !element.closest("[inert], [hidden]") &&
      getComputedStyle(element).visibility === "visible" &&
      element.getClientRects().length > 0,
  );
  const first = elements[0];
  const last = elements.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}

/** Present saved and freshly researched companies in the same viewport dossier. */
export default function CompanyDossier({
  profile,
  report,
  standalone,
}: {
  profile?: Profile;
  report?: Report;
  standalone?: StandaloneReport;
}) {
  const company = profile?.company ?? {
    company_id: standalone!.identity.identity_id,
    display_name: standalone!.identity.company_name,
    website_url: "https://" + standalone!.identity.canonical_domain,
    stage: null,
    segment: "Standalone research",
    business_model: null,
  };
  const decisionLayout = !report;
  const outlook = standalone?.outlook ?? report?.outlook ?? profile?.outlook;
  const dimensionModels = standalone
    ? standalone.dimension_models
    : profile?.dimension_models;
  const cashFlowResearch = standalone?.sources.find(
    (source) => source.provider === "sec",
  )?.cash_flow_research;
  const modelSections = useMemo(
    () =>
      new Map(dimensionModels?.dimensions.map((row) => [row.group_id, row])),
    [dimensionModels],
  );
  const eventSourceUrls = useMemo(
    () =>
      new Map(
        standalone?.events.flatMap((event) =>
          event.evidence_ids.map((id) => [id, event.url] as const),
        ),
      ),
    [standalone?.events],
  );
  const cutoff = outlook?.as_of ?? profile?.publication.source.as_of;
  const synthetic = profile?.publication.source.synthetic ?? false;
  const [mobileGroup, setMobileGroup] = useState(0);
  const [panel, setPanel] = useState<Panel>({ kind: "driver", index: 0 });
  const dialog = useRef<MotionDialogHandle>(null);
  const opener = useRef<HTMLElement | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const location = useLocation();
  const savedPath = profile
    ? `/companies/${encodeURIComponent(profile.publication.assessment.publication_id)}/${encodeURIComponent(company.company_id)}`
    : null;
  const researchPath = standalone
    ? "/research/identities/" +
      standalone.identity.identity_id +
      "?profile=" +
      (standalone.settings?.profile ?? "thorough")
    : "/research/new?" +
      new URLSearchParams({
        domain: companyDomain(company.website_url) ?? "",
        ...(profile
          ? {
              company: company.company_id,
              publication: profile.publication.assessment.publication_id,
            }
          : {}),
      }).toString();
  const measurements = useMemo(() => {
    const definitions = new Map(
      (profile?.definitions ?? []).map((row) => [row.metric_id, row]),
    );
    const rows: Measurement[] = (profile?.metrics ?? []).map((row) => {
      const definition = definitions.get(row.metric_id);
      return {
        id: row.observation_id,
        label: definition?.label ?? row.metric_id,
        value: observationValue(row),
        unit: [definition?.unit, definition?.currency]
          .filter(Boolean)
          .join(" · "),
        period: metricPeriod(row),
        available: row.available_at,
        collected: row.collected_at,
        definition: definition?.definition ?? "",
        reason: row.reason,
        evidence: row.evidence_ids,
        fresh: false,
      };
    });
    for (const row of report?.inventory.observations ?? [])
      rows.push({
        id: row.observation_id,
        label: "Hacker News exact-domain story links",
        value:
          row.value == null ? "Unavailable" : row.value.toLocaleString("en-GB"),
        unit: "story links",
        period: `${date(row.window.start)} to ${date(row.window.end)} (end excluded)`,
        available: row.available_at,
        collected: row.collected_at,
        definition: row.definition,
        reason: row.reason_codes.join(", ").replaceAll("_", " ") || null,
        evidence: row.evidence_ids,
        fresh: true,
      });
    const retainedCaptures = new Set(
      standalone?.sources.flatMap(
        (source) => source.details?.retained_capture_ids ?? [],
      ),
    );
    const captureByEvidence = new Map(
      standalone?.evidence.map((row) => [row.evidence_id, row.capture_id]),
    );
    for (const row of standalone?.observations ?? [])
      rows.push({
        id: row.observation_id,
        label: row.metric_id.replaceAll("_", " "),
        value:
          row.value == null ? "Unavailable" : row.value.toLocaleString("en-GB"),
        unit: row.unit,
        period: row.window
          ? date(row.window.start) +
            " to " +
            date(row.window.end) +
            " (end excluded)"
          : "Measurement period not supplied",
        available: "",
        collected: row.collected_at,
        definition: row.definition,
        reason: row.missing_reason ?? null,
        evidence: row.evidence_ids,
        fresh: row.origin === "fresh",
        retained:
          row.evidence_ids.length > 0 &&
          row.evidence_ids.every((id) =>
            retainedCaptures.has(captureByEvidence.get(id) ?? ""),
          ),
      });
    return new Map(rows.map((row) => [row.id, row]));
  }, [profile, report, standalone]);
  const sources = useMemo(
    () => [
      ...(report?.inventory.evidence ?? []),
      ...(profile?.evidence ?? []),
      ...(standalone?.evidence ?? []).map((row) => ({
        evidence_id: row.evidence_id,
        provider:
          standalone?.sources.find((source) =>
            source.evidence.some(
              (item) => item.evidence_id === row.evidence_id,
            ),
          )?.name ?? "Identity preview",
        kind: "fresh excerpt",
        review_state: "retrieved; attribution in claims",
        assertion: row.excerpt,
        url: row.url,
        available_at: null,
        collected_at: row.collected_at,
        published_at: null,
      })),
    ],
    [profile, report, standalone],
  );
  const sourceMap = useMemo(
    () => new Map(sources.map((row) => [row.evidence_id, row])),
    [sources],
  );
  const sections = useMemo(
    () => new Map(outlook?.specialists.map((row) => [row.group_id, row])),
    [outlook],
  );
  const assigned =
    outlook?.specialists.reduce(
      (sum, row) => sum + row.metric_observation_ids.length,
      0,
    ) ?? 0;
  const usable =
    outlook?.specialists.reduce(
      (sum, row) => sum + row.usable_metric_observation_ids.length,
      0,
    ) ?? 0;
  const partial =
    standalone?.mapping?.state === "partial" ||
    standalone?.sources.some((source) =>
      ["partial", "failed"].includes(source.state),
    ) ||
    report?.inventory.observations.some((row) =>
      row.reason_codes.includes("provider_results_truncated"),
    );
  const currentGroup = groups[panel.index];
  const isCashFlowDriver =
    currentGroup.id === "financial_health" && !!cashFlowResearch;
  const section =
    panel.kind === "driver" ? sections.get(currentGroup.id) : undefined;
  const dimensionModel =
    panel.kind === "driver" ? modelSections.get(currentGroup.id) : undefined;
  const open = (next: Panel) => {
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setPanel(next);
    dialog.current?.showModal();
  };
  useEffect(() => {
    if (location.hash === "#sources") {
      setPanel({ kind: "sources", index: 0 });
      dialog.current?.showModal();
    }
  }, [location.hash]);
  const exportReport = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(standalone ?? report ?? profile, null, 2)], {
        type: "application/json",
      }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${company.company_id}-research.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  const renderMeasurements = (ids: string[], usableIds: string[]) =>
    ids.length ? (
      <dl className="research-metrics">
        {ids.map((id) => {
          const row = measurements.get(id);
          return row ? (
            <div key={id}>
              <dt>{row.label}</dt>
              <dd>
                <strong>{row.value}</strong>
                <small>
                  {row.retained
                    ? "Retained collection"
                    : row.fresh
                      ? "Fresh collection"
                      : "Saved context"}{" "}
                  · {row.unit}
                </small>
                <small>{row.period}</small>
                <small>
                  Available {date(row.available || null)} · Collected{" "}
                  {date(row.collected)}
                </small>
                <p>{row.definition}</p>
                {row.reason && <p>{row.reason}</p>}
                <small>
                  {usableIds.includes(id)
                    ? "Usable observation at report cutoff; not model confidence."
                    : "Not marked usable at report cutoff; inspect source limitations."}
                </small>
                {row.evidence.map((sourceId) => {
                  const source = sourceMap.get(sourceId);
                  return source ? (
                    <MotionDisclosure
                      key={sourceId}
                      summary={<>{source.provider} source</>}
                    >
                      <p>
                        {source.assertion ??
                          "Restricted source. Contents and attachment location are not public."}
                      </p>
                      {source.url && (
                        <SourceLink url={source.url}>
                          Original source
                        </SourceLink>
                      )}
                      <small>
                        Available {date(source.available_at)} · Collected{" "}
                        {date(source.collected_at)}
                      </small>
                    </MotionDisclosure>
                  ) : (
                    <small key={sourceId}>Source unavailable</small>
                  );
                })}
              </dd>
            </div>
          ) : (
            <div key={id}>
              <dt>Unresolved measurement</dt>
              <dd>Unavailable</dd>
            </div>
          );
        })}
      </dl>
    ) : (
      <div className="drawer-empty">
        <Icon name="file" />
        <h3>No measurements published</h3>
        <p>This is an evidence gap, not a negative prediction.</p>
      </div>
    );
  const switchTab = (event: KeyboardEvent<HTMLDivElement>) => {
    const count = panel.kind === "driver" ? groups.length : 4;
    let next = panel.index;
    if (event.key === "ArrowRight") next = (next + 1) % count;
    else if (event.key === "ArrowLeft") next = (next + count - 1) % count;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = count - 1;
    else return;
    event.preventDefault();
    setPanel({ ...panel, index: next });
    tabRefs.current[next]?.focus();
  };
  return (
    <article
      className={`company-dossier ${decisionLayout ? "decision-dossier" : ""}`}
      aria-label="Company research dossier"
    >
      <header className="dossier-company">
        <div className="dossier-identity">
          <div className="dossier-monogram" aria-hidden="true">
            {company.display_name.slice(0, 1)}
          </div>
          <div>
            {decisionLayout && (
              <span className="micro-label">
                COMPANY RESEARCH / DECISION WORKSPACE
              </span>
            )}
            <div className="dossier-name">
              <h1>{company.display_name}</h1>
              <span className="stage-tag">
                {company.stage ?? "Stage undisclosed"}
              </span>
            </div>
            <p>
              {company.segment}
              <span className="context-dot">·</span>
              {company.business_model ?? "Software company"}
            </p>
            <span className="dossier-domain">
              {companyDomain(company.website_url) ?? "Website not recorded"}
            </span>
          </div>
        </div>
        <div className="dossier-readiness">
          <span className="micro-label">EVIDENCE COVERAGE</span>
          <strong>
            <span className="status-dot" />
            {usable} / {assigned} measurements
          </strong>
          <small>Source-backed · as of {date(cutoff ?? null)}</small>
        </div>
        {!decisionLayout && (
          <div className="dossier-outlook">
            <span className="outlook-mark" aria-hidden="true">
              —
            </span>
            <div>
              <span className="micro-label">STARTUP OUTLOOK</span>
              <h2>Overall outlook unavailable</h2>
              <small>
                {dimensionModels
                  ? "Auxiliary proxy experiments available · outcome models pending"
                  : "Outcome models not trained"}
              </small>
            </div>
          </div>
        )}
        <div className="dossier-actions">
          <Link className="button" to={researchPath}>
            {standalone ? "Refresh research" : "Research company"}{" "}
            <Icon name="arrow" />
          </Link>
          <MotionButton className="secondary" onClick={exportReport}>
            <Icon name="file" />
            Export report
          </MotionButton>
        </div>
      </header>
      {decisionLayout && (
        <DecisionBrief
          report={standalone}
          models={dimensionModels}
          usableIds={outlook?.specialists.flatMap(
            (row) => row.usable_metric_observation_ids,
          )}
          summary={evidenceSummary(profile, standalone, report)}
          onEvidence={() => open({ kind: "sources", index: 1 })}
        />
      )}
      {decisionLayout && (
        <SignalCharts
          observations={
            standalone
              ? standalone.observations.map((row) => ({
                  id: row.observation_id,
                  metric: row.metric_id,
                  definition: row.definition,
                  value:
                    row.applicability === "applicable" &&
                    !row.missing_reason &&
                    row.unit === "downloads"
                      ? (row.value ?? null)
                      : null,
                  window: row.window ?? null,
                }))
              : (profile?.metrics ?? []).map((row) => ({
                  id: row.observation_id,
                  metric: row.metric_id,
                  value:
                    row.state === "observed" &&
                    row.value?.kind === "integer" &&
                    profile?.definitions.some(
                      (definition) =>
                        definition.metric_id === row.metric_id &&
                        definition.unit === "downloads",
                    )
                      ? row.value.value
                      : null,
                  window: row.window,
                }))
          }
          models={dimensionModels}
          outlook={outlook}
          onEvidence={() => open({ kind: "driver", index: 0 })}
        />
      )}
      {(synthetic || partial || (report && !outlook?.forecasts)) && (
        <div className="dossier-banners">
          <SyntheticNotice synthetic={synthetic} />
          {partial && (
            <p className="notice warning" role="note">
              {standalone
                ? "Partial source results: inspect collection and mapping limits."
                : "Partial source results: attention count unavailable."}{" "}
              <MotionButton onClick={() => open({ kind: "sources", index: 0 })}>
                View limitations
              </MotionButton>
            </p>
          )}
          {report && !outlook?.forecasts && (
            <p className="notice" role="note">
              Legacy report: original analysis preserved.{" "}
              <Link to={savedPath!}>View original saved analysis</Link>
            </p>
          )}
        </div>
      )}
      <section
        className="dossier-summary"
        aria-label="Outcome forecasts and evidence coverage"
      >
        {outlook?.forecasts ? (
          <>
            {outlook.forecasts.map((forecast, index) => (
              <section className="dossier-stat" key={forecast.outcome_id}>
                <div>
                  <h3>{forecastNames[forecast.outcome_id]}</h3>
                  <div className="stat-value">
                    —{" "}
                    <span className="horizon-tag">
                      {forecast.horizon_months} months
                    </span>
                  </div>
                  <p>Prediction unavailable</p>
                </div>
                <span className="stat-icon">
                  <Icon
                    name={
                      index === 0 ? "chart" : index === 1 ? "shield" : "finance"
                    }
                  />
                </span>
              </section>
            ))}
          </>
        ) : (
          (profile?.assessment.outcomes ?? []).map((outcome) => (
            <section className="dossier-stat" key={outcome.outcome_id}>
              <div>
                <h3>{outcomeNames[outcome.outcome_id]}</h3>
                <div className="stat-value">
                  — <span className="horizon-tag">Saved assessment</span>
                </div>
                <p>Original outcome · inspect assessment</p>
              </div>
              <span className="stat-icon">
                <Icon name="chart" />
              </span>
            </section>
          ))
        )}
        <section className="dossier-stat">
          <div>
            <h3>
              <MotionButton
                className="dossier-inline-action"
                onClick={() => open({ kind: "sources", index: 0 })}
              >
                Source inventory
              </MotionButton>
            </h3>
            <div className="stat-value">
              {sources.length}
              <span className="stat-unit">
                {" "}
                {standalone ? "excerpts" : "sources"}
              </span>
            </div>
            <p>
              {standalone
                ? `${usable} usable measurement${usable === 1 ? "" : "s"}`
                : `${measurements.size} measurements`}{" "}
              · {standalone || report ? "Research report" : "Saved analysis"}
            </p>
            {standalone && (
              <MotionButton
                className="dossier-inline-action"
                onClick={() => open({ kind: "sources", index: 3 })}
              >
                Evidence mapping
              </MotionButton>
            )}
          </div>
          <span className="stat-icon">
            <Icon name="file" />
          </span>
        </section>
      </section>
      <div className="dossier-section-label">
        <h2>
          BUSINESS FUNDAMENTALS <span>(5 DIMENSIONS)</span>
        </h2>
        <p>
          {decisionLayout
            ? "Open a dimension for its evidence and limitations"
            : "Select a pillar to inspect measurements and model readiness"}
        </p>
        <span className="model-label">
          <Icon name="shield" /> Business outcome models · not trained
        </span>
      </div>
      <div
        className="pillar-mobile-tabs"
        role="group"
        aria-label="Overview dimensions"
      >
        <MotionSelection>
          {groups.map((group, index) => (
            <MotionButton
              key={group.id}
              title={group.name}
              aria-pressed={mobileGroup === index}
              aria-controls={`pillar-${group.id}`}
              id={`overview-tab-${group.id}`}
              onClick={() => setMobileGroup(index)}
            >
              <span aria-hidden="true">0{index + 1}</span>
              <span>
                {
                  ["Adoption", "Attention", "Finance", "Industry", "Team"][
                    index
                  ]
                }
              </span>
              {mobileGroup === index && <MotionIndicator />}
            </MotionButton>
          ))}
        </MotionSelection>
      </div>
      <section className="dossier-pillars" aria-label="Fundamental drivers">
        {groups.map((group, index) => {
          const row = sections.get(group.id);
          const component = modelSections.get(group.id);
          const sdkScore =
            group.id === "adoption_retention" &&
            component?.eligibility === "eligible"
              ? component.score
              : null;
          const sentimentScore =
            group.id === "attention_sentiment" &&
            component?.eligibility === "eligible"
              ? component.score
              : null;
          const ids = row?.metric_observation_ids ?? [];
          const coverage = standalone?.mapping?.dimensions.find(
            (item) => item.group_id === group.id,
          );
          return (
            <article
              key={group.id}
              id={`pillar-${group.id}`}
              className={`pillar-card ${index === mobileGroup ? "mobile-selected" : ""} ${row?.data_status === "insufficient_data" ? "pillar-gap" : ""}`}
            >
              <header>
                <div className="pillar-top">
                  <span>DIMENSION 0{index + 1}</span>
                  {!decisionLayout && (
                    <span className="pillar-model">
                      {group.id === "financial_health" && cashFlowResearch
                        ? "Cash-flow component trained"
                        : sdkScore != null
                          ? "SDK component trained"
                          : sentimentScore != null
                            ? "Sentiment component trained"
                            : "Outcome model untrained"}
                    </span>
                  )}
                </div>
                <h3>
                  <MotionButton
                    className="pillar-expand"
                    aria-label={`Expand dimension: ${group.name}`}
                    aria-haspopup="dialog"
                    aria-controls="company-evidence-drawer"
                    onClick={() => open({ kind: "driver", index })}
                  >
                    {group.name}
                    <Icon name="arrow" />
                  </MotionButton>
                </h3>
                {!decisionLayout && (
                  <p className="pillar-description">{group.description}</p>
                )}
              </header>
              <div
                className="pillar-measurements"
                tabIndex={0}
                role="region"
                aria-label={`${group.name} measurements`}
              >
                {coverage && (
                  <small className="more-metrics">
                    {coverage.status} evidence · {coverage.claim_ids.length}{" "}
                    claims · {coverage.event_ids.length} events
                  </small>
                )}
                {ids.length ? (
                  <dl>
                    {ids.slice(0, 3).map((id) => {
                      const metric = measurements.get(id);
                      return (
                        <div key={id}>
                          <dt title={metric?.label}>
                            {metric?.label ?? "Measurement unavailable"}
                          </dt>
                          <dd title={metric?.value}>
                            {metric?.value ?? "Unavailable"}
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                ) : (
                  <div className="pillar-empty">
                    <span className="pillar-empty-icon">
                      <Icon name={group.icon} />
                    </span>
                    <p>
                      {coverage ? (
                        coverage.claim_ids.length ||
                        coverage.event_ids.length ? (
                          `${coverage.claim_ids.length} attributed claims · ${coverage.event_ids.length} dated events`
                        ) : (
                          "No supported evidence mapped to this dimension."
                        )
                      ) : standalone ? (
                        "Dimension mapping is unavailable for this report. Inspect the source inventory."
                      ) : (
                        <>
                          No verified measurements
                          <br />
                          published for this area.
                        </>
                      )}
                    </p>
                    <span>
                      {coverage?.status === "reported"
                        ? "Reported evidence"
                        : "Evidence gap"}
                    </span>
                  </div>
                )}
                {ids.length > 3 && (
                  <small className="more-metrics">
                    +{ids.length - 3} more in evidence panel
                  </small>
                )}
              </div>
              {!decisionLayout && (
                <div className="pillar-model-note">
                  <span className="micro-label">
                    {sentimentScore != null
                      ? "EXPERIMENTAL TEXT SENTIMENT"
                      : sdkScore != null
                        ? "EXPERIMENTAL SDK FORECAST"
                        : "SPECIALIST OUTLOOK"}
                  </span>
                  <p>
                    {sentimentScore != null
                      ? `Title sentiment index ${sentimentScore.toFixed(1)} / 100`
                      : sdkScore != null
                        ? `SDK demand index ${sdkScore.toFixed(1)} / 100`
                        : "Business prediction unavailable"}
                  </p>
                  <small>
                    {sentimentScore != null
                      ? `${component?.sample_size} retrieved titles; unvalidated financial-news model transfer`
                      : sdkScore != null
                        ? "Trained download forecast; not customer retention or business success"
                        : "Requires training on later company outcomes"}
                  </small>
                </div>
              )}
              <footer>
                <span
                  className={`pillar-status ${row?.data_status === "available" ? "available" : ""}`}
                >
                  <span className="status-dot" />
                  {row ? dataNames[row.data_status] : "Analysis not published"}
                </span>
                <MotionButton
                  aria-label={`Inspect evidence: ${group.name}`}
                  aria-haspopup="dialog"
                  aria-controls="company-evidence-drawer"
                  onClick={() => open({ kind: "driver", index })}
                >
                  Inspect evidence <Icon name="arrow" />
                </MotionButton>
              </footer>
            </article>
          );
        })}
      </section>
      {standalone && (
        <MotionDisclosure
          className="decision-research-details"
          summary="Research findings, citations & continuation"
        >
          <CitedResearchAnalysis report={standalone} />
        </MotionDisclosure>
      )}
      <div className="dossier-ledger">
        <ResearchTools
          path={location.pathname}
          summary={evidenceSummary(profile, standalone, report)}
        />
        <div>
          <Icon name="shield" />
          <strong>EVIDENCE LEDGER</strong>
          <span>
            {sources.length} {standalone ? "excerpts" : "sources"}
          </span>
          <span className="ledger-date">Cutoff {date(cutoff ?? null)}</span>
          <span className="ledger-date">
            {standalone
              ? profile
                ? "Fresh + saved context"
                : "Fresh evidence"
              : report
                ? "Fresh + saved context"
                : "Saved publication"}
          </span>
        </div>
        <MotionButton onClick={() => open({ kind: "sources", index: 0 })}>
          Sources & limitations <Icon name="arrow" />
        </MotionButton>
        {profile && (
          <MotionButton
            className="saved-assessment-action"
            onClick={() => open({ kind: "sources", index: 2 })}
          >
            Saved assessment
          </MotionButton>
        )}
      </div>
      <MotionDialog
        className="driver-dialog dossier-drawer"
        id="company-evidence-drawer"
        ref={dialog}
        aria-labelledby="driver-dialog-title"
        onKeyDown={containFocus}
        onClose={(event) => {
          // Native close can restore focus before this queued callback fires.
          // Do not steal focus if the user has already moved to another control.
          if (
            document.activeElement === document.body ||
            event.currentTarget.contains(document.activeElement)
          ) {
            opener.current?.focus();
          }
        }}
      >
        <header className="driver-dialog-header">
          <div>
            <span className="micro-label">
              {panel.kind === "driver"
                ? `DIMENSION 0${panel.index + 1}`
                : "RESEARCH RECORD"}
            </span>
            <h2 id="driver-dialog-title">
              {panel.kind === "driver"
                ? currentGroup.name
                : "Sources & limitations"}
            </h2>
          </div>
          <MotionButton
            className="secondary"
            autoFocus
            onClick={() => dialog.current?.close()}
            aria-label="Close"
          >
            <Icon name="close" />
          </MotionButton>
        </header>
        <div
          role="tablist"
          aria-label={
            panel.kind === "driver"
              ? "Fundamental drivers"
              : "Evidence sections"
          }
          className="driver-tabs"
          onKeyDown={switchTab}
        >
          <MotionSelection>
            {(panel.kind === "driver"
              ? groups.map((group) => group.name)
              : [
                  "Sources",
                  "Measurements",
                  profile ? "Saved assessment" : "Identity",
                  "Provenance",
                ]
            ).map((name, index) => (
              <MotionButton
                key={name}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                role="tab"
                aria-selected={panel.index === index}
                tabIndex={panel.index === index ? 0 : -1}
                id={`drawer-tab-${index}`}
                aria-controls="driver-panel"
                onClick={() => setPanel({ ...panel, index })}
              >
                {name}
                {panel.index === index && <MotionIndicator />}
              </MotionButton>
            ))}
          </MotionSelection>
        </div>
        <div
          className="driver-panel"
          id="driver-panel"
          role="tabpanel"
          tabIndex={0}
          aria-labelledby={`drawer-tab-${panel.index}`}
        >
          {standalone && (
            <div hidden={panel.kind !== "sources" || panel.index !== 3}>
              <MappingControls key={standalone.report_id} report={standalone} />
            </div>
          )}
          {panel.kind === "driver" ? (
            <>
              <div className="drawer-model-state">
                <Icon name={currentGroup.icon} />
                <div>
                  <strong>
                    {isCashFlowDriver
                      ? "Cash-flow component model trained"
                      : "Business outcome model not trained"}
                  </strong>
                  <p>
                    Data:{" "}
                    {section ? dataNames[section.data_status] : "Not published"}{" "}
                    ·{" "}
                    {isCashFlowDriver
                      ? "Experimental annual cash-flow model"
                      : "Model: no trained company-outcome model"}
                  </p>
                </div>
              </div>
              <p>{currentGroup.description}</p>
              {dimensionModel && (
                <>
                  <h3>Auxiliary proxy experiment</h3>
                  <p>{dimensionModel.architecture}</p>
                  <p>Target: {dimensionModel.target}</p>
                  {dimensionModel.score != null && (
                    <p>
                      {dimensionModel.group_id === "attention_sentiment"
                        ? "Title sentiment index"
                        : "SDK demand percentile"}
                      : {dimensionModel.score.toFixed(1)} / 100. This experiment
                      was not trained on business successes or failures and does
                      not score this business.
                    </p>
                  )}
                  <p>
                    Inputs from source {dimensionModels?.source_snapshot_id} as
                    of {date(dimensionModels?.as_of ?? null)}.{" "}
                    {dimensionModel.group_id === "attention_sentiment"
                      ? `Based on ${dimensionModel.sample_size} distinct retrieved titles. The index is 50 × (1 + mean positive probability − mean negative probability).`
                      : "The index is a percentile of training proxy outcomes."}{" "}
                    It is not a company-success probability.
                  </p>
                  {standalone?.evidence
                    .filter((item) =>
                      dimensionModel.evidence_ids?.includes(item.evidence_id),
                    )
                    .map((item) => (
                      <blockquote key={item.evidence_id}>
                        <p>{item.excerpt}</p>
                        <SourceLink
                          url={
                            eventSourceUrls.get(item.evidence_id) ?? item.url
                          }
                        >
                          Classified source title
                        </SourceLink>
                      </blockquote>
                    ))}
                  {profile?.evidence
                    .filter((item) =>
                      dimensionModel.evidence_ids?.includes(item.evidence_id),
                    )
                    .map((item) => (
                      <blockquote key={item.evidence_id}>
                        <p>{item.assertion}</p>
                        <small>Published {date(item.published_at)}</small>
                        {item.url && (
                          <SourceLink url={item.url}>
                            Classified source title
                          </SourceLink>
                        )}
                      </blockquote>
                    ))}
                  <Reasons reasons={dimensionModel.reason_codes} />
                  <ul>
                    {dimensionModel.limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                </>
              )}
              <Reasons
                reasons={
                  section?.reason_codes.filter(
                    (reason) =>
                      (!isCashFlowDriver ||
                        reason !== "sec_annual_financial_component_only") &&
                      ((!dimensionModel && !isCashFlowDriver) ||
                        reason !== "model_not_trained"),
                  ) ?? ["no_published_group_mapping", "model_not_trained"]
                }
              />
              {standalone && !standalone.mapping && !isCashFlowDriver && (
                <p>
                  This report has no published dimension evidence mapping.{" "}
                  <MotionButton
                    className="secondary"
                    onClick={() => setPanel({ kind: "sources", index: 1 })}
                  >
                    Browse fresh measurements
                  </MotionButton>
                </p>
              )}
              {standalone && currentGroup.id === "financial_health" && (
                <CashFlowResearch
                  sources={standalone.sources}
                  evidence={standalone.evidence}
                />
              )}
              <h3>Observed evidence</h3>
              {renderMeasurements(
                section?.metric_observation_ids ?? [],
                section?.usable_metric_observation_ids ?? [],
              )}
              {standalone?.mapping && (
                <MappedDimensionEvidence
                  report={standalone}
                  group={currentGroup.id}
                />
              )}
            </>
          ) : panel.index === 0 ? (
            <>
              {standalone && <FreshResearchEvidence report={standalone} />}
              <h3>Sources and review status</h3>
              <p>
                Source verification is separate from model confidence. Original
                dates are preserved.
              </p>
              <ul className="dossier-sources">
                {sources.map((source) => (
                  <li key={source.evidence_id}>
                    <div>
                      <strong>{source.provider}</strong>
                      <span>
                        {source.kind.replaceAll("_", " ")} ·{" "}
                        {source.review_state}
                      </span>
                    </div>
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
                  </li>
                ))}
              </ul>
              <h3>Limitations</h3>
              <SyntheticNotice synthetic={synthetic} />
              <Reasons
                reasons={
                  standalone?.limitations ??
                  report?.limitations ??
                  profile?.assessment.limitations ??
                  []
                }
              />
              <p>
                Company-outcome predictions and confidence intervals remain
                unavailable. Experimental dimensions have separate targets and
                limitations.
              </p>
            </>
          ) : panel.index === 1 ? (
            <>
              <h3>All published measurements</h3>
              {renderMeasurements(
                [...measurements.keys()],
                outlook?.specialists.flatMap(
                  (row) => row.usable_metric_observation_ids,
                ) ?? [],
              )}
            </>
          ) : panel.index === 2 ? (
            <>
              <h3>
                {profile ? "Original saved assessment" : "Confirmed identity"}
              </h3>
              {profile && (
                <p>
                  These retain their published outcome definitions and are not
                  aliases for the new forecast targets.
                </p>
              )}
              {!profile && standalone && (
                <>
                  <h3>Confirmed website identity</h3>
                  <p>
                    {standalone.identity.company_name} ·{" "}
                    {standalone.identity.requested_domain} →{" "}
                    {standalone.identity.canonical_domain}
                  </p>
                  <Reasons reasons={standalone.identity.conflicts} />
                  <Reasons reasons={standalone.identity.limitations} />
                  <p>
                    No saved assessment is attached to this standalone report.
                  </p>
                </>
              )}
              {profile && <Outcomes outcomes={profile.assessment.outcomes} />}
              <h3>Evidence, risks and unknowns</h3>
              {(profile?.assessment.statements ?? []).map((statement) => (
                <section key={statement.statement_id}>
                  <h4>{statement.role.replaceAll("_", " ")}</h4>
                  <p>{statement.text}</p>
                  {statement.evidence_ids.length > 0 && (
                    <MotionButton
                      className="secondary"
                      onClick={() => setPanel({ kind: "sources", index: 0 })}
                    >
                      Inspect {statement.evidence_ids.length} supporting
                      source(s)
                    </MotionButton>
                  )}
                </section>
              ))}
              <h3>Company events</h3>
              {profile?.events.length ? (
                profile.events.map((event) => (
                  <section key={event.event_id} className="evidence-event">
                    <h4>
                      {event.occurred_on ?? "Date unknown"} · {event.kind}
                    </h4>
                    <p>{event.description}</p>
                  </section>
                ))
              ) : (
                <p>No dated company events published.</p>
              )}
            </>
          ) : (
            <>
              <h3>Versions and provenance</h3>

              {profile && (
                <PublicationNotice publication={profile.publication} />
              )}
              {profile && <Coverage rows={profile.coverage} />}
              <dl className="metadata">
                {Object.entries({
                  "Source cutoff": date(cutoff ?? null),
                  "Saved source":
                    profile?.publication.source.snapshot_id ??
                    "No saved source",
                  "Saved assessment":
                    profile?.publication.assessment.publication_id ??
                    "No saved assessment",
                  "Source mode":
                    profile?.publication.source.mode ?? "Fresh collection",
                  Report:
                    standalone?.report_id ??
                    report?.report_id ??
                    "Saved analysis",
                  "Grouping policy":
                    outlook?.grouping_policy_version ?? "Not published",
                  "Model status": "Not trained",
                }).map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <Reasons
                reasons={profile?.publication.source.limitations ?? []}
              />
              {(standalone || report) && (
                <Link
                  to={
                    standalone
                      ? "/research/v2/jobs/" + standalone.job_id
                      : `/research/jobs/${encodeURIComponent(report!.job_id)}`
                  }
                >
                  View research status
                </Link>
              )}
            </>
          )}
        </div>
      </MotionDialog>
    </article>
  );
}

function FreshResearchEvidence({ report }: { report: StandaloneReport }) {
  return (
    <>
      <CashFlowResearch sources={report.sources} evidence={report.evidence} />
      <h3>Fresh source coverage</h3>
      <SourceProgress sources={report.sources} />
      <h3>Attributed claims</h3>
      <p>
        Company statements, registry facts and coverage candidates are separate
        from measured platform proxies.
      </p>
      {report.claims.length === 0 && <p>No attributed claims collected.</p>}
      {report.claims.map((claim) => (
        <MotionDisclosure
          key={claim.claim_id}
          summary={
            <>
              {" "}
              {claim.attribution.replaceAll("_", " ")} · {claim.category}{" "}
            </>
          }
        >
          <p>{claim.text}</p>
          <p className="evidence-timestamp">
            Published {claim.published_on ?? "Not supplied"}
          </p>
          {claim.conflicts_with.length > 0 && (
            <p className="notice warning">
              Potential conflicting claims: {claim.conflicts_with.join(", ")}.
              Dates or definitions may differ.
            </p>
          )}
          {claim.evidence_ids.map((id) => {
            const source = report.evidence.find(
              (row) => row.evidence_id === id,
            );
            return source ? (
              <p key={id}>
                <SourceLink url={source.url}>Claim source</SourceLink> ·{" "}
                {source.location} · Collected {date(source.collected_at)}
              </p>
            ) : null;
          })}
        </MotionDisclosure>
      ))}
      <h3>Retrieved events</h3>
      {report.events.map((event) => (
        <MotionDisclosure
          className="evidence-event"
          key={event.event_id}
          summary={
            <>
              {" "}
              {event.kind.replaceAll("_", " ")} · {event.title}{" "}
            </>
          }
        >
          <p className="evidence-timestamp">
            Published {event.published_at ?? "Not supplied"}
          </p>
          <SourceLink url={event.url}>Event source</SourceLink>
        </MotionDisclosure>
      ))}
      <MotionDisclosure
        summary={<>Capture provenance ({report.captures.length})</>}
      >
        {report.captures.map((capture) => (
          <p key={capture.capture_id}>
            <SourceLink url={capture.final_url}>Captured source</SourceLink> ·
            Collected {date(capture.collected_at)} · {capture.parser_version} ·
            SHA-256 {capture.artifact.sha256}
          </p>
        ))}
      </MotionDisclosure>
    </>
  );
}
