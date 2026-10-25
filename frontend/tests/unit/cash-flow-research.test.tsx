import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { DTO } from "../../src/api/client";
import { CashFlowResearch } from "../../src/pages/research/CashFlowResearch";

const source: DTO<"SourceState"> = {
  provider: "sec",
  name: "SEC",
  state: "partial",
  captures: [],
  claims: [],
  events: [],
  evidence: [],
  links: [],
  observations: [],
  reason_codes: ["experimental_cash_flow_research_model_ran"],
  cash_flow_research: {
    status: "research_estimate",
    issuer_id: "0001477333",
    accession_number: "0001477333-26-000016",
    filing_date: "2026-02-26",
    period_end: "2025-12-31",
    as_of: "2026-10-25T00:00:00Z",
    target: "positive_operating_cash_flow_1fy",
    probability: 0.75,
    architecture: "regularized_logistic_regression_c_0.1",
    model_sha256: "a".repeat(64),
    evaluation_sha256: "b".repeat(64),
    evidence_ids: ["filing"],
    limitations: ["Public issuers only; 25 test issuers."],
  },
};

it("shows the annual component, source dates and scope without a business score", () => {
  render(<CashFlowResearch sources={[source]} evidence={[]} />);
  expect(screen.getByText("75%")).toBeVisible();
  expect(screen.getByText(/conditional on observed follow-up/)).toBeVisible();
  expect(screen.getByText(/does not establish survival/)).toBeVisible();
  expect(screen.getByText(/2025-12-31/)).toBeVisible();
  fireEvent.click(screen.getByText("Model and supporting filings"));
  expect(screen.getByText(/Regularized logistic regression/)).toBeVisible();
  expect(screen.getByText(/25 test issuers/)).toBeVisible();
  expect(screen.queryByText(/AScore/)).toBeNull();
});

it("adds no estimate when the immutable source has no financial model output", () => {
  const { container } = render(<CashFlowResearch sources={[]} evidence={[]} />);
  expect(container).toBeEmptyDOMElement();
});
