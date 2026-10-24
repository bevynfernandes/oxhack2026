import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { DTO } from "../../src/api/client";
import {
  MappingControls,
  MappedDimensionEvidence,
} from "../../src/pages/research/EvidenceMapping";
import * as client from "../../src/pages/research/client";

const source: DTO<"Report"> = {
  schema_version: "research-report-v2",
  report_id: "original",
  job_id: "collection",
  researched_at: "2026-10-24T12:00:00Z",
  identity: {} as DTO<"Identity">,
  sources: [],
  observations: [],
  claims: [],
  events: [],
  captures: [],
  evidence: [
    {
      evidence_id: "proof",
      capture_id: "capture",
      url: "https://example.com/about",
      excerpt: "Our customer grew revenue by 40 percent.",
      location: "p[1]",
      collected_at: "2026-10-24T12:00:00Z",
    },
  ],
  outlook: {} as DTO<"StartupOutlook">,
  limitations: [],
  mapping: {
    schema_version: "evidence-mapping-v1",
    policy_version: "public-evidence-mapping-v1",
    parser_version: "evidence-document-v2",
    prompt_version: "evidence-proposals-v1",
    artifacts: [],
    dispositions: [],
    reason_codes: [],
    generation_attempts: 0,
    input_tokens: 0,
    output_tokens: 0,
    mapped_at: "2026-10-24T12:05:00Z",
    source_as_of: "2026-10-24T12:00:00Z",
    state: "completed",
    mode: "rules",
    records: [
      {
        mapping_id: "mapping",
        record_type: "claim",
        record_id: "claim",
        group_id: "adoption_retention",
        concept: "revenue",
        subject: "customer",
        subject_name: "Customer in quoted context",
        attribution: "company_reported",
        method: "rule",
        language: "en",
        metric_eligible: false,
        qualifier: "unknown",
        evidence_ids: ["proof"],
        reason_codes: ["customer_context"],
        quotes: [
          {
            evidence_id: "proof",
            capture_id: "capture",
            document_sha256: "a".repeat(64),
            prefix: "",
            suffix: "",
            block_id: "block",
            exact: "Our customer grew revenue by 40 percent.",
            start: 0,
            end: 39,
            location: "p[1]",
          },
        ],
      },
    ],
    dimensions: [],
  },
};

afterEach(() => vi.restoreAllMocks());

it("keeps customer evidence attributable and linked within its backend dimension", () => {
  render(
    <MemoryRouter>
      <MappedDimensionEvidence report={source} group="adoption_retention" />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByText("revenue · customer"));
  expect(
    screen.getByText("Our customer grew revenue by 40 percent."),
  ).toBeVisible();
  expect(screen.getByText(/not verified business outcomes/)).toBeVisible();
  expect(screen.getByRole("link", { name: /Read source/ })).toHaveAttribute(
    "href",
    "https://example.com/about",
  );
  expect(screen.queryByText(/success probability/)).toBeNull();
});

it("re-maps only after an explicit click and preserves the current report", async () => {
  const capabilities = vi.spyOn(client, "fetchCapabilities").mockResolvedValue({
    schema_version: "research-capabilities-v2",
    storage_available: true,
    collection_enabled: false,
    worker_available: true,
    browser_available: false,
    providers: [],
    active_jobs: 2,
    queued_jobs: 8,
    network_operations: 8,
    deadline_seconds: 300,
    request_budget: 120,
    response_bytes: 4194304,
    capture_bytes: 33554432,
    mapping: {
      enabled: true,
      mode: "rules",
      gemini_available: false,
      deadline_seconds: 60,
    },
  });
  const create = vi.spyOn(client, "createMappingJob").mockResolvedValue({
    schema_version: "research-mapping-job-v1",
    job_id: "remapping",
    source_report_id: "original",
    requested_at: "2026-10-24T12:06:00Z",
    progress: { state: "pending", completed_batches: 0, reason_codes: [] },
  });
  const read = vi.spyOn(client, "fetchMappingJob").mockResolvedValue({
    schema_version: "research-mapping-job-v1",
    job_id: "remapping",
    source_report_id: "original",
    report_id: "new-report",
    requested_at: "2026-10-24T12:06:00Z",
    progress: { state: "completed", completed_batches: 2, reason_codes: [] },
  });
  const queries = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queries}>
      <MemoryRouter>
        <MappingControls report={source} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(capabilities).toHaveBeenCalledOnce());
  const button = screen.getByRole("button", {
    name: "Re-map captured evidence",
  });
  await waitFor(() => expect(button).toBeEnabled());
  expect(create).not.toHaveBeenCalled();
  fireEvent.click(button);
  await waitFor(() => expect(read).toHaveBeenCalledWith("remapping"));
  expect(create).toHaveBeenCalledOnce();
  expect(create).toHaveBeenCalledWith("original");
  expect(
    await screen.findByRole("link", { name: "Open newly mapped report" }),
  ).toHaveAttribute("href", "/research/v2/reports/new-report");
  expect(source.report_id).toBe("original");
});
