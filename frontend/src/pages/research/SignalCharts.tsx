import type { DTO } from "../../api/client";
import { date } from "../../components/Common";
import { MotionButton, MotionDisclosure } from "../../motion";
import { downloadBars, type DownloadObservation } from "./signalChartData";
import "./signal-charts.css";

const labels = {
  adoption_retention: "Adoption & retention",
  attention_sentiment: "Attention & sentiment",
  financial_health: "Financial health",
  industry_competition: "Industry & competition",
  team_execution: "Team & execution",
};

/** Keep observed quantities, experimental estimates and coverage visually distinct. */
export default function SignalCharts({
  observations,
  models,
  outlook,
  onEvidence,
}: {
  observations: DownloadObservation[];
  models?: DTO<"CompanyDimensionModels"> | null;
  outlook?: Pick<DTO<"StartupOutlook">, "as_of" | "specialists"> | null;
  onEvidence: () => void;
}) {
  const model = models?.dimensions.find(
    (row) => row.group_id === "adoption_retention",
  );
  const bars = downloadBars(observations, model);
  const maximum = Math.max(1, ...bars.map((row) => row.value));
  const estimated = bars.some((row) => row.estimated);
  return (
    <section className="signal-charts" aria-label="Research signal charts">
      <section className="signal-chart" aria-label="SDK download chart">
        <span className="micro-label">OBSERVED ACTIVITY + EXPERIMENT</span>
        <h2>SDK download activity</h2>
        <p>Package downloads, not users, revenue or company-success odds.</p>
        {bars[0]?.definition && (
          <p className="signal-chart-note">{bars[0].definition}</p>
        )}
        {bars.length ? (
          <>
            <div className="signal-chart-scale" aria-hidden="true">
              <span>0 downloads</span>
              <span>{maximum.toLocaleString("en-GB")}</span>
            </div>
            <ol
              className="signal-chart-bars"
              aria-label="Download totals by period"
            >
              {bars.map((row) => (
                <li key={row.label}>
                  <div className="signal-chart-label">
                    <strong>{row.label}</strong>
                    <span>
                      {row.estimated ? "≈ " : ""}
                      {row.value.toLocaleString("en-GB")}
                    </span>
                  </div>
                  <div className="signal-chart-track" aria-hidden="true">
                    <div
                      className={
                        row.estimated
                          ? "signal-chart-fill signal-chart-estimate"
                          : "signal-chart-fill"
                      }
                      style={{ width: `${(row.value / maximum) * 100}%` }}
                    />
                  </div>
                  <small>
                    {date(row.start)} – {date(row.end)} (end excluded)
                  </small>
                </li>
              ))}
            </ol>
            <p className="signal-chart-note">
              Solid: collected totals.{" "}
              {estimated
                ? "Dashed: experimental model estimate; uncertainty interval unavailable."
                : "No eligible estimate for these observations; no forecast drawn."}
            </p>
          </>
        ) : (
          <p className="notice">
            No unambiguous 30-day SDK download series in this report. Inspect
            the evidence for missing, invalid or multiple-package measurements;
            missing data is not zero.
          </p>
        )}
        {estimated && (
          <MotionDisclosure summary={<>How to read this estimate</>}>
            <p>
              {model!.architecture} · Model as of {date(models!.as_of)}. The bar
              converts the published log-growth output back into downloads; it
              is not a new model.
            </p>
            <p>
              The /100 demand index elsewhere is the forecast’s percentile
              against historical training outcomes, not a probability or
              confidence rating.
            </p>
            <ul>
              {model!.limitations.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </MotionDisclosure>
        )}
        <MotionButton className="dossier-inline-action" onClick={onEvidence}>
          Inspect chart evidence
        </MotionButton>
      </section>
      <section className="signal-chart" aria-label="Evidence coverage chart">
        <span className="micro-label">RESEARCH COVERAGE</span>
        <h2>Where the evidence is usable</h2>
        <p>
          Usable measurements out of assigned measurements. Coverage is not
          confidence or a business score.
        </p>
        <ul className="signal-chart-bars">
          {(outlook?.specialists ?? []).map((group) => {
            const assigned = new Set(group.metric_observation_ids);
            const usable = new Set(
              group.usable_metric_observation_ids.filter((id) =>
                assigned.has(id),
              ),
            ).size;
            return (
              <li key={group.group_id}>
                <div className="signal-chart-label">
                  <strong>{labels[group.group_id]}</strong>
                  <span>
                    {usable} / {assigned.size}
                  </span>
                </div>
                <div className="signal-chart-track" aria-hidden="true">
                  <div
                    className="signal-chart-fill"
                    style={{
                      width: `${assigned.size ? (usable / assigned.size) * 100 : 0}%`,
                    }}
                  />
                </div>
                {assigned.size === 0 && <small>No measurements assigned</small>}
              </li>
            );
          })}
        </ul>
        {!outlook?.specialists.length && (
          <p>Evidence coverage has not been published.</p>
        )}
        <p className="signal-chart-note">
          As of {date(outlook?.as_of ?? null)}. Missing evidence does not
          predict failure.
        </p>
      </section>
    </section>
  );
}
