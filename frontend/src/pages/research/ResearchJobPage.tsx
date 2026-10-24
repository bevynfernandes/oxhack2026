import {
  MotionState,
  MotionDisclosure,
  MotionLink as Link,
} from "../../motion";
import { useQuery } from "@tanstack/react-query";
import { useParams, useLocation } from "react-router-dom";
import { api, type DTO } from "../../api/client";
import { date, QueryState, Reasons } from "../../components/Common";
import { researchResult } from "./client";

/** Poll durable reads only and stop at terminal states or a read failure. */
function LegacyResearchJobPage() {
  const { jobId = "" } = useParams();
  const query = useQuery({
    queryKey: ["research-job", jobId],
    queryFn: async () =>
      researchResult(
        await api.GET("/api/v1/research-jobs/{job_id}", {
          params: { path: { job_id: jobId } },
        }),
      ),
    refetchInterval: (query) =>
      query.state.error
        ? false
        : query.state.data &&
            ["queued", "running"].includes(query.state.data.state)
          ? 1500
          : false,
  });
  const job = query.data;
  return (
    <article className="research-start">
      <Link to="/">Choose a company</Link>
      <header className="page-heading">
        <p className="eyebrow">RESEARCH</p>
        <h1>Research status</h1>
      </header>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {job && (
        <section className="panel" aria-label="Research job">
          <p>{job.request.domain}</p>
          <MotionState stateKey={job.state}>
            <h2 role="status">
              {
                {
                  queued: "Queued",
                  running: "Research in progress",
                  partial: "Partial results",
                  completed: "Research complete",
                  failed: "Research failed",
                }[job.state]
              }
            </h2>
          </MotionState>
          <p>
            {
              {
                queued: "Waiting for the local worker.",
                running:
                  "Checking the confirmed domain against the configured sources.",
                partial:
                  "Some source results are incomplete. Read the report with these limits in mind.",
                completed:
                  "The source check finished. Model readiness is shown separately in the report.",
                failed:
                  "Research did not produce a usable report. Return to the saved analysis or explicitly start a new job.",
              }[job.state]
            }
          </p>
          <ul>
            {job.sources.map((source) => (
              <li key={source.provider}>
                Hacker News · {source.state}
                <Reasons reasons={source.reason_codes} />
              </li>
            ))}
          </ul>
          <Reasons reasons={job.reason_codes} />
          <p className="disclaimer">
            Requested {date(job.requested_at)}
            {job.finished_at && " · Finished " + date(job.finished_at)}
          </p>
          <div className="research-actions">
            {job.report_id && (
              <Link
                className="button"
                to={"/research/reports/" + encodeURIComponent(job.report_id)}
              >
                Open research report
              </Link>
            )}
            <Link
              to={
                "/companies/" +
                encodeURIComponent(job.request.assessment_publication_id) +
                "/" +
                encodeURIComponent(job.request.company_id)
              }
            >
              View saved analysis
            </Link>
            {job.state === "failed" && (
              <Link
                to={
                  "/research/new/" +
                  encodeURIComponent(job.request.assessment_publication_id) +
                  "/" +
                  encodeURIComponent(job.request.company_id)
                }
              >
                Confirm a new research job
              </Link>
            )}
          </div>
        </section>
      )}
    </article>
  );
}

export default function ResearchJobPage() {
  const { pathname } = useLocation();
  return pathname.startsWith("/research/v2/") ? (
    <StandaloneJobPage />
  ) : (
    <LegacyResearchJobPage />
  );
}
/** Show backend collector checkpoints without estimating progress. */
export function SourceProgress({ sources }: { sources: DTO<"SourceState">[] }) {
  return (
    <ul className="source-progress">
      {sources.map((source) => (
        <li key={source.provider}>
          <strong>{source.name}</strong>
          <MotionState
            className="source-progress-state"
            stateKey={source.state}
          >
            <span>{source.state}</span>
          </MotionState>
          <Reasons reasons={source.reason_codes} />
          {source.finished_at && (
            <small>Finished {date(source.finished_at)}</small>
          )}
          {(source.evidence.length > 0 || source.observations.length > 0) && (
            <MotionDisclosure
              summary={
                <>
                  {" "}
                  Collected results · {source.observations.length} measurements
                  · {source.evidence.length} excerpts{" "}
                </>
              }
            >
              {source.observations.map((row) => (
                <p key={row.observation_id}>
                  {row.metric_id.replaceAll("_", " ")}:{" "}
                  {row.value == null
                    ? "Unavailable"
                    : row.value.toLocaleString("en-GB")}{" "}
                  {row.unit} {row.missing_reason && " · " + row.missing_reason}
                </p>
              ))}
              {source.evidence.slice(0, 3).map((row) => (
                <blockquote key={row.evidence_id}>{row.excerpt}</blockquote>
              ))}
            </MotionDisclosure>
          )}
        </li>
      ))}
    </ul>
  );
}
function StandaloneJobPage() {
  const { jobId = "" } = useParams();
  const query = useQuery({
    queryKey: ["research-v2-job", jobId],
    queryFn: async () =>
      researchResult(
        await api.GET("/api/v2/research-jobs/{job_id}", {
          params: { path: { job_id: jobId } },
        }),
      ),
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data &&
      ["queued", "running"].includes(query.state.data.state)
        ? 1500
        : false,
  });
  const job = query.data;
  return (
    <article className="research-start">
      <Link to="/">Companies</Link>
      <h1>Research status</h1>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {job && (
        <section className="panel">
          <MotionState stateKey={job.state}>
            <h2 role="status">
              {
                {
                  queued: "Queued",
                  running: "Research in progress",
                  completed: "Research complete",
                  partial: "Partial results",
                  failed: "Research failed",
                }[job.state]
              }
            </h2>
          </MotionState>
          <p>
            Each source reports its own result. A missing or failed source does
            not erase successful results or establish company failure.
          </p>
          <Reasons reasons={job.reason_codes} />
          <SourceProgress sources={job.sources} />
          <div className="research-actions">
            {job.report_id && (
              <Link
                className="button"
                to={"/research/v2/reports/" + job.report_id}
              >
                Open research report
              </Link>
            )}
            <Link to={"/research/identities/" + job.identity_id}>
              {job.state === "failed"
                ? "Review identity and confirm another attempt"
                : "View confirmed identity"}
            </Link>
          </div>
        </section>
      )}
    </article>
  );
}
