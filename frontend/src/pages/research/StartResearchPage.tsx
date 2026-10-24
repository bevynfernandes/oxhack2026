import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { QueryState } from "../../components/Common";
import { companyDomain } from "../companies/identity";
import { useCompany } from "../companies/shared";
import { researchResult } from "./client";

/** Confirm the exact saved identity before submitting a research write. */
export default function StartResearchPage() {
  const { snapshotId = "", companyId = "" } = useParams();
  const company = useCompany(snapshotId, companyId);
  const [confirmed, setConfirmed] = useState(false);
  useEffect(() => setConfirmed(false), [snapshotId, companyId]);
  const navigate = useNavigate();
  const domain = companyDomain(company.data?.company.website_url ?? null);
  const start = useMutation({
    retry: false,
    mutationFn: async () =>
      researchResult(
        await api.POST("/api/v1/research-jobs", {
          body: {
            assessment_publication_id: snapshotId,
            company_id: companyId,
            domain: domain!,
            identity_confirmed: true,
          },
        }),
      ),
    onSuccess: (job) =>
      navigate("/research/jobs/" + encodeURIComponent(job.job_id)),
  });
  return (
    <article className="research-start">
      <Link to="/">Choose a company</Link>
      <header className="page-heading">
        <p className="eyebrow">NEW RESEARCH</p>
        <h1>Confirm the company</h1>
        <p>Check the name and website before starting a new research job.</p>
      </header>
      <QueryState
        pending={company.isPending}
        error={company.error}
        retry={() => void company.refetch()}
      />
      {company.data && (
        <form
          className="panel"
          onSubmit={(event) => {
            event.preventDefault();
            if (confirmed && domain && !start.isPending) start.mutate();
          }}
        >
          <h2>{company.data.company.display_name}</h2>
          <p>{domain ?? "No supported website recorded"}</p>
          <p>
            Research checks a bounded set of Hacker News links to this exact
            domain. Other measurements remain saved evidence with their original
            dates. Models are not trained; predictions remain unavailable.
          </p>
          <label className="identity-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              disabled={start.isPending || !domain}
            />
            This is the company and website I want to research.
          </label>
          {start.error && (
            <p role="alert" className="notice error">
              {start.error.message}
            </p>
          )}
          <div className="research-actions">
            <button
              type="submit"
              disabled={!confirmed || !domain || start.isPending}
            >
              {start.isPending
                ? "Submitting research…"
                : "Confirm and start research"}
            </button>
            <Link
              to={
                "/companies/" +
                encodeURIComponent(snapshotId) +
                "/" +
                encodeURIComponent(companyId)
              }
            >
              View saved analysis
            </Link>
          </div>
          <p className="disclaimer">
            Known saved companies are supported. An unknown company needs an
            identity match before research can start.
          </p>
        </form>
      )}
    </article>
  );
}
