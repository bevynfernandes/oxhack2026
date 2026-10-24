import { expect, test } from "@playwright/test";
import type { DTO } from "../../src/api/client";
import { auditAccessibility } from "../helpers/accessibility";

const reportId = process.env.SIGNALSHIFT_REAL_MAPPING_REPORT_ID;
const groupNames = {
  adoption_retention: "Adoption & Retention",
  attention_sentiment: "Attention & Sentiment",
  financial_health: "Financial Health",
  industry_competition: "Industry & Competition",
  team_execution: "Team & Execution",
};

test("retained real evidence remains attributable through explicit immutable re-mapping", async ({
  page,
}, info) => {
  test.skip(!reportId, "Requires an explicit retained real mapped report");
  test.setTimeout(180_000);
  const sourceUrl = `/api/v2/research-reports/${reportId}`;
  const originalResponse = await page.request.get(sourceUrl);
  expect(originalResponse.ok()).toBe(true);
  const original = await originalResponse.text();
  const report: DTO<"Report"> = JSON.parse(original);
  const record = report.mapping?.records.find((row) => row.quotes.length);
  expect(record).toBeDefined();
  expect(report.captures.length).toBeGreaterThan(0);
  expect(report.identity.saved_context?.assessment.synthetic ?? false).toBe(
    false,
  );
  let writes = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname === "/api/v2/research-mapping-jobs"
    )
      writes++;
  });
  await page.goto(`/research/v2/reports/${reportId}`);
  await page
    .getByRole("button", {
      name: `Inspect evidence: ${groupNames[record!.group_id]}`,
    })
    .click();
  const dialog = page.getByRole("dialog");
  const claims = dialog.getByRole("region", {
    name: "Mapped claims and events",
  });
  await claims
    .getByRole("button", {
      name: `${record!.concept.replaceAll("_", " ")} · ${record!.subject.replaceAll("_", " ")}`,
      exact: true,
    })
    .first()
    .click();
  await expect(
    claims.getByText(record!.quotes[0].exact, { exact: true }).first(),
  ).toBeVisible();
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("real-mapped-quote.png") });
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Evidence mapping", exact: true })
    .click();
  expect(writes).toBe(0);
  const remap = dialog.getByRole("button", {
    name: "Re-map captured evidence",
  });
  await expect(remap).toBeEnabled();
  await remap.focus();
  await page.keyboard.press("Enter");
  const result = dialog.getByRole("link", { name: "Open newly mapped report" });
  await expect(result).toBeVisible({ timeout: 75_000 });
  expect(writes).toBe(1);
  const nextPath = await result.getAttribute("href");
  expect(nextPath).not.toBe(`/research/v2/reports/${reportId}`);
  const nextId = nextPath!.split("/").at(-1)!;
  const mapped: DTO<"Report"> = await (
    await page.request.get(`/api/v2/research-reports/${nextId}`)
  ).json();
  expect(mapped.mapping?.derived_from_report_id).toBe(reportId);
  expect(mapped.researched_at).toBe(report.researched_at);
  expect(mapped.outlook.as_of).toBe(report.outlook.as_of);
  expect(mapped.captures).toEqual(report.captures);
  expect(mapped.mapping?.mapped_at).not.toBe(report.mapping?.mapped_at);
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page
    .getByRole("button", { name: "Evidence mapping", exact: true })
    .click();
  await expect(result).toBeVisible();
  expect(
    await dialog.evaluate((node) => node.scrollWidth <= node.clientWidth),
  ).toBe(true);
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("real-remapping-mobile.png") });
  await result.click();
  await expect(page).toHaveURL(new RegExp(`${nextId}$`));
  expect(await (await page.request.get(sourceUrl)).text()).toBe(original);
  expect(writes).toBe(1);
});
