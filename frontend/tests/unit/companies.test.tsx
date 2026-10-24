import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { DTO } from "../../src/api/client";
import {
  Coverage,
  observationValue,
  Outcomes,
} from "../../src/pages/companies/shared";
import raw from "../../../tests/fixtures/api/companies.json";

it("keeps financial precision, actual zero, Boolean false and missingness distinct", () => {
  const row = raw.source.metrics[0] as DTO<"CompanyMetric">;
  expect(observationValue(row)).toBe("0");
  expect(
    observationValue({
      ...row,
      value: { kind: "decimal", value: "12345678901234567890.123456" },
    }),
  ).toBe("12345678901234567890.123456");
  expect(
    observationValue({ ...row, value: { kind: "boolean", value: false } }),
  ).toBe("No");
  expect(observationValue({ ...row, state: "missing", value: null })).toBe(
    "Missing",
  );
  expect(observationValue({ ...row, state: "conflicting", value: null })).toBe(
    "Conflicting evidence",
  );
  expect(
    observationValue({ ...row, state: "not_applicable", value: null }),
  ).toBe("Not applicable");
  expect(observationValue({ ...row, state: "restricted", value: null })).toBe(
    "Restricted measurement",
  );
});

it("renders all three published outcome sections without inventing a probability", () => {
  const outcomes = raw.assessments[0]
    .outcomes as DTO<"CompanyOutcomeAssessment">[];
  render(<Outcomes outcomes={outcomes} />);
  expect(
    screen.getByRole("heading", { name: "Operating and growing" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Cash-flow self-sufficiency" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Financing or acquisition" }),
  ).toBeVisible();
  expect(screen.getAllByText("Provisional · evidence only")).toHaveLength(2);
  expect(screen.getByText("Assessment unavailable")).toBeVisible();
  expect(screen.queryByText(/\d+%/)).toBeNull();
});

it("keeps stale and conflicting counts visible without treating inapplicable metrics as evidence", () => {
  render(
    <Coverage
      rows={[
        {
          company_id: "synthetic",
          family: "commercial",
          applicable_metric_ids: ["a", "b"],
          observed_metric_ids: ["a"],
          missing_metric_ids: [],
          conflicting_metric_ids: ["b"],
          inapplicable_metric_ids: ["c"],
          stale_metric_ids: ["a"],
          restricted_metric_ids: [],
        },
      ]}
    />,
  );
  expect(
    screen.getByText(
      "Commercial health: 1/2 observed; 1 stale; 1 conflicting; 1 not applicable",
    ),
  ).toBeVisible();
});
