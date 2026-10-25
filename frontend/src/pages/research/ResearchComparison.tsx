import { useQueries } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import { date, QueryState, SyntheticNotice } from "../../components/Common";
import { MotionDisclosure, MotionLink as Link } from "../../motion";
import { fetchResearchReport, fetchStandaloneReport } from "./client";
import { researchKind } from "./library";
import { evidenceSummary } from "./summary";

/** Fetch each exact immutable resource independently; never turn it into another cohort. */
export async function fetchComparisonRecord(path: string) {
  const kind = researchKind(path);
  if (kind === "saved") {
    const [, , snapshot, company] = path.split("/");
    return evidenceSummary(
      unwrap(
        await api.GET(
          "/api/v1/company-snapshots/{snapshot_id}/companies/{company_id}",
          { params: { path: { snapshot_id: snapshot, company_id: company } } },
        ),
      ),
    );
  }
  if (kind === "report") {
    const id = path.split("/").at(-1)!;
    return path.startsWith("/research/v2/")
      ? evidenceSummary(undefined, await fetchStandaloneReport(id))
      : evidenceSummary(undefined, undefined, await fetchResearchReport(id));
  }
  throw new Error("Choose a saved dossier or completed report to compare.");
}
/** Compare evidence records with explicit vintage/definition differences and no winner. */
export default function ResearchComparison() {
  const [params] = useSearchParams();
  const paths = params.getAll("record");
  const valid =
    paths.length >= 2 &&
    paths.length <= 3 &&
    new Set(paths).size === paths.length &&
    paths.every((path) =>
      ["report", "saved"].includes(researchKind(path) ?? ""),
    );
  const queries = useQueries({
    queries: (valid ? paths : []).map((path) => ({
      queryKey: ["research-comparison", path],
      queryFn: () => fetchComparisonRecord(path),
      retry: false,
    })),
  });
  const ready = valid && queries.every((query) => query.data && !query.error);
  return (
    <>
      <Link to="/explore">Change research selection</Link>
      <header className="page-heading">
        <h1>Compare research evidence</h1>
        <p>
          Compare fresh reports and published dossiers without treating
          different collection dates or metric definitions as equivalent.
        </p>
      </header>
      <p className="notice">
        No validated success probabilities, ranked winner or inferred peer
        suitability. Excerpts and experimental proxy estimates are not verified
        commercial outcomes.
      </p>
      {!valid ? (
        <p role="alert">
          Choose two or three distinct dossiers from Your research. Research
          jobs cannot be compared before a report exists.
        </p>
      ) : (
        <QueryState
          pending={
            !queries.some((query) => query.error) &&
            queries.some((query) => query.isPending)
          }
          error={queries.find((query) => query.error)?.error ?? null}
          retry={() => {
            void Promise.all(queries.map((query) => query.refetch()));
          }}
        />
      )}
      {ready && (
        <div
          className="research-comparison"
          role="region"
          aria-label="Research evidence comparison"
        >
          {queries.map((query, index) => {
            const row = query.data!;
            return (
              <article className="panel" key={paths[index]}>
                <h2>
                  <Link to={paths[index]}>{row.name}</Link>
                </h2>
                <SyntheticNotice synthetic={row.synthetic} />
                <p>{row.domain}</p>
                <p>{row.context}</p>
                <p>Research date: {date(row.asOf)}</p>
                <p>
                  <strong>Prediction unavailable</strong>
                </p>
                <p>{row.coverage}</p>
                <h3>Supporting evidence</h3>
                <p>{row.supporting}</p>
                <h3>Risk and gaps</h3>
                <p>{row.risk}</p>
                <p>
                  {row.gaps.join(", ") ||
                    "Inspect source-specific limitations."}
                </p>
                <MotionDisclosure
                  summary={<>Measurements ({row.measurements.length})</>}
                >
                  <dl>
                    {row.measurements.map((metric) => (
                      <div key={metric.id}>
                        <dt>{metric.label}</dt>
                        <dd>
                          {metric.value} {metric.unit}
                          <p>{metric.definition}</p>
                          <small>
                            {metric.period} · Collected {date(metric.collected)}
                          </small>
                        </dd>
                      </div>
                    ))}
                  </dl>
                </MotionDisclosure>
                <MotionDisclosure summary={<>Report limitations</>}>
                  <ul>
                    {row.limitations.map((limit, i) => (
                      <li key={i}>{limit}</li>
                    ))}
                  </ul>
                </MotionDisclosure>
                <Link to={paths[index] + "#sources"}>
                  Inspect original sources and dates
                </Link>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
