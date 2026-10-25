import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { ResearchWorkspace } from "../../src/pages/research/ResearchReportPage";
import { SourceLink } from "../../src/components/Common";
import { researchResult } from "../../src/pages/research/client";
import type { DTO } from "../../src/api/client";
import fixture from "../../../tests/fixtures/api/research.json";

const report = fixture as unknown as DTO<"ResearchReport">;
it("renders three backend horizons and five drivers without numerical outlook", () => {
  render(
    <MemoryRouter>
      <ResearchWorkspace report={report} />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
  expect(screen.getAllByText("24 months")).toHaveLength(2);
  expect(screen.queryByText("12 months")).toBeNull();
  expect(
    screen.getByRole("heading", { name: "Overall outlook" }),
  ).toBeVisible();
  expect(screen.getAllByRole("button", { name: /^Inspect / })).toHaveLength(5);
  expect(screen.getByText(/Partial source results/)).toBeVisible();
  expect(screen.queryByText(/\d+%/)).toBeNull();
});
it("does not add forecasts when opening an older immutable report", () => {
  const legacy = {
    ...report,
    outlook: { ...report.outlook, forecasts: undefined },
  };
  render(
    <MemoryRouter>
      <ResearchWorkspace report={legacy} />
    </MemoryRouter>,
  );
  expect(screen.getByText(/Legacy report:/)).toBeVisible();
  expect(screen.queryByText("24 months")).toBeNull();
  expect(
    screen.getByRole("link", { name: "View original saved analysis" }),
  ).toHaveAttribute("href", "/companies/synthetic-assessments-v1/alpha");
});
it("does not present proxy experiments as trained business outcome models", () => {
  const groups: DTO<"SpecialistOutlook">["group_id"][] = [
    "adoption_retention",
    "attention_sentiment",
    "financial_health",
    "industry_competition",
    "team_execution",
  ];
  const attached: DTO<"ResearchReport"> = {
    ...report,
    inventory: {
      ...report.inventory,
      saved_context: {
        ...report.inventory.saved_context,
        dimension_models: {
          schema_version: "experimental-dimensions-v1",
          company_id: "alpha",
          source_snapshot_id: "synthetic-companies-v1",
          as_of: "2025-02-01T00:00:00Z",
          model_bundle_sha256: "a".repeat(64),
          dimensions: groups.map((group, index) => ({
            group_id: group,
            model_status: "experimental_trained",
            architecture: "Test model",
            target: "Test proxy, not success",
            model_sha256: "b".repeat(64),
            eligibility: index ? "insufficient_data" : "eligible",
            score: index ? null : 34.8,
            predicted_value: index ? null : 0.1,
            prediction_unit: index ? null : "log growth",
            metric_observation_ids: index ? [] : ["current", "previous"],
            reason_codes: ["experimental_proxy"],
            limitations: ["Not validated company success"],
          })),
        },
      },
    },
  };
  render(
    <MemoryRouter>
      <ResearchWorkspace report={attached} />
    </MemoryRouter>,
  );
  expect(screen.getAllByText("Outcome model untrained")).toHaveLength(5);
  expect(screen.queryByText("SDK demand index: 34.8 / 100")).toBeNull();
  expect(screen.getAllByText("Prediction unavailable")).toHaveLength(2);
  expect(screen.getByText("Combined score unavailable")).toBeVisible();
  expect(screen.getByText(/outcome models pending/)).toBeVisible();
});
it.each([
  [409, "identity"],
  [503, "unavailable"],
  [404, "not found"],
  [422, "confirm"],
])("reports safe research error %i", (status, message) => {
  expect(() =>
    researchResult({
      response: new Response("private", { status: Number(status) }),
    }),
  ).toThrow(String(message));
});

it("keeps validated HN item links clickable without admitting arbitrary query data", () => {
  render(
    <>
      <SourceLink url="https://news.ycombinator.com/item?id=123">
        HN story
      </SourceLink>
      <SourceLink url="https://news.ycombinator.com/item?id=123&token=private">
        Invalid story
      </SourceLink>
      <SourceLink url="https://news.ycombinator.com.example/item?id=123">
        Lookalike
      </SourceLink>
    </>,
  );
  expect(
    screen.getByRole("link", { name: "HN story (opens new tab)" }),
  ).toHaveAttribute("href", "https://news.ycombinator.com/item?id=123");
  expect(screen.getAllByRole("link")).toHaveLength(1);
});
