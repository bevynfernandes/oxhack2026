import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, unwrap, type DTO } from "../../api/client";
import {
  count,
  percent,
  date,
  modeLabel,
  windowLabel,
  QueryState,
  SyntheticNotice,
  Reasons,
  Provenance,
} from "../../components/Common";
import RevealPanel from "../replay/RevealPanel";
import { useSelection } from "../replay/selection";
import ToolDetail from "../tool-detail/ToolDetail";
import { targetLabel } from "./BatchPicker";

/** Cache only the immutable batch and matching published catalogue/rankings. */
export function useBatch(batchId: string) {
  return useQuery({
    queryKey: ["batch", batchId],
    queryFn: async ({ signal }) => {
      const [forecast, rankings, catalog] = await Promise.all([
        api.GET("/api/v1/forecasts/{batch_id}", {
          params: { path: { batch_id: batchId } },
          signal,
        }),
        api.GET("/api/v1/rankings/{batch_id}", {
          params: { path: { batch_id: batchId } },
          signal,
        }),
        api.GET("/api/v1/catalog", {
          params: { query: { batch_id: batchId } },
          signal,
        }),
      ]);
      return {
        batch: unwrap(forecast),
        rankings: unwrap(rankings),
        catalog: unwrap(catalog),
      };
    },
  });
}

export default function BatchPage() {
  const { batchId = "", toolId } = useParams();
  const query = useBatch(batchId);
  return (
    <>
      <Link to="/">Choose another forecast</Link>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data &&
        (toolId ? (
          <ToolDetail {...query.data} toolId={toolId} />
        ) : (
          <RankingsWorkspace key={batchId} {...query.data} />
        ))}
    </>
  );
}

function RankingsWorkspace({
  batch,
  rankings,
  catalog,
}: {
  batch: DTO<"ForecastBatch">;
  rankings: DTO<"Rankings">;
  catalog: DTO<"Catalog">;
}) {
  const tools = new Map(catalog.tools.map((tool) => [tool.tool_id, tool]));
  const forecasts = new Map(
    batch.results.map((result) => [result.tool_id, result]),
  );
  const organizations = new Map(
    catalog.tools.map((tool) => [tool.organization_id, tool.organization_name]),
  );
  const name = (id: string) =>
    tools.get(id)?.tool_name ?? organizations.get(id) ?? id;
  const eligible = rankings.primary.tool_ids.map(
    (id) => forecasts.get(id)!.organization_id,
  );
  const defaults = rankings.recommended_tool_ids.map(
    (id) => forecasts.get(id)!.organization_id,
  );
  const selection = useSelection(batch.batch_id, eligible, defaults);
  const ranked = new Set(rankings.primary.tool_ids);
  const ordered = [
    ...rankings.primary.tool_ids,
    ...batch.results
      .filter((item) => !ranked.has(item.tool_id))
      .map((item) => item.tool_id),
  ];
  const toggle = (id: string) =>
    selection.select(
      selection.selected.includes(id)
        ? selection.selected.filter((value) => value !== id)
        : [...selection.selected, id],
    );
  return (
    <>
      <SyntheticNotice synthetic={batch.provenance.synthetic} />
      <div className="page-heading">
        <p className="eyebrow">
          {batch.ecosystem} · {targetLabel(batch.target_id)}
        </p>
        <h1>Your scouting shortlist</h1>
        <p>
          {modeLabel(batch.mode)} · decision {date(batch.decision_at)}
        </p>
      </div>
      <div className="summary-grid">
        <div>
          <span>Observation boundary</span>
          <strong>{date(batch.observation_window_end)}</strong>
        </div>
        <div>
          <span>Forecast window</span>
          <strong>{windowLabel(batch.target_window)}</strong>
        </div>
        <div>
          <span>Your selection</span>
          <strong>{selection.selected.length} of 5 organizations</strong>
        </div>
      </div>
      <p>
        Reference window: {windowLabel(batch.reference_window)}. There is a
        reporting-lag gap before the forecast window.
      </p>
      {catalog.tools.some(
        (tool) => tool.mapping_verification === "retrospective",
      ) && (
        <p className="notice">
          Some identities were verified retrospectively. Inspect the tool's
          mapping dates and cohort limitations before interpreting this
          reconstruction.
        </p>
      )}
      <Reasons reasons={catalog.limitations ?? []} />
      <section className="panel">
        <div className="section-heading">
          <h2>Published growth ranking</h2>
          <a href="#replay">Go to reveal</a>
        </div>
        <p>
          Recommended:{" "}
          {rankings.recommended_tool_ids.map(name).join(", ") ||
            "No eligible recommendations"}
          .
        </p>
        {rankings.shortfall_reason && (
          <p className="notice">{rankings.shortfall_reason}</p>
        )}
        <button
          className="secondary"
          onClick={() => selection.select(defaults)}
        >
          Use published recommendation
        </button>
        {selection.storageWarning && (
          <p role="status">
            Browser storage is unavailable. Keep this tab open to retain your
            selection.
          </p>
        )}
        <div className="table-scroll">
          <table>
            <caption>
              Organization representatives, in the published order
            </caption>
            <thead>
              <tr>
                <th>Select</th>
                <th>Organization / tool</th>
                <th>Reference downloads</th>
                <th>Forecast downloads</th>
                <th>Predicted growth</th>
                <th>Baseline downloads</th>
                <th>Evidence / freshness</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((id) => {
                const result = forecasts.get(id)!;
                const tool = tools.get(id);
                const checked = selection.selected.includes(
                  result.organization_id,
                );
                return (
                  <tr key={id}>
                    <td>
                      <input
                        aria-label={`Select ${tool?.organization_name ?? result.organization_id}`}
                        type="checkbox"
                        checked={checked}
                        disabled={
                          !ranked.has(id) ||
                          (!checked && selection.selected.length >= 5)
                        }
                        onChange={() => toggle(result.organization_id)}
                      />
                    </td>
                    <th scope="row">
                      <Link to={`/batches/${batch.batch_id}/tools/${id}`}>
                        {tool?.tool_name ?? id}
                      </Link>
                      <small>
                        {tool?.organization_name}
                        <br />
                        {tool?.package_name}
                      </small>
                      <Reasons reasons={result.reasons} />
                    </th>
                    <td>{count(result.reference_downloads)}</td>
                    <td>
                      {count(result.predicted_downloads)}
                      <small>
                        {result.availability} ·{" "}
                        {result.estimate_kind.replaceAll("_", " ")}
                      </small>
                    </td>
                    <td>{percent(result.predicted_growth_pct)}</td>
                    <td>
                      {count(result.baseline?.predicted_downloads)}
                      <small>
                        {result.baseline?.model_id ?? "No comparator"}
                      </small>
                    </td>
                    <td>
                      {result.evidence_status}
                      <small>
                        {result.freshness.stale ? "Stale" : "Current"} ·{" "}
                        {result.freshness.completeness}
                      </small>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {rankings.exclusions.length > 0 && (
          <details>
            <summary>
              Excluded from growth ranking ({rankings.exclusions.length})
            </summary>
            {rankings.exclusions.map((item) => (
              <div key={item.tool_id}>
                <strong>{name(item.tool_id)}</strong>
                <Reasons reasons={item.reasons} />
              </div>
            ))}
          </details>
        )}
        <details>
          <summary>Baseline rankings</summary>
          {rankings.baselines.map((ranking) => (
            <div key={ranking.name}>
              <h3>{ranking.name}</h3>
              <ol>
                {ranking.tool_ids.map((id) => (
                  <li key={id}>{name(id)}</li>
                ))}
              </ol>
            </div>
          ))}
        </details>
      </section>
      <RevealPanel
        batchId={batch.batch_id}
        selected={selection.selected}
        allowed={rankings.reveal_allowed}
        informed={selection.revealed}
        receipts={selection.receipts}
        record={selection.record}
        name={name}
      />
      {batch.evaluation_id && (
        <p>
          <Link to={`/evaluations/${batch.evaluation_id}`}>
            Inspect evaluation and baseline comparisons
          </Link>
        </p>
      )}
      <Provenance provenance={batch.provenance} />
    </>
  );
}
