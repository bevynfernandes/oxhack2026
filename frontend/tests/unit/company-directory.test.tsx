import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { expect, it } from "vitest";
import type { DTO } from "../../src/api/client";
import CompanyListPage from "../../src/pages/companies/CompanyListPage";
import raw from "../../../tests/fixtures/api/companies.json";

function LocationControls() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output aria-label="Current filters">{location.search}</output>
      <button onClick={() => navigate(-1)}>Back</button>
    </>
  );
}

it("composes rapid filter and comparison changes without restoring a cleared search", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity } },
  });
  const publication: DTO<"CompanyPublication"> = {
    schema_version: "company-api-v1",
    company_count: 2,
    assessment: raw.publication as DTO<"CompanyAssessmentPublication">,
    source: raw.source as DTO<"CompanySnapshotMetadata">,
  };
  const snapshot = publication.assessment.publication_id;
  const rows: DTO<"CompanySummary">[] = raw.source.companies.map((company) => ({
    company,
    assessment_id: company.company_id,
    coverage: [
      {
        company_id: company.company_id,
        family: "traction",
        applicable_metric_ids: ["missing"],
        observed_metric_ids: [],
        missing_metric_ids: ["missing"],
        conflicting_metric_ids: [],
        inapplicable_metric_ids: [],
        stale_metric_ids: [],
        restricted_metric_ids: [],
      },
    ],
    outcomes: [],
    main_risk: null,
    supporting_signal: null,
  }));
  client.setQueryData(["company-publications"], { items: [publication] });
  client.setQueryData(["companies", snapshot], { publication, items: rows });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/explore?snapshot=${snapshot}&q=beta`]}>
        <CompanyListPage />
        <LocationControls />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const search = screen.getByRole("searchbox", { name: "Search companies" });
  expect(search).toHaveValue("beta");
  act(() => {
    fireEvent.change(search, { target: { value: "" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Stage" }), {
      target: { value: "unknown" },
    });
    fireEvent.change(screen.getByLabelText("Evidence coverage"), {
      target: { value: "gaps" },
    });
  });
  expect(search).toHaveValue("");
  const alpha = screen.getByRole("checkbox", {
    name: "Compare Synthetic alpha",
  });
  const beta = screen.getByRole("checkbox", { name: "Compare Synthetic beta" });
  act(() => {
    fireEvent.click(alpha);
    fireEvent.click(beta);
  });
  expect(alpha).toBeChecked();
  expect(beta).toBeChecked();
  const filters = new URLSearchParams(
    screen.getByLabelText("Current filters").textContent!,
  );
  expect(filters.has("q")).toBe(false);
  expect(filters.get("stage")).toBe("unknown");
  expect(filters.get("coverage")).toBe("gaps");
  expect(filters.getAll("company")).toEqual(["alpha", "beta"]);
  expect(
    screen.getByRole("link", { name: "Compare selected companies" }),
  ).toHaveAttribute(
    "href",
    expect.stringContaining("company=alpha&company=beta"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
  expect(alpha).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(alpha).toBeChecked();
  expect(beta).toBeChecked();
});
