import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { ResearchWorkspace } from "../../src/pages/research/ResearchReportPage";
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
  expect(screen.getByText("12 months")).toBeVisible();
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
