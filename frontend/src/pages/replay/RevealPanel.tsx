import { MotionButton } from "../../motion";
import { useMutation } from "@tanstack/react-query";
import { api, unwrap, type DTO } from "../../api/client";
import { count, metricValue, percent, Reasons } from "../../components/Common";
import type { Receipt } from "./selection";

/** Request separate outcomes, preserving the exact submitted selection in each receipt. */
export default function RevealPanel({
  batchId,
  selected,
  allowed,
  informed,
  receipts,
  record,
  name,
}: {
  batchId: string;
  selected: string[];
  allowed: boolean;
  informed: boolean;
  receipts: Receipt[];
  record: (result: DTO<"Reveal">) => void;
  name: (id: string) => string;
}) {
  const mutation = useMutation({
    mutationFn: async (organizationIds: string[]) =>
      unwrap(
        await api.POST("/api/v1/replays/{batch_id}/reveal", {
          params: { path: { batch_id: batchId } },
          body: { organization_ids: organizationIds },
        }),
      ),
    onSuccess: record,
  });
  return (
    <section className="panel" id="replay" aria-labelledby="replay-title">
      <h2 id="replay-title">Historical reveal</h2>
      <p>
        {informed
          ? "You have already revealed this batch. Further selections are informed by those outcomes."
          : "Your current selection is captured when you reveal. Outcomes arrive in a separate request."}
      </p>
      {!allowed && (
        <p className="notice">
          Complete outcomes are not yet available for this batch.
        </p>
      )}
      <MotionButton
        disabled={!allowed || mutation.isPending}
        onClick={() => mutation.mutate([...selected])}
      >
        {mutation.isPending
          ? "Revealing…"
          : informed
            ? "Score a new selection"
            : "Reveal outcomes"}
      </MotionButton>
      {mutation.isError && <p role="alert">{mutation.error.message}</p>}
      {receipts.map((receipt, index) => (
        <article
          className="receipt"
          key={receipt.id}
          aria-label={`Scored selection ${index + 1}`}
        >
          <h3>
            Selection {index + 1} ·{" "}
            {receipt.informed ? "After reveal" : "Before reveal"}
          </h3>
          <p>
            Frozen organizations:{" "}
            {receipt.result.selected_organization_ids.map(name).join(", ") ||
              "None selected"}
          </p>
          <p>Outcome vintage: {receipt.result.outcome_vintage}</p>
          <div className="table-scroll">
            <table>
              <caption>Authoritative shortlist scores</caption>
              <thead>
                <tr>
                  <th>Selection</th>
                  <th>Metric</th>
                  <th>Score</th>
                  <th>Limitation</th>
                </tr>
              </thead>
              <tbody>
                {[
                  receipt.result.selection_score,
                  ...(receipt.result.selection_metrics ?? []),
                  ...receipt.result.comparators,
                ].map((score, i) => (
                  <tr key={i}>
                    <th scope="row">{score.name}</th>
                    <td>{score.metric}</td>
                    <td>{metricValue(score.value)}</td>
                    <td>
                      {score.reason?.replaceAll("_", " ") ?? "None reported"}
                      {score.headline_eligible === false && (
                        <small>
                          Excluded from headline top-five evaluation.
                        </small>
                      )}
                      {score.candidate_universe_id && (
                        <small>
                          Candidate universe: {score.candidate_universe_id}
                        </small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-scroll">
            <table>
              <caption>Mature outcomes and absolute errors</caption>
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Actual downloads</th>
                  <th>Realized growth</th>
                  <th>Model error</th>
                  <th>Baseline error</th>
                  <th>Coverage</th>
                </tr>
              </thead>
              <tbody>
                {receipt.result.outcomes.map((outcome) => (
                  <tr key={outcome.tool_id}>
                    <th scope="row">{name(outcome.tool_id)}</th>
                    <td>{count(outcome.actual_downloads)}</td>
                    <td>{percent(outcome.realized_growth_pct)}</td>
                    <td>{count(outcome.model_absolute_error)}</td>
                    <td>{count(outcome.baseline_absolute_error)}</td>
                    <td>
                      <Reasons reasons={outcome.reasons} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Reasons reasons={receipt.result.limitations} />
        </article>
      ))}
    </section>
  );
}
