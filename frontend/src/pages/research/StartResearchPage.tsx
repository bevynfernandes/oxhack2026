import {
  MotionState,
  MotionButton,
  MotionInput,
  MotionDisclosure,
  MotionLink as Link,
} from "../../motion";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { QueryState, Reasons, SourceLink } from "../../components/Common";
import { companyDomain } from "../companies/identity";
import { useCompany } from "../companies/shared";
import {
  researchResult,
  fetchIdentity,
  fetchCapabilities,
  confirmIdentity,
} from "./client";

/** Confirm the exact saved identity before submitting a research write. */
function SavedResearchPage() {
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
            <MotionInput
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              disabled={start.isPending || !domain}
            />
            This is the company and website I want to research.
          </label>
          {start.error && (
            <MotionState stateKey={start.error.message}>
              <p role="alert" className="notice error">
                {start.error.message}
              </p>
            </MotionState>
          )}
          <div className="research-actions">
            <MotionButton
              type="submit"
              disabled={!confirmed || !domain || start.isPending}
            >
              {start.isPending
                ? "Submitting research…"
                : "Confirm and start research"}
            </MotionButton>
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

/** Keep legacy saved confirmation links while supporting standalone discovery. */
export default function StartResearchPage() {
  const { snapshotId } = useParams();
  return snapshotId ? <SavedResearchPage /> : <DomainResearchPage />;
}
function DomainResearchPage() {
  const { identityId = "" } = useParams();
  const [search] = useSearchParams();
  const [domain, setDomain] = useState(search.get("domain") ?? "");
  const [confirmed, setConfirmed] = useState(false);
  const navigate = useNavigate();
  useEffect(() => setConfirmed(false), [identityId]);
  const capabilities = useQuery({
    queryKey: ["research-capabilities"],
    queryFn: fetchCapabilities,
  });
  const identity = useQuery({
    queryKey: ["research-identity", identityId],
    enabled: Boolean(identityId),
    queryFn: () => fetchIdentity(identityId),
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data &&
      ["queued", "running"].includes(query.state.data.state)
        ? 1500
        : false,
  });
  const discovery = useMutation({
    retry: false,
    mutationFn: async () =>
      researchResult(
        await api.POST("/api/v2/research-identities", {
          body: {
            domain,
            ...(search.get("company") && search.get("publication")
              ? {
                  company_id: search.get("company")!,
                  assessment_publication_id: search.get("publication")!,
                }
              : {}),
          },
        }),
      ),
    onSuccess: (row) => navigate("/research/identities/" + row.identity_id),
  });
  const start = useMutation({
    retry: false,
    mutationFn: () => confirmIdentity(identityId),
    onSuccess: (job) => navigate("/research/v2/jobs/" + job.job_id),
  });
  const preview = identity.data;
  const enabled =
    capabilities.data?.collection_enabled && capabilities.data.worker_available;
  return (
    <article className="research-start">
      <Link to="/">Choose a company</Link>
      <header className="page-heading">
        <p className="eyebrow">NEW RESEARCH</p>
        <h1>
          {identityId ? "Confirm the company" : "Research a startup domain"}
        </h1>
      </header>
      <QueryState
        pending={capabilities.isPending}
        error={capabilities.error}
        retry={() => void capabilities.refetch()}
      />
      {capabilities.data && !enabled && (
        <p role="alert" className="notice">
          New research is disabled or the worker is unavailable. Existing
          reports remain readable.
        </p>
      )}
      {capabilities.data && (
        <MotionDisclosure summary={<>Research availability</>}>
          <p>
            Browser rendering:{" "}
            {capabilities.data.browser_available
              ? "Available"
              : "Unavailable; some JavaScript pages may be incomplete"}
          </p>
          <ul>
            {capabilities.data.providers.map((row) => (
              <li key={row.provider}>
                {row.provider}: {row.available ? "Configured" : "Unavailable"}
                {row.reason && " · " + row.reason}
              </li>
            ))}
          </ul>
        </MotionDisclosure>
      )}
      {!identityId ? (
        <form
          className="panel"
          onSubmit={(event) => {
            event.preventDefault();
            if (domain.trim() && enabled && !discovery.isPending)
              discovery.mutate();
          }}
        >
          <label>
            Company domain
            <MotionInput
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="posthog.com"
              required
              maxLength={2048}
            />
          </label>
          <p>
            Preview reads the website to identify the company. Full research
            starts only after you confirm the discovered identity and
            destination.
          </p>
          <MotionButton
            disabled={!domain.trim() || !enabled || discovery.isPending}
          >
            {discovery.isPending ? "Requesting preview…" : "Preview company"}
          </MotionButton>
          {discovery.error && (
            <MotionState stateKey={discovery.error.message}>
              <p className="notice error" role="alert">
                {discovery.error.message}
              </p>
            </MotionState>
          )}
        </form>
      ) : (
        <>
          <QueryState
            pending={identity.isPending}
            error={identity.error}
            retry={() => void identity.refetch()}
          />
          {preview && (
            <section className="panel">
              <MotionState stateKey={preview.state}>
                <p role="status">
                  {preview.state === "ready"
                    ? "Identity preview ready"
                    : preview.state === "failed"
                      ? "Identity discovery failed"
                      : preview.state === "running"
                        ? "Discovering company identity"
                        : "Identity discovery queued"}
                </p>
              </MotionState>
              <h2>{preview.company_name}</h2>
              <dl className="metadata">
                <div>
                  <dt>Requested domain</dt>
                  <dd>{preview.requested_domain}</dd>
                </div>
                <div>
                  <dt>Destination to confirm</dt>
                  <dd>{preview.canonical_domain}</dd>
                </div>
              </dl>
              <p>
                This is a discovered website identity, not independent
                verification of legal ownership.
              </p>
              {preview.conflicts.length > 0 && (
                <div className="notice warning">
                  <h3>Identity conflicts</h3>
                  <Reasons reasons={preview.conflicts} />
                </div>
              )}
              <Reasons reasons={preview.limitations} />
              <MotionDisclosure
                summary={<>Identity evidence ({preview.evidence.length})</>}
              >
                {preview.evidence.map((row) => (
                  <section key={row.evidence_id}>
                    <p>{row.excerpt}</p>
                    <SourceLink url={row.url}>Identity source</SourceLink>
                    <p>Collected {row.collected_at}</p>
                  </section>
                ))}
              </MotionDisclosure>
              {preview.state === "ready" && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (confirmed && enabled && !start.isPending)
                      start.mutate();
                  }}
                >
                  <label className="identity-confirm">
                    <MotionInput
                      type="checkbox"
                      checked={confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                      disabled={start.isPending}
                    />
                    I confirm this company, the destination{" "}
                    {preview.canonical_domain}, and the identity conflicts shown
                    above.
                  </label>
                  <MotionButton
                    disabled={!confirmed || !enabled || start.isPending}
                  >
                    {start.isPending
                      ? "Submitting research…"
                      : "Confirm and start research"}
                  </MotionButton>
                  {start.error && (
                    <MotionState stateKey={start.error.message}>
                      <p role="alert" className="notice error">
                        {start.error.message}
                      </p>
                    </MotionState>
                  )}
                </form>
              )}
              {preview.state === "failed" && (
                <Link to="/research/new">Start another identity preview</Link>
              )}
              {preview.saved_context && (
                <Link
                  to={
                    "/companies/" +
                    preview.saved_context.publication.assessment
                      .publication_id +
                    "/" +
                    preview.saved_context.company.company_id
                  }
                >
                  View saved analysis
                </Link>
              )}
            </section>
          )}
        </>
      )}
    </article>
  );
}
