import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { date, QueryState, Reasons } from "../../components/Common";
import { researchResult } from "./client";

/** Poll durable reads only and stop at terminal states or a read failure. */
export default function ResearchJobPage() {
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
