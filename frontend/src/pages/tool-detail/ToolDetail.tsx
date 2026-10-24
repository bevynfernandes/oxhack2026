import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, unwrap, type DTO } from "../../api/client";
import {
  count,
  percent,
  date,
  windowLabel,
  modeLabel,
  QueryState,
  SyntheticNotice,
  Reasons,
  EvidenceList,
  Provenance,
} from "../../components/Common";

const HistoryChart = lazy(() => import("../../components/HistoryChart"));

/** Inspect aggregate estimates and observations bounded by the chosen batch. */
export default function ToolDetail({
  batch,
  catalog,
  toolId,
}: {
  batch: DTO<"ForecastBatch">;
  catalog: DTO<"Catalog">;
  toolId: string;
}) {
  const forecast = batch.results.find((result) => result.tool_id === toolId);
  const tool = catalog.tools.find((item) => item.tool_id === toolId);
  const history = useQuery({
    queryKey: ["history", batch.batch_id, toolId],
    enabled: Boolean(forecast),
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/tools/{tool_id}/history", {
          params: {
            path: { tool_id: toolId },
            query: { batch_id: batch.batch_id, limit: 365 },
          },
          signal,
        }),
      ),
  });
  if (!forecast || !tool)
    return (
      <p role="alert">This tool is not in the selected published batch.</p>
    );
  return (
    <>
      <p>
        <Link to={`/batches/${batch.batch_id}`}>Back to shortlist</Link>
      </p>
      <SyntheticNotice synthetic={batch.provenance.synthetic} />
      <div className="page-heading">
        <p className="eyebrow">
          {tool.organization_name} · {tool.ecosystem} · {tool.package_name}
        </p>
        <h1>{tool.tool_name}</h1>
        <p>
          {modeLabel(batch.mode)} · {forecast.evidence_status} evidence
        </p>
      </div>
      <section className="panel">
        <h2>Aggregate forecast</h2>
        <p>Target: {windowLabel(batch.target_window)}</p>
        <div className="summary-grid">
          <div>
            <span>Forecast downloads</span>
            <strong>{count(forecast.predicted_downloads)}</strong>
          </div>
          <div>
            <span>Reference downloads</span>
            <strong>{count(forecast.reference_downloads)}</strong>
          </div>
          <div>
            <span>Predicted growth</span>
            <strong>{percent(forecast.predicted_growth_pct)}</strong>
          </div>
        </div>
        <p>
          Reference: {windowLabel(batch.reference_window)}. Reporting-lag gap
          ends at {date(batch.decision_at)}.
        </p>
        <p>
          Estimate kind: {forecast.estimate_kind.replaceAll("_", " ")}. Model:{" "}
          {forecast.model_id}.
        </p>
        <p>
          Baseline: {forecast.baseline?.model_id ?? "Unavailable"} ·{" "}
          {count(forecast.baseline?.predicted_downloads)} downloads.
        </p>
        {forecast.interval ? (
          <p>
            Validated aggregate interval: {count(forecast.interval.lower)} to{" "}
            {count(forecast.interval.upper)} downloads. Nominal coverage{" "}
            {percent(forecast.interval.nominal_coverage * 100)}. Method{" "}
            {forecast.interval.method}; calibration{" "}
            {forecast.interval.calibration_id}.
          </p>
        ) : (
          <p className="notice">
            No validated prediction interval is available. This is an
            aggregate-window estimate, not a daily forecast trajectory.
          </p>
        )}
        <Reasons reasons={forecast.reasons} />
        <p>
          Freshness: {forecast.freshness.stale ? "Stale" : "Current"} ·{" "}
          {forecast.freshness.completeness} · as of{" "}
          {date(forecast.freshness.as_of)}
        </p>
        <Reasons reasons={forecast.freshness.reasons ?? []} />
      </section>
      <section className="panel">
        <h2>Observed history</h2>
        <p>
          Observations end at {date(batch.observation_window_end)}. Missing data
          remains unavailable.
        </p>
        <QueryState
          pending={history.isPending}
          error={history.error}
          retry={() => void history.refetch()}
        />
        {history.data &&
          (history.data.points.length ? (
            <>
              <Suspense fallback={<p role="status">Loading chart…</p>}>
                <HistoryChart points={history.data.points} />
              </Suspense>
              <div className="table-scroll">
                <table>
                  <caption>
                    Observed values (accessible chart alternative)
                  </caption>
                  <thead>
                    <tr>
                      <th>Measurement window</th>
                      <th>Downloads</th>
                      <th>Coverage</th>
                      <th>Revision</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.data.points.map((point) => (
                      <tr key={`${point.window.start}-${point.revision_id}`}>
                        <th scope="row">{windowLabel(point.window)}</th>
                        <td>{count(point.downloads)}</td>
                        <td>{point.completeness}</td>
                        <td>{point.revision_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p>No observations were published for this tool and batch.</p>
          ))}
      </section>
      <section className="panel">
        <h2>Evidence and interpretation</h2>
        <EvidenceList evidence={forecast.evidence} />
        <EvidenceList evidence={tool.mapping_evidence} />
      </section>
      <Provenance provenance={batch.provenance} />
    </>
  );
}
