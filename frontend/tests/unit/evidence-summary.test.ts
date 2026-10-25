import { expect, it } from "vitest";
import fixture from "../../../tests/fixtures/api/research.json";
import { evidenceSummary } from "../../src/pages/research/summary";
import { fetchComparisonRecord } from "../../src/pages/research/ResearchComparison";
import type { fetchResearchReport } from "../../src/pages/research/client";
const report = fixture as unknown as Awaited<
  ReturnType<typeof fetchResearchReport>
>;
it("keeps fresh legacy dates and missing measurements instead of silently comparing saved context", () => {
  const summary = evidenceSummary(undefined, undefined, report);
  expect(summary.asOf).toBe(report.researched_at);
  expect(summary.asOf).not.toBe(
    report.inventory.saved_context.assessment.as_of,
  );
  expect(summary.measurements[0]).toMatchObject({
    value: "Unavailable",
    definition: report.inventory.observations[0].definition,
  });
  expect(summary.synthetic).toBe(true);
  expect(summary.coverage).toContain("not confidence");
  expect(summary.risk).toContain("not evidence of failure");
});
it("preserves measured zero and source period without deriving a success score", () => {
  const copy = structuredClone(report);
  copy.inventory.observations[0].value = 0;
  const summary = evidenceSummary(undefined, undefined, copy);
  expect(summary.measurements[0].value).toBe("0");
  expect(summary.measurements[0].period).toContain("end excluded");
  expect(summary).not.toHaveProperty("prediction");
});
it("renders a genuine empty evidence state and rejects arbitrary comparison destinations", async () => {
  expect(evidenceSummary().measurements).toEqual([]);
  expect(evidenceSummary().supporting).toContain(
    "No usable supporting measurement",
  );
  await expect(fetchComparisonRecord("https://example.com")).rejects.toThrow(
    "Choose a saved dossier",
  );
  await expect(fetchComparisonRecord("/research/v2/jobs/one")).rejects.toThrow(
    "Choose a saved dossier",
  );
});
