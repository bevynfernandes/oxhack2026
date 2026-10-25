import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import type { DTO } from "../../src/api/client";
import { SourceProgress } from "../../src/pages/research/ResearchJobPage";

it("shows Search provenance separately and isolates provider attribution markup", () => {
  const source: DTO<"SourceState"> = {
    provider: "google_search",
    name: "Google Search discovery",
    state: "partial",
    reason_codes: ["google_search_unmatched_candidate"],
    captures: [],
    evidence: [],
    observations: [],
    claims: [],
    events: [],
    links: [],
    discovery: {
      run_id: "job",
      model: "gemma-4-31b-it",
      collected_at: "2026-10-25T04:00:00Z",
      requests: 1,
      reserved_input: 3000,
      queries: ["example.com funding"],
      candidates: [
        {
          url: "https://publisher.example/story",
          title: "Company story",
          state: "unmatched",
          reason: "google_search_unmatched_candidate",
        },
      ],
      search_suggestions: "<p>Search suggestions</p><script>unsafe()</script>",
    },
  };
  render(
    <MemoryRouter>
      <SourceProgress sources={[source]} />
    </MemoryRouter>,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Search discovery · 1 candidates" }),
  );

  expect(screen.getByText("example.com funding")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Company story (opens new tab)" }),
  ).toHaveAttribute("href", "https://publisher.example/story");
  expect(screen.getByText(/Only captured pages matched/)).toBeVisible();
  const attribution = screen.getByTitle("Google Search suggestions");
  expect(attribution).toHaveAttribute(
    "sandbox",
    "allow-popups allow-popups-to-escape-sandbox",
  );
  expect(attribution.getAttribute("sandbox")).not.toContain("allow-scripts");
  expect(attribution.getAttribute("sandbox")).not.toContain(
    "allow-same-origin",
  );
  expect(screen.queryByText("Search suggestions")).toBeNull();
});
