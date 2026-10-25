import { InterpretationSummary } from "./ResearchWorkflow";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { DTO } from "../../api/client";
import { date, Reasons, SourceLink } from "../../components/Common";
import CompanySpinner from "../../components/CompanySpinner";
import {
  MotionButton,
  MotionInput,
  MotionDisclosure,
  MotionLink as Link,
} from "../../motion";
import {
  createMappingJob,
  fetchCapabilities,
  fetchMappingJob,
  type fetchStandaloneReport,
} from "./client";

type Report = Awaited<ReturnType<typeof fetchStandaloneReport>>;
type Group = DTO<"SpecialistOutlook">["group_id"];

/** A new interpretation is an explicit write; source collection dates stay frozen. */
export function MappingControls({ report }: { report: Report }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [reuseCache, setReuseCache] = useState(true);
  const capabilities = useQuery({
    queryKey: ["research-capabilities"],
    queryFn: fetchCapabilities,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const create = useMutation({
    mutationFn: () =>
      createMappingJob(report.report_id, reuseCache ? "reuse" : "bypass"),
    retry: false,
    onSuccess: (job) => setJobId(job.job_id),
  });
  const status = useQuery({
    queryKey: ["evidence-mapping-job", jobId],
    queryFn: () => fetchMappingJob(jobId!),
    enabled: jobId !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      !query.state.error &&
      ["pending", "running"].includes(query.state.data?.progress?.state ?? "")
        ? 1000
        : false,
  });
  const job = status.data;
  const active =
    create.isPending ||
    (!!jobId &&
      (!job ||
        ["pending", "running"].includes(job.progress?.state ?? "pending")));
  return (
    <section
      className="evidence-mapping-controls"
      aria-label="Evidence mapping"
    >
      <p>
        {report.mapping
          ? `Evidence mapped ${date(report.mapping.mapped_at)} · ${report.mapping.state}`
          : "This report has no dimension evidence mapping yet."}
        {report.mapping?.model && <> · {report.mapping.model}</>}
      </p>
      <label>
        <MotionInput
          type="checkbox"
          checked={reuseCache}
          disabled={active}
          onChange={(event) => setReuseCache(event.target.checked)}
        />{" "}
        Reuse unchanged interpretation from cache
      </label>
      <MotionButton
        className="secondary"
        disabled={active || !capabilities.data?.mapping?.enabled}
        onClick={() => create.mutate()}
      >
        {active ? (
          <span className="loading-label">
            <CompanySpinner
              size="small"
              website={report.identity.canonical_domain}
            />
            Mapping evidence…
          </span>
        ) : (
          "Re-map captured evidence"
        )}
      </MotionButton>
      <small>
        Uses retained sources and creates a new report. To collect newer
        sources, use Refresh research.
      </small>
      {job && (
        <p role="status">
          Mapping {job.progress?.state ?? "pending"} ·{" "}
          {job.progress?.completed_batches ?? 0} batches processed
        </p>
      )}
      {job && <InterpretationSummary statistics={job.progress?.statistics} />}
      {job && <Reasons reasons={job.progress?.reason_codes ?? []} />}
      {report.mapping && (
        <Reasons reasons={report.mapping.reason_codes ?? []} />
      )}
      {job?.report_id && (
        <Link to={`/research/v2/reports/${job.report_id}`}>
          Open newly mapped report
        </Link>
      )}
      {(create.error || status.error) && (
        <p role="alert">{(create.error ?? status.error)?.message}</p>
      )}
      {status.error && (
        <MotionButton
          className="secondary"
          onClick={() => void status.refetch()}
        >
          Retry mapping status read
        </MotionButton>
      )}
      {!capabilities.isPending && !capabilities.data?.mapping?.enabled && (
        <small>
          Evidence mapping is unavailable; stored evidence remains readable.
        </small>
      )}
    </section>
  );
}

/** Show backend assignments, original quotes and attribution without scoring claims. */
export function MappedDimensionEvidence({
  report,
  group,
}: {
  report: Report;
  group: Group;
}) {
  const rows =
    report.mapping?.records.filter(
      (row) => row.group_id === group && row.record_type !== "observation",
    ) ?? [];
  const support = new Map(report.evidence.map((row) => [row.evidence_id, row]));
  const claims = new Map(report.claims.map((row) => [row.claim_id, row]));
  const events = new Map(report.events.map((row) => [row.event_id, row]));
  return (
    <section aria-label="Mapped claims and events">
      <h3>Attributed claims and events</h3>
      <p>
        Statements retain their source and subject; they are not verified
        business outcomes.
      </p>
      {!rows.length && (
        <p>No supported claims or events mapped to this dimension.</p>
      )}
      {rows.map((row) => {
        const claim = claims.get(row.record_id);
        const event = events.get(row.record_id);
        return (
          <MotionDisclosure
            key={row.mapping_id}
            summary={`${row.concept.replaceAll("_", " ")} · ${row.subject.replaceAll("_", " ")}`}
          >
            <p>
              {row.attribution.replaceAll("_", " ")} · {row.subject_name}
            </p>
            {row.quotes.map((quote) => (
              <blockquote key={quote.evidence_id} lang={row.language}>
                {quote.exact}
              </blockquote>
            ))}
            {!row.quotes.length && <p>{claim?.text ?? event?.title}</p>}
            <p>Published {row.published_on ?? "Date not supplied"}</p>
            {row.numerical_context && (
              <p>
                Attributed quantity: {row.numerical_context.value_decimal}{" "}
                {row.numerical_context.currency ?? row.numerical_context.unit}
                {" · "}
                {row.qualifier.replaceAll("_", " ")}
                {" · "}
                {row.numerical_context.measurement_start
                  ? `${row.numerical_context.measurement_start} to ${row.numerical_context.measurement_end}`
                  : (row.numerical_context.measurement_instant ??
                    "Measurement period not supplied")}
              </p>
            )}
            {!!claim?.conflicts_with.length && (
              <p>
                Conflicting claims retained: {claim.conflicts_with.join(", ")}
              </p>
            )}
            {row.evidence_ids.map((id) => {
              const evidence = support.get(id);
              return (
                evidence && (
                  <p key={id}>
                    <SourceLink url={evidence.url}>Read source</SourceLink>
                    {" · "}Collected {date(evidence.collected_at)}
                  </p>
                )
              );
            })}
            <Reasons reasons={row.reason_codes} />
          </MotionDisclosure>
        );
      })}
    </section>
  );
}
