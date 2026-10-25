import type { fetchStandaloneReport } from "./client";
import { MotionButton } from "../../motion";
import { SourceLink } from "../../components/Common";
import type { EvidenceSummary } from "./summary";

/** Prioritise source-backed signals without inventing a verdict or confidence. */
export default function DecisionBrief({
  report,
  summary,
  onEvidence,
}: {
  report: Awaited<ReturnType<typeof fetchStandaloneReport>>;
  summary: EvidenceSummary;
  onEvidence: () => void;
}) {
  const analysis = report.mapping?.analysis;
  const finding = analysis?.statements.find((row) => row.kind === "finding");
  const findingRecords =
    report.mapping?.records.filter((row) =>
      finding?.mapping_ids.includes(row.mapping_id),
    ) ?? [];
  const findingSource = report.evidence.find((row) =>
    findingRecords.some((record) =>
      record.evidence_ids.includes(row.evidence_id),
    ),
  );
  const conflict = analysis?.statements.find((row) => row.kind === "conflict");
  const gaps = report.outlook.specialists
    .filter((row) => row.data_status === "insufficient_data")
    .map(
      (row) =>
        ({
          adoption_retention: "Adoption & retention",
          attention_sentiment: "Attention & sentiment",
          financial_health: "Financial health",
          industry_competition: "Industry & competition",
          team_execution: "Team & execution",
        })[row.group_id],
    );
  const eligibleModels = report.dimension_models?.dimensions.filter(
    (row) => row.eligibility === "eligible" && row.score != null,
  );
  const experiment =
    eligibleModels?.find((row) => row.group_id === "adoption_retention") ??
    eligibleModels?.find((row) => row.group_id === "attention_sentiment");
  const isSentiment = experiment?.group_id === "attention_sentiment";
  const usable = new Set(
    report.outlook.specialists.flatMap(
      (row) => row.usable_metric_observation_ids,
    ),
  );
  const signal = summary.measurements.find(
    (row) => usable.has(row.id) && row.value !== "Unavailable",
  );
  return (
    <section className="decision-brief" aria-labelledby="decision-brief-title">
      <div className="decision-brief-heading">
        <div>
          <span className="micro-label">THE DECISION BRIEF</span>
          <h2 id="decision-brief-title">What the evidence tells us</h2>
        </div>
        <span className="decision-status">
          {analysis?.state === "unavailable"
            ? "Interpretation unavailable"
            : report.mapping?.state === "partial"
              ? "Partial analysis"
              : "Evidence review"}
        </span>
      </div>
      <div className="decision-brief-grid">
        <section>
          <h3>{finding ? "Research finding" : "Observed signal"}</h3>
          {finding ? (
            <p>{finding.text}</p>
          ) : signal ? (
            <>
              <p className="decision-signal-value">
                {signal.value} <span>{signal.unit.replaceAll("_", " ")}</span>
              </p>
              <p>{signal.definition}</p>
              <small>{signal.period}</small>
            </>
          ) : (
            <p>
              No usable measurement yet. Collected claims alone do not establish
              traction.
            </p>
          )}
          {finding && findingSource ? (
            <SourceLink url={findingSource.url}>
              Read supporting source
            </SourceLink>
          ) : (
            <MotionButton
              className="dossier-inline-action"
              onClick={onEvidence}
            >
              Inspect supporting evidence
            </MotionButton>
          )}
          {finding && (
            <small>
              Source-grounded interpretation, not a validated prediction.
            </small>
          )}
        </section>
        <section>
          <h3>{conflict ? "Needs verification" : "What is still missing"}</h3>
          <p>
            {conflict?.text ??
              (gaps.length
                ? gaps.join(" · ")
                : "Check the source dates, definitions and limitations before drawing a conclusion.")}
          </p>
          <small>
            {conflict
              ? "Conflicting evidence requires review; it is not a prediction of failure."
              : "An evidence gap is not a negative business signal."}
          </small>
        </section>
        <section className="decision-experiment">
          <h3>
            {experiment
              ? isSentiment
                ? "Title sentiment"
                : "SDK demand index"
              : "Before making a decision"}
          </h3>
          {experiment ? (
            <>
              <p className="decision-signal-value">
                {experiment.score!.toFixed(1)} <span>/ 100</span>
              </p>
              <p>
                {isSentiment
                  ? `Experimental index of ${experiment.sample_size ?? "retrieved"} source titles.`
                  : "Experimental next-30-day SDK download forecast percentile."}
              </p>
              <small>
                {isSentiment
                  ? "Not customer sentiment or a company-success score."
                  : "Not customer retention or a company-success score."}
              </small>
            </>
          ) : (
            <p>
              Verify the missing fundamentals with primary sources. This report
              cannot establish whether the company will succeed or fail.
            </p>
          )}
        </section>
      </div>
    </section>
  );
}
