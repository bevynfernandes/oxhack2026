import type { fetchStandaloneReport, fetchResearchReport } from "./client";
import type { useCompany } from "../companies/shared";
import { metricPeriod, observationValue } from "../companies/shared";
import { date } from "../../components/Common";

type Profile = NonNullable<ReturnType<typeof useCompany>["data"]>;
export type EvidenceSummary = {
  name: string;
  domain: string;
  asOf: string | null;
  context: string;
  coverage: string;
  supporting: string;
  risk: string;
  gaps: string[];
  limitations: string[];
  synthetic: boolean;
  measurements: {
    id: string;
    label: string;
    value: string;
    unit: string;
    definition: string;
    period: string;
    collected: string | null;
  }[];
};
/** Describe source data without ranking companies, estimating probabilities or harmonising unlike metrics. */
export function evidenceSummary(
  profile?: Profile,
  report?: Awaited<ReturnType<typeof fetchStandaloneReport>>,
  legacy?: Awaited<ReturnType<typeof fetchResearchReport>>,
): EvidenceSummary {
  const sourceProfile =
    report?.identity.saved_context ??
    legacy?.inventory.saved_context ??
    profile;
  const outlook = report?.outlook ?? legacy?.outlook ?? sourceProfile?.outlook;
  const groups = outlook?.specialists ?? [];
  const usable = new Set(
    groups.flatMap((row) => row.usable_metric_observation_ids),
  );
  const assigned = new Set(groups.flatMap((row) => row.metric_observation_ids));
  const definitions = new Map(
    sourceProfile?.definitions.map((row) => [row.metric_id, row]),
  );
  const observations = report?.observations ?? legacy?.inventory.observations;
  const freshMeasurements = (observations ?? []).map((row) => ({
    id: row.observation_id,
    label: row.metric_id.replaceAll("_", " "),
    value:
      row.value == null ? "Unavailable" : row.value.toLocaleString("en-GB"),
    unit: row.unit,
    definition: row.definition,
    period: row.window
      ? `${date(row.window.start)} to ${date(row.window.end)} (end excluded)`
      : "Period not recorded",
    collected: row.collected_at,
  }));
  const savedMeasurements = (sourceProfile?.metrics ?? []).map((row) => ({
    id: row.observation_id,
    label: definitions.get(row.metric_id)?.label ?? row.metric_id,
    value: observationValue(row),
    unit: definitions.get(row.metric_id)?.unit ?? "",
    definition:
      definitions.get(row.metric_id)?.definition ?? "Definition unavailable",
    period: metricPeriod(row),
    collected: row.collected_at,
  }));
  const measurements = report
    ? freshMeasurements
    : legacy
      ? [
          ...freshMeasurements,
          ...savedMeasurements.filter(
            (row) => !freshMeasurements.some((fresh) => fresh.id === row.id),
          ),
        ]
      : savedMeasurements;
  const supporting = measurements.find((row) => usable.has(row.id));
  const gaps = groups
    .filter((row) => row.data_status === "insufficient_data")
    .map((row) => row.group_id.replaceAll("_", " "));
  return {
    name:
      report?.identity.company_name ??
      sourceProfile?.company.display_name ??
      "Company",
    domain:
      report?.identity.canonical_domain ??
      sourceProfile?.company.website_url ??
      "Website unknown",
    asOf:
      report?.researched_at ??
      legacy?.researched_at ??
      sourceProfile?.assessment.as_of ??
      null,
    context: sourceProfile
      ? [
          sourceProfile.company.segment,
          sourceProfile.company.stage ?? "Stage unknown",
          sourceProfile.company.business_model ?? "Business model unknown",
        ].join(" · ")
      : "Sector, stage and business model not independently established",
    coverage: `${usable.size} of ${assigned.size} assigned measurements usable; this is coverage, not confidence`,
    supporting: supporting
      ? `${supporting.label}: ${supporting.value} ${supporting.unit}. ${supporting.period}. This is an observed signal, not a ranked predictor of success.`
      : "No usable supporting measurement is published. Source excerpts alone do not establish traction.",
    risk: "Largest business risk is not established by a validated model. Missing evidence is a research limitation, not evidence of failure.",
    gaps,
    limitations:
      report?.limitations ??
      legacy?.limitations ??
      sourceProfile?.publication.source.limitations ??
      [],
    synthetic:
      sourceProfile?.publication.source.synthetic ??
      report?.outlook.synthetic ??
      false,
    measurements,
  };
}
