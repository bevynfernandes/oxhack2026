import { useId, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import type { DTO } from "../../api/client";
import { Reasons, SourceLink } from "../../components/Common";
import { MotionButton, MotionSelect, MotionDisclosure } from "../../motion";
import { continueResearch, fetchCapabilities } from "./client";

export type ResearchProfile = DTO<"ResearchSettings">["profile"];
const profiles: ResearchProfile[] = ["fast", "thorough", "deep"];

/** Keep profile choices shared between new research and explicit continuation. */
export function ProfilePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: ResearchProfile;
  onChange: (profile: ResearchProfile) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="research-profile">
      <label htmlFor={id}>Research depth</label>
      <MotionSelect
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => {
          const profile = profiles.find(
            (candidate) => candidate === event.target.value,
          );
          if (profile) onChange(profile);
        }}
      >
        <option value="fast">Fast · up to 5 minutes, 20 company pages</option>
        <option value="thorough">
          Thorough · up to 10 minutes, 60 company pages
        </option>
        <option value="deep">Deep · up to 20 minutes, 120 company pages</option>
      </MotionSelect>
      <small>
        Limits include collection and interpretation. Sources can finish
        earlier.
      </small>
    </div>
  );
}

/** Show measured interpretation work without turning cache hits into model calls. */
export function InterpretationSummary({
  statistics,
  mode,
}: {
  statistics?: DTO<"InterpretationStatistics"> | null;
  mode?: string;
}) {
  if (!statistics)
    return (
      <p>
        {mode === "rules"
          ? "Rule-based mapping only. Gemini did not run for this report."
          : "Detailed interpretation accounting is unavailable for this older report."}
      </p>
    );
  return (
    <section
      className="interpretation-summary"
      aria-label="Interpretation accounting"
    >
      <h3>
        {statistics.mode === "rules"
          ? "Rule-based evidence mapping"
          : "Gemini interpretation"}
      </h3>
      {statistics.mode === "rules" ? (
        <p>Gemini is disabled for this run.</p>
      ) : (
        <>
          <p>
            {statistics.stage.replaceAll("_", " ")} · {statistics.model}
          </p>
          <p>
            {statistics.processed} of {statistics.candidates} evidence blocks
            reviewed · {statistics.deferred} deferred
          </p>
          <p>
            {statistics.provider_requests} new provider requests ·{" "}
            {statistics.cached_batches} cached batches ·{" "}
            {statistics.failed_batches} failed batches
          </p>
          <p>
            {statistics.accepted_proposals} supported proposals ·{" "}
            {statistics.rejected_proposals} rejected proposals
          </p>
          <small>
            Provider-reported tokens:{" "}
            {statistics.input_tokens == null
              ? "input not reported"
              : `${statistics.input_tokens.toLocaleString()} input`}
            ,{" "}
            {statistics.output_tokens == null
              ? "output not reported"
              : `${statistics.output_tokens.toLocaleString()} output`}
            .
          </small>
        </>
      )}
    </section>
  );
}

/** Continue only retained work after an explicit click, creating another report. */
export function ContinueControls({
  jobId,
  reportId,
  sources,
  mapping,
  settings,
}: {
  jobId: string;
  reportId?: string;
  sources: DTO<"SourceState">[];
  mapping?: DTO<"MappingProgress"> | DTO<"MappingBundle"> | null;
  settings?: DTO<"ResearchSettings"> | null;
}) {
  const [profile, setProfile] = useState<ResearchProfile>(
    settings?.profile ?? "thorough",
  );
  const navigate = useNavigate();
  const capabilities = useQuery({
    queryKey: ["research-capabilities"],
    queryFn: fetchCapabilities,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const continuation = useMutation({
    mutationFn: () => continueResearch(jobId, profile, reportId),
    retry: false,
    onSuccess: (job) => navigate(`/research/v2/jobs/${job.job_id}`),
  });
  const remaining = sources.reduce(
    (count, source) => count + (source.details?.frontier.length ?? 0),
    0,
  );
  const cursors = sources.some((source) => source.details?.cursor);
  const failures = sources.some((source) => source.state === "failed");
  const deferred = mapping?.statistics?.deferred ?? 0;
  if (
    !remaining &&
    !cursors &&
    !failures &&
    !deferred &&
    mapping?.state !== "partial"
  )
    return null;
  return (
    <section className="research-continuation" aria-label="Continue research">
      <h3>Continue retained work</h3>
      <p>
        {remaining} queued pages · {deferred} deferred evidence blocks
        {cursors ? " · source pagination remains" : ""}
        {failures ? " · failed providers will be retried" : ""}. Completed
        evidence is retained; this creates a new job and report.
      </p>
      <ProfilePicker
        value={profile}
        onChange={setProfile}
        disabled={continuation.isPending}
      />
      <MotionButton
        className="secondary"
        disabled={
          continuation.isPending ||
          !capabilities.data?.collection_enabled ||
          !capabilities.data.worker_available
        }
        onClick={() => continuation.mutate()}
      >
        {continuation.isPending
          ? "Submitting continuation…"
          : "Continue research"}
      </MotionButton>
      {continuation.error && <p role="alert">{continuation.error.message}</p>}
    </section>
  );
}

/** Present findings beside the original cited evidence and explicit analysis gaps. */
export function CitedResearchAnalysis({
  report,
}: {
  report: Pick<
    DTO<"Report">,
    | "mapping"
    | "evidence"
    | "job_id"
    | "report_id"
    | "sources"
    | "settings"
    | "derived_from_report_id"
  >;
}) {
  const mapping = report.mapping;
  const analysis = mapping?.analysis;
  const records = new Map(mapping?.records.map((row) => [row.mapping_id, row]));
  const evidence = new Map(
    report.evidence.map((row) => [row.evidence_id, row]),
  );
  return (
    <section
      className="panel research-analysis"
      aria-label="Grounded research analysis"
    >
      <h2>Evidence findings</h2>
      <MotionDisclosure
        summary={
          <>
            Gemini analysis and citations · {analysis?.statements.length ?? 0}{" "}
            findings
          </>
        }
      >
        <InterpretationSummary
          statistics={mapping?.statistics}
          mode={mapping?.mode}
        />
        {analysis?.statements.map((statement, index) => (
          <section key={index}>
            <h3>
              {statement.kind === "finding"
                ? "Finding"
                : statement.kind === "conflict"
                  ? "Conflicting evidence"
                  : "Evidence gap"}{" "}
              · {statement.group_id.replaceAll("_", " ")}
            </h3>
            <p>{statement.text}</p>
            {statement.mapping_ids.map((id) => {
              const record = records.get(id);
              if (!record) return null;
              return (
                <div key={id}>
                  <small>
                    {record.attribution.replaceAll("_", " ")} ·{" "}
                    {record.subject_name}
                  </small>
                  {record.quotes.slice(0, 1).map((quote) => (
                    <blockquote key={quote.evidence_id}>
                      {quote.exact}
                    </blockquote>
                  ))}
                  {record.evidence_ids.slice(0, 2).map((evidenceId) => {
                    const source = evidence.get(evidenceId);
                    return (
                      source && (
                        <p key={evidenceId}>
                          <SourceLink url={source.url}>
                            Read supporting source
                          </SourceLink>{" "}
                          · Collected {source.collected_at}
                        </p>
                      )
                    );
                  })}
                </div>
              );
            })}
          </section>
        ))}
        {!analysis?.statements.length && (
          <p>
            No model-written findings are available. The collected evidence and
            rule mappings remain available in the source details.
          </p>
        )}
        {analysis && <Reasons reasons={analysis.reason_codes} />}
        <p>
          Missing financials, retention and competitor evidence remain gaps. No
          numerical growth, survival or financial forecast is inferred.
        </p>
      </MotionDisclosure>
      {report.derived_from_report_id && (
        <p>
          Continues an earlier report. Retained sources keep their original
          collection dates.
        </p>
      )}
      <ContinueControls
        jobId={report.job_id}
        reportId={report.report_id}
        sources={report.sources}
        mapping={mapping}
        settings={report.settings}
      />
    </section>
  );
}
