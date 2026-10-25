import ResearchLibrary from "../research/ResearchLibrary";
import {
  MotionButton,
  MotionInput,
  MotionSelect,
  MotionLink as Link,
} from "../../motion";
import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import { date, QueryState } from "../../components/Common";
import { Coverage, PublicationNotice } from "./shared";

/** Search a published company set and select up to three exact profiles. */
export default function CompanyListPage() {
  const [urlParams, setParams] = useSearchParams();
  const [params, setPendingParams] = useState(urlParams);
  const snapshot = params.get("snapshot") ?? "";
  const search = (params.get("q") ?? "").slice(0, 120);
  const segment = params.get("segment") ?? "";
  const stage = params.get("stage") ?? "";
  const coverage = params.get("coverage") ?? "";
  const selected = [...new Set(params.getAll("company"))];
  const pendingParams = useRef(params);
  useLayoutEffect(() => {
    pendingParams.current = urlParams;
    setPendingParams(urlParams);
  }, [urlParams]);
  const updateParams = (next: URLSearchParams, replace = false) => {
    pendingParams.current = next;
    setPendingParams(next);
    setParams(next, { replace });
  };
  const choices = useQuery({
    queryKey: ["company-publications"],
    queryFn: async () => unwrap(await api.GET("/api/v1/company-snapshots")),
  });
  const companies = useQuery({
    queryKey: ["companies", snapshot],
    enabled: Boolean(snapshot),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/company-snapshots/{snapshot_id}/companies", {
          params: { path: { snapshot_id: snapshot } },
        }),
      ),
  });
  const rows = companies.data?.items ?? [];
  const visible = rows.filter(({ company, coverage: evidence }) => {
    const applicable = evidence.reduce(
      (sum, row) => sum + row.applicable_metric_ids.length,
      0,
    );
    const observed = evidence.reduce(
      (sum, row) => sum + row.observed_metric_ids.length,
      0,
    );
    const restricted = evidence.some(
      (row) => row.restricted_metric_ids.length > 0,
    );
    return (
      `${company.display_name} ${company.segment}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()) &&
      (!segment || company.segment === segment) &&
      (!stage ||
        (stage === "unknown"
          ? company.stage === null
          : company.stage === stage)) &&
      (!coverage ||
        (coverage === "complete"
          ? applicable > 0 && observed === applicable && !restricted
          : observed < applicable || restricted))
    );
  });
  const setFilter = (name: string, value: string) => {
    const next = new URLSearchParams(pendingParams.current);
    if (value) next.set(name, value);
    else next.delete(name);
    if (name === "snapshot") {
      for (const key of ["company", "segment", "stage", "coverage", "q"])
        next.delete(key);
    }
    updateParams(next, name === "q");
  };
  const toggle = (id: string, checked: boolean) => {
    const next = new URLSearchParams(pendingParams.current);
    const selection = [...new Set(next.getAll("company"))];
    next.delete("company");
    const ids = checked
      ? [...new Set([...selection, id])]
      : selection.filter((key) => key !== id);
    ids.forEach((key) => next.append("company", key));
    updateParams(next);
  };
  const validSelection =
    selected.length >= 2 &&
    selected.length <= 3 &&
    selected.every((id) => rows.some((row) => row.company.company_id === id));
  const comparison = new URLSearchParams({ snapshot });
  selected.forEach((id) => comparison.append("company", id));
  return (
    <>
      <header className="page-heading">
        <p className="eyebrow">RESEARCH WORKSPACE</p>
        <h1>Research library</h1>
        <p>
          Return to startup research you have already opened, or compare the
          evidence for two companies side by side.
        </p>
      </header>
      <ResearchLibrary />
      <h2>Published company cohorts</h2>
      <p>
        These historical dossiers share a published snapshot. Fresh reports
        appear in Your research above after you open them.
      </p>
      <QueryState
        pending={choices.isPending}
        error={choices.error}
        retry={() => void choices.refetch()}
      />
      {choices.data && choices.data.items.length === 0 && (
        <p role="status">No company assessments have been published.</p>
      )}
      {choices.data && (
        <label className="snapshot-picker">
          Assessment snapshot
          <MotionSelect
            value={snapshot}
            onChange={(event) => setFilter("snapshot", event.target.value)}
          >
            <option value="">Choose a published assessment</option>
            {snapshot &&
              !choices.data.items.some(
                (item) => item.assessment.publication_id === snapshot,
              ) && (
                <option value={snapshot}>Unknown snapshot: {snapshot}</option>
              )}
            {choices.data.items.map(({ source, assessment }) => (
              <option
                key={assessment.publication_id}
                value={assessment.publication_id}
              >
                {date(source.as_of)} · {assessment.publication_id}
                {source.synthetic ? " · Synthetic test data" : ""}
              </option>
            ))}
          </MotionSelect>
        </label>
      )}
      {snapshot && (
        <QueryState
          pending={companies.isPending}
          error={companies.error}
          retry={() => void companies.refetch()}
        />
      )}
      {companies.data && (
        <>
          <PublicationNotice publication={companies.data.publication} />
          <div className="filters company-filters">
            <label>
              Search companies
              <MotionInput
                type="search"
                maxLength={120}
                value={search}
                onChange={(event) => setFilter("q", event.target.value)}
              />
            </label>
            <label>
              Segment
              <MotionSelect
                value={segment}
                onChange={(event) => setFilter("segment", event.target.value)}
              >
                <option value="">All segments</option>
                {[...new Set(rows.map((row) => row.company.segment))]
                  .sort()
                  .map((value) => (
                    <option key={value}>{value}</option>
                  ))}
              </MotionSelect>
            </label>
            <label>
              Stage
              <MotionSelect
                value={stage}
                onChange={(event) => setFilter("stage", event.target.value)}
              >
                <option value="">All stages</option>
                <option value="unknown">Unknown</option>
                {[
                  ...new Set(
                    rows.flatMap((row) =>
                      row.company.stage ? [row.company.stage] : [],
                    ),
                  ),
                ]
                  .sort()
                  .map((value) => (
                    <option key={value}>{value}</option>
                  ))}
              </MotionSelect>
            </label>
            <label>
              Evidence coverage
              <MotionSelect
                value={coverage}
                onChange={(event) => setFilter("coverage", event.target.value)}
              >
                <option value="">All coverage</option>
                <option value="complete">
                  All applicable metrics observed
                </option>
                <option value="gaps">Has evidence gaps</option>
              </MotionSelect>
            </label>
          </div>
          <p role="status">
            {visible.length} of {rows.length} companies
          </p>
          <div className="compare-selection" aria-label="Comparison selection">
            <span>{selected.length} of 3 selected</span>
            {validSelection ? (
              <Link className="button" to={`/compare?${comparison}`}>
                Compare selected companies
              </Link>
            ) : (
              <span>Select two or three companies to compare.</span>
            )}
            {selected.length > 0 && (
              <MotionButton
                className="secondary"
                onClick={() => {
                  const next = new URLSearchParams(pendingParams.current);
                  next.delete("company");
                  updateParams(next);
                }}
              >
                Clear selection
              </MotionButton>
            )}
          </div>
          {visible.length === 0 ? (
            <p>No companies match these filters.</p>
          ) : (
            <div
              className="table-scroll"
              role="region"
              aria-label="Company evidence table"
              tabIndex={0}
            >
              <table className="company-table">
                <caption>
                  Published evidence assessments; no validated success
                  probabilities. Coverage counts observations, including stale
                  values.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Compare</th>
                    <th scope="col">Company</th>
                    <th scope="col">Outlook</th>
                    <th scope="col">Supporting evidence</th>
                    <th scope="col">Risk or gap</th>
                    <th scope="col">Evidence coverage</th>
                    <th scope="col">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => (
                    <tr key={row.company.company_id}>
                      <td>
                        <MotionInput
                          type="checkbox"
                          aria-label={`Compare ${row.company.display_name}`}
                          checked={selected.includes(row.company.company_id)}
                          disabled={
                            !selected.includes(row.company.company_id) &&
                            selected.length >= 3
                          }
                          onChange={(event) =>
                            toggle(row.company.company_id, event.target.checked)
                          }
                        />
                      </td>
                      <th scope="row">
                        <Link
                          to={`/companies/${encodeURIComponent(snapshot)}/${encodeURIComponent(row.company.company_id)}`}
                        >
                          {row.company.display_name}
                        </Link>
                        <small>
                          {row.company.segment} ·{" "}
                          {row.company.stage ?? "Stage unknown"} ·{" "}
                          {row.company.business_model ??
                            "Business model unknown"}
                        </small>
                      </th>
                      <td>
                        {row.outcomes.some(
                          (outcome) =>
                            outcome.assessment_status === "evidence_only",
                        )
                          ? "Provisional evidence assessment"
                          : "Assessment unavailable"}
                      </td>
                      <td>
                        {row.supporting_signal ??
                          "No supporting signal published"}
                      </td>
                      <td>{row.main_risk ?? "No risk statement published"}</td>
                      <td>
                        <Coverage rows={row.coverage} />
                      </td>
                      <td>
                        {date(companies.data!.publication.source.recorded_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
