import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import { date, modeLabel, QueryState } from "../../components/Common";

const targets: Record<string, string> = {
  downloads_next_30d_v1: "Next 30 days",
  downloads_trailing_28d_at_91d_v1: "Trailing 28 days, 91 days ahead",
};
export const targetLabel = (id: string) => targets[id] ?? id;

/** Select an exact published combination; never silently change a requested batch. */
export default function BatchPicker() {
  const [params, setParams] = useSearchParams();
  const ecosystem = params.get("ecosystem") ?? "npm";
  const target = params.get("target") ?? "downloads_next_30d_v1";
  const query = useQuery({
    queryKey: ["cutoffs"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/cutoffs", { signal })),
  });
  const cutoffs =
    query.data?.items.filter(
      (item) => item.ecosystem === ecosystem && item.target_id === target,
    ) ?? [];
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">Evidence for your next investigation</p>
        <h1>Find the tools worth a closer look.</h1>
        <p>
          Compare published package-download forecasts, build a five-company
          shortlist, and inspect the evidence behind it.
        </p>
      </div>
      <section className="panel">
        <h2>Choose a forecast</h2>
        <div className="filters">
          <label>
            Ecosystem
            <select
              aria-label="Ecosystem"
              value={ecosystem}
              onChange={(e) => setParams({ ecosystem: e.target.value, target })}
            >
              <option value="npm">npm</option>
              <option value="pypi">PyPI</option>
            </select>
          </label>
          <label>
            Forecast target
            <select
              aria-label="Forecast target"
              value={target}
              onChange={(e) => setParams({ ecosystem, target: e.target.value })}
            >
              {Object.entries(targets).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <QueryState
          pending={query.isPending}
          error={query.error}
          retry={() => void query.refetch()}
        />
        {query.data &&
          (cutoffs.length ? (
            <ul className="batch-list">
              {cutoffs.map((item) => (
                <li key={item.batch_id}>
                  <div>
                    <strong>{date(item.decision_at)}</strong>
                    <p>
                      {modeLabel(item.mode)}
                      {item.synthetic ? " · Synthetic test data" : ""}
                    </p>
                  </div>
                  <Link className="button" to={`/batches/${item.batch_id}`}>
                    Open forecast{" "}
                    <span className="sr-only">{item.batch_id}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="notice">
              No published batches for this combination. Choose another
              ecosystem or target.
            </p>
          ))}
      </section>
      <p className="disclaimer">
        Downloads measure package activity. They do not establish users,
        revenue, company quality or investment returns. Ecosystems are evaluated
        separately.
      </p>
    </>
  );
}
