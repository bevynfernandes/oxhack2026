import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import DecisionBrief from "../../src/pages/research/DecisionBrief";
import type { EvidenceSummary } from "../../src/pages/research/summary";

type Report = NonNullable<ComponentProps<typeof DecisionBrief>["report"]>;
const report = {
  outlook: {
    specialists: [
      {
        group_id: "adoption_retention",
        data_status: "insufficient_data",
        usable_metric_observation_ids: ["usable"],
      },
    ],
  },
  evidence: [{ evidence_id: "source", url: "https://example.com/research" }],
  mapping: {
    state: "partial",
    analysis: { state: "unavailable", statements: [] },
    records: [{ mapping_id: "mapped", evidence_ids: ["source"] }],
  },
  dimension_models: {
    dimensions: [
      {
        group_id: "attention_sentiment",
        eligibility: "eligible",
        score: 48.285,
        sample_size: 4,
      },
    ],
  },
} as unknown as Report;
const summary: EvidenceSummary = {
  name: "Example",
  domain: "example.com",
  asOf: null,
  context: "Standalone research",
  coverage: "One usable measurement",
  supporting: "",
  risk: "",
  gaps: [],
  limitations: [],
  synthetic: false,
  measurements: [
    {
      id: "missing",
      label: "Revenue",
      value: "Unavailable",
      unit: "USD",
      definition: "Reported revenue",
      period: "Unknown",
      collected: null,
    },
    {
      id: "usable",
      label: "Retrieved links",
      collected: null,
      value: "4",
      unit: "story_links",
      definition: "Retrieved story links, not users.",
      period: "September to October",
    },
  ],
};

it("shows usable observations and labels experiments without fabricating a company verdict", () => {
  const inspect = vi.fn();
  render(
    <DecisionBrief report={report} summary={summary} onEvidence={inspect} />,
  );
  expect(screen.getByText("Interpretation unavailable")).toBeVisible();
  expect(screen.getByText("Retrieved story links, not users.")).toBeVisible();
  expect(screen.getByText(/48.3/)).toBeVisible();
  expect(
    screen.getByText("Not customer sentiment or a company-success score."),
  ).toBeVisible();
  expect(screen.queryByText("Revenue")).toBeNull();
  fireEvent.click(
    screen.getByRole("button", { name: "Inspect supporting evidence" }),
  );
  expect(inspect).toHaveBeenCalledOnce();
});

it("uses the report's finding and citation when interpretation becomes available", () => {
  const available = {
    ...report,
    mapping: {
      ...report.mapping!,
      analysis: {
        state: "completed",
        statements: [
          {
            kind: "finding",
            text: "Company reports 20 paying teams.",
            mapping_ids: ["mapped"],
          },
        ],
      },
    },
  } as unknown as Report;
  render(
    <DecisionBrief report={available} summary={summary} onEvidence={vi.fn()} />,
  );
  expect(screen.getByText("Company reports 20 paying teams.")).toBeVisible();
  expect(
    screen.getByRole("link", {
      name: "Read supporting source (opens new tab)",
    }),
  ).toHaveAttribute("href", "https://example.com/research");
  expect(
    screen.getByText(
      "Source-grounded interpretation, not a validated prediction.",
    ),
  ).toBeVisible();
  expect(screen.queryByText("Retrieved story links, not users.")).toBeNull();
});

it("withholds ineligible experimental scores", () => {
  const unavailable = {
    ...report,
    dimension_models: {
      dimensions: [
        {
          ...report.dimension_models!.dimensions[0],
          eligibility: "unreliable",
          score: 99,
        },
      ],
    },
  } as Report;
  render(
    <DecisionBrief
      report={unavailable}
      summary={summary}
      onEvidence={vi.fn()}
    />,
  );
  expect(screen.queryByText(/99/)).toBeNull();
  expect(
    screen.getByRole("heading", { name: "Before making a decision" }),
  ).toBeVisible();
});

it("uses a saved publication's measurements without claiming fresh interpretation", () => {
  render(
    <DecisionBrief
      summary={summary}
      usableIds={["usable"]}
      models={report.dimension_models}
      onEvidence={vi.fn()}
    />,
  );
  expect(screen.getByText("Retrieved story links, not users.")).toBeVisible();
  expect(screen.getByText("Evidence review")).toBeVisible();
  expect(screen.queryByText("Interpretation unavailable")).toBeNull();
  expect(
    screen.getByRole("heading", { name: "Title sentiment" }),
  ).toBeVisible();
});
