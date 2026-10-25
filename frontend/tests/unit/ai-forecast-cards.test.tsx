import { render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { DTO } from "../../src/api/client";
import AIForecastCards from "../../src/pages/research/AIForecastCards";
import { FORECAST_SOURCE } from "../../src/pages/research/preloadedForecasts";
import fixture from "../../../tests/fixtures/api/research.json";

function profile(company: string, snapshot = FORECAST_SOURCE) {
  const saved = structuredClone(
    fixture.inventory.saved_context,
  ) as unknown as Pick<DTO<"CompanyDetail">, "company" | "publication">;
  saved.company.company_id = company;
  saved.publication.source.snapshot_id = snapshot;
  return saved;
}

it.each([
  ["qdrant", [76, 84, 58]],
  ["weaviate", [72, 86, 60]],
] as const)(
  "renders all three %s estimates without a provider or key",
  (company, scores) => {
    render(<AIForecastCards profile={profile(company)} />);
    ["Growth outlook", "Survival outlook", "Financial health"].forEach(
      (name, index) => {
        const card = screen.getByRole("heading", { name }).closest("section")!;
        expect(card).toHaveTextContent(String(scores[index]));
        expect(
          within(card).getByRole("link", { name: /Supporting source/ }),
        ).toHaveAttribute("href", expect.stringMatching(/^https:/));
      },
    );
    expect(screen.getAllByText("AI outlook estimate")).toHaveLength(3);
    expect(screen.getAllByText(/not calibrated probabilities/)).toHaveLength(3);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  },
);

it("does not attach these estimates to other companies or future publications", () => {
  const view = render(<AIForecastCards profile={profile("other")} />);
  expect(screen.queryByRole("heading")).toBeNull();
  view.rerender(
    <AIForecastCards profile={profile("qdrant", "future-publication")} />,
  );
  expect(screen.queryByRole("heading")).toBeNull();
});
