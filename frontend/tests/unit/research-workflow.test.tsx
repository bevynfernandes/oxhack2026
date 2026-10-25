import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { DTO } from "../../src/api/client";
import {
  ContinueControls,
  InterpretationSummary,
  ProfilePicker,
} from "../../src/pages/research/ResearchWorkflow";
import * as client from "../../src/pages/research/client";

afterEach(() => vi.restoreAllMocks());
const statistics: DTO<"InterpretationStatistics"> = {
  mode: "rules_gemini",
  model: "test-model",
  stage: "finished",
  candidates: 200,
  processed: 120,
  deferred: 80,
  batches: 5,
  failed_batches: 1,
  cached_batches: 3,
  provider_requests: 2,
  accepted_proposals: 7,
  rejected_proposals: 4,
  input_tokens: null,
  output_tokens: null,
};

it("labels cached work separately from new calls and unknown usage", () => {
  render(<InterpretationSummary statistics={statistics} />);
  expect(
    screen.getByText(
      /120 of 200 evidence blocks reviewed by Gemini · 80 deferred/,
    ),
  ).toBeVisible();
  expect(
    screen.getByText(
      /2 new provider requests · 3 cached batches · 1 failed batches/,
    ),
  ).toBeVisible();
  expect(
    screen.getByText(/input not reported, output not reported/),
  ).toBeVisible();
});

it("makes a rules-only historical report explicit without inventing Gemini activity", () => {
  render(<InterpretationSummary mode="rules" />);
  expect(screen.getByText(/Gemini did not run/)).toBeVisible();
  expect(screen.queryByText(/provider requests/)).toBeNull();
});

it("offers all bounded profiles through a labelled native control", () => {
  const change = vi.fn();
  render(<ProfilePicker value="thorough" onChange={change} />);
  const control = screen.getByRole("combobox", { name: "Research depth" });
  expect(control).toHaveValue("thorough");
  fireEvent.change(control, { target: { value: "deep" } });
  expect(change).toHaveBeenCalledWith("deep");
  expect(screen.getAllByRole("option")).toHaveLength(3);
});

it.each([false, true])(
  "continues only on a click, including failed-only work (%s)",
  async (failedOnly) => {
    vi.spyOn(client, "fetchCapabilities").mockResolvedValue({
      collection_enabled: true,
      worker_available: true,
    } as Awaited<ReturnType<typeof client.fetchCapabilities>>);
    const create = vi
      .spyOn(client, "continueResearch")
      .mockResolvedValue({ job_id: "continued" } as Awaited<
        ReturnType<typeof client.continueResearch>
      >);
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter>
          <Routes>
            <Route
              path="/"
              element={
                <ContinueControls
                  jobId="original"
                  sources={
                    failedOnly
                      ? [
                          {
                            provider: "github",
                            name: "GitHub",
                            state: "failed",
                          } as DTO<"SourceState">,
                        ]
                      : []
                  }
                  mapping={
                    {
                      state: failedOnly ? "completed" : "partial",
                      statistics: {
                        ...statistics,
                        deferred: failedOnly ? 0 : 80,
                      },
                    } as DTO<"MappingProgress">
                  }
                />
              }
            />
            <Route
              path="/research/v2/jobs/:jobId"
              element={<p>New immutable research job</p>}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const button = screen.getByRole("button", { name: "Continue research" });
    await waitFor(() => expect(button).toBeEnabled());
    expect(create).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "deep" },
    });
    fireEvent.click(button);
    expect(await screen.findByText("New immutable research job")).toBeVisible();
    expect(create).toHaveBeenCalledExactlyOnceWith(
      "original",
      "deep",
      undefined,
    );
  },
);

it("distinguishes failed extraction from successful cited synthesis", () => {
  render(
    <InterpretationSummary
      statistics={{
        ...statistics,
        processed: 0,
        deferred: 200,
        accepted_proposals: 0,
      }}
      analysis={{
        state: "partial",
        method: "gemini",
        statements: [
          {
            text: "Company reports revenue over $50 million a year.",
            group_id: "financial_health",
            kind: "finding",
            mapping_ids: ["revenue"],
          },
        ],
        reason_codes: ["analysis_unsupported_statement"],
      }}
    />,
  );
  expect(
    screen.getByText(/Processing ended with incomplete extraction/),
  ).toBeVisible();
  expect(
    screen.getByText(/Synthesis: partial · 1 validated statements/),
  ).toBeVisible();
  expect(screen.getByText(/0 supported extraction proposals/)).toBeVisible();
});
