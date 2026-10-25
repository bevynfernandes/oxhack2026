import type { DTO } from "../../api/client";
import { date, SourceLink } from "../../components/Common";
import { MotionDisclosure } from "../../motion";

/** Show the evidenced annual component separately from complete business scores. */
export function CashFlowResearch({
  sources,
  evidence,
}: {
  sources: readonly DTO<"SourceState">[];
  evidence: readonly DTO<"ResearchEvidence">[];
}) {
  const estimates = sources.flatMap((source) =>
    source.cash_flow_research ? [source.cash_flow_research] : [],
  );
  if (!estimates.length) return null;
  return (
    <section className="cash-flow-research" aria-label="Cash-flow research">
      <h3>Experimental cash-flow estimate</h3>
      {estimates.map((estimate) => (
        <article key={`${estimate.issuer_id}-${estimate.accession_number}`}>
          <p>
            <strong>
              {new Intl.NumberFormat("en-GB", {
                style: "percent",
                maximumFractionDigits: 1,
              }).format(estimate.probability)}
            </strong>{" "}
            estimated likelihood of positive operating cash flow in the next
            fiscal-year report, conditional on observed follow-up.
          </p>
          <p className="notice warning">
            Research estimate from a small public-company sample. This component
            does not establish survival, cash runway or the Overall score.
          </p>
          <p className="evidence-timestamp">
            Annual period ended {date(estimate.period_end)} · Filed{" "}
            {date(estimate.filing_date)}
          </p>
          <MotionDisclosure summary={<>Model and supporting filings</>}>
            <p>
              Regularized logistic regression, trained locally. SEC issuer{" "}
              {estimate.issuer_id}; original accession{" "}
              {estimate.accession_number}.
            </p>
            <ul>
              {estimate.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
            {estimate.evidence_ids.map((id) => {
              const source = evidence.find((item) => item.evidence_id === id);
              return source ? (
                <p key={id}>
                  <SourceLink url={source.url}>Supporting source</SourceLink> ·{" "}
                  Collected {date(source.collected_at)}
                </p>
              ) : null;
            })}
            <p>Fitted model SHA-256: {estimate.model_sha256}</p>
            <p>Evaluation SHA-256: {estimate.evaluation_sha256}</p>
          </MotionDisclosure>
        </article>
      ))}
    </section>
  );
}
