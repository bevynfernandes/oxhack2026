import { MotionDisclosure } from "../../motion";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap, type DTO } from "../../api/client";
import { date, Reasons, SyntheticNotice } from "../../components/Common";

export const families = [
  ["traction", "Traction"],
  ["commercial", "Commercial health"],
  ["execution", "Execution"],
  ["market_financing", "Market and financing"],
] as const;

export const outcomeNames = {
  operating_growth_24m_v1: "Operating and growing",
  commercial_viability_12m_v1: "Cash-flow self-sufficiency",
  financing_or_acquisition_24m_v1: "Financing or acquisition",
} as const;

/** Read one exact profile; an unknown identifier never selects another company. */
export function useCompany(snapshot: string, company: string) {
  return useQuery({
    queryKey: ["company", snapshot, company],
    enabled: Boolean(snapshot && company),
    queryFn: async () =>
      unwrap(
        await api.GET(
          "/api/v1/company-snapshots/{snapshot_id}/companies/{company_id}",
          { params: { path: { snapshot_id: snapshot, company_id: company } } },
        ),
      ),
  });
}

/** Retain the publication's actual dates, provenance mode and limitations. */
export function PublicationNotice({
  publication,
}: {
  publication: DTO<"CompanyPublication">;
}) {
  const source = publication.source;
  return (
    <>
      <SyntheticNotice synthetic={source.synthetic} />
      <p className="disclaimer">
        Evidence as of {date(source.as_of)} · Assessment published{" "}
        {date(publication.assessment.recorded_at)}
        {source.mode === "historical_reconstruction" &&
          " · Historical reconstruction: some evidence was collected later"}
      </p>
      <MotionDisclosure summary={<>Snapshot limitations and versions</>}>
        <Reasons reasons={source.limitations} />
        <dl className="metadata">
          <div>
            <dt>Assessment publication</dt>
            <dd>{publication.assessment.publication_id}</dd>
          </div>
          <div>
            <dt>Assessment policy</dt>
            <dd>{publication.assessment.policy_version}</dd>
          </div>
          <div>
            <dt>Source snapshot</dt>
            <dd>{source.snapshot_id}</dd>
          </div>
          <div>
            <dt>Cohort</dt>
            <dd>{source.cohort_version}</dd>
          </div>
          <div>
            <dt>Source mode</dt>
            <dd>{source.mode.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Code revision</dt>
            <dd>{source.code_revision}</dd>
          </div>
          <div>
            <dt>Configuration</dt>
            <dd>{source.configuration_sha256}</dd>
          </div>
        </dl>
      </MotionDisclosure>
    </>
  );
}

/** Describe observed and stale evidence separately from predictive validity. */
export function Coverage({ rows }: { rows: DTO<"PublicCompanyCoverage">[] }) {
  return (
    <ul className="coverage-list">
      {families.map(([family, label]) => {
        const row = rows.find((item) => item.family === family);
        return (
          <li key={family}>
            {label}: {row?.observed_metric_ids.length ?? 0}/
            {row?.applicable_metric_ids.length ?? 0} observed
            {Boolean(row?.stale_metric_ids.length) &&
              `; ${row!.stale_metric_ids.length} stale`}
            {Boolean(row?.conflicting_metric_ids.length) &&
              `; ${row!.conflicting_metric_ids.length} conflicting`}
            {Boolean(row?.inapplicable_metric_ids.length) &&
              `; ${row!.inapplicable_metric_ids.length} not applicable`}
            {Boolean(row?.restricted_metric_ids?.length) &&
              `; ${row!.restricted_metric_ids!.length} restricted`}
          </li>
        );
      })}
    </ul>
  );
}

/** Render C2's separate published outcomes without constructing probabilities. */
export function Outcomes({
  outcomes,
  compact = false,
}: {
  outcomes: DTO<"CompanyOutcomeAssessment">[];
  compact?: boolean;
}) {
  return (
    <div className="outcome-rows">
      {outcomes.map((row) => (
        <section className="outcome-row" key={row.outcome_id}>
          <div>
            {!compact && <h3>{outcomeNames[row.outcome_id]}</h3>}
            <small>Horizon ends {date(row.horizon_end)}</small>
          </div>
          <div>
            <strong>
              {row.assessment_status === "evidence_only"
                ? "Provisional · evidence only"
                : "Assessment unavailable"}
            </strong>
            <p>{row.summary}</p>
            <Reasons reasons={row.reason_codes} />
          </div>
        </section>
      ))}
    </div>
  );
}

/** Format exact decimal strings without conversion to binary floating point. */
export function observationValue(row: DTO<"CompanyMetric">): string {
  if (row.value === null)
    return {
      missing: "Missing",
      conflicting: "Conflicting evidence",
      not_applicable: "Not applicable",
      observed: "Unavailable",
      restricted: "Restricted measurement",
    }[row.state];
  if (row.value.kind === "boolean") return row.value.value ? "Yes" : "No";
  if (row.value.kind === "decimal") return row.value.value;
  return new Intl.NumberFormat("en-GB").format(row.value.value);
}

export function metricPeriod(row: DTO<"CompanyMetric">): string {
  return row.window
    ? `${date(row.window.start)} to ${date(row.window.end)} (end excluded)`
    : date(row.measured_at);
}
