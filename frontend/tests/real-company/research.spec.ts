import { auditAccessibility } from "../helpers/accessibility";
import { expect, test } from "@playwright/test";

const reportId = process.env.SIGNALSHIFT_REAL_REPORT_ID;
test("real partial research replay preserves immutable legacy report and source details", async ({
  page,
}, info) => {
  test.skip(
    !reportId,
    "Requires the verified research replay and enabled local read service",
  );
  const url = "/api/v1/research-reports/" + reportId;
  const response = await page.request.get(url);
  expect(response.ok()).toBe(true);
  const original = await response.text();
  const report = JSON.parse(original);
  expect(report.inventory.synthetic).toBe(false);
  expect(report.outlook.forecasts).toBeUndefined();
  expect(report.outlook.specialists).toHaveLength(5);
  await page.goto("/research/reports/" + reportId);
  await expect(
    page.getByRole("heading", { name: "Qdrant", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Legacy report:/)).toBeVisible();
  await expect(page.getByText(/Partial source results/)).toBeVisible();
  await expect(page.getByText("24 months")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Inspect evidence: Attention & Sentiment" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Unavailable", { exact: true })).toBeVisible();
  await dialog.getByText("hn_algolia source", { exact: true }).click();
  await expect(
    dialog.getByRole("link", { name: "Original source (opens new tab)" }),
  ).toHaveAttribute("href", "https://hn.algolia.com/api/v1/search_by_date");
  await page.keyboard.press("Escape");
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({
    path: info.outputPath("real-research-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("real-research-mobile.png"),
    fullPage: true,
  });
  await page.reload();
  expect(await (await page.request.get(url)).text()).toBe(original);
});

test("live standalone domain preview, collection, evidence and immutable refresh", async ({
  page,
}, info) => {
  test.skip(
    process.env.SIGNALSHIFT_LIVE_RESEARCH_UI !== "1",
    "Explicit live UI collection opt-in required",
  );
  test.setTimeout(1_400_000);
  for (const domain of ["qdrant.tech", "posthog.com", "linear.app"]) {
    await page.goto("/research/new");
    await page.getByLabel("Company domain").fill(domain);
    await page.getByRole("button", { name: "Preview company" }).click();
    await expect(page.getByRole("status")).toHaveText(
      "Identity preview ready",
      { timeout: 90_000 },
    );
    await expect(
      page.getByRole("button", { name: "Confirm and start research" }),
    ).toBeDisabled();
    await page.getByRole("checkbox").check();
    await page
      .getByRole("button", { name: "Confirm and start research" })
      .click();
    await expect(
      page.getByRole("link", { name: "Open research report" }),
    ).toBeVisible({ timeout: 360_000 });
    const jobUrl = page.url();
    await page.getByRole("link", { name: "Open research report" }).click();
    await expect(
      page.getByRole("heading", { name: "Overall outlook unavailable" }),
    ).toBeVisible();
    const reportUrl = page.url();
    const id = reportUrl.split("/").at(-1)!;
    const response = await page.request.get("/api/v2/research-reports/" + id);
    expect(response.ok()).toBe(true);
    const original = await response.text();
    const report = JSON.parse(original);
    expect(report.identity.saved_context).toBeNull();
    expect(report.sources[0].evidence.length).toBeGreaterThan(0);
    expect(report.captures.length).toBeGreaterThan(0);
    expect(
      report.outlook.forecasts.every(
        (row: { prediction: unknown }) => row.prediction === null,
      ),
    ).toBe(true);
    await page
      .getByRole("button", { name: "Sources & limitations", exact: true })
      .click();
    await expect(
      page
        .getByRole("dialog")
        .getByText("Fresh source coverage", { exact: true }),
    ).toBeVisible();
    expect((await auditAccessibility(page)).violations).toEqual([]);
    await page.getByRole("tab", { name: "Measurements", exact: true }).click();
    await expect(
      page
        .getByRole("dialog")
        .getByText("Fresh collection", { exact: false })
        .first(),
    ).toBeVisible();
    await page.screenshot({ path: info.outputPath(domain + "-evidence.png") });
    await page.keyboard.press("Escape");
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({ path: info.outputPath(domain + "-mobile.png") });
    await page.setViewportSize({ width: 1280, height: 800 });
    if (domain === "linear.app") {
      await page.getByRole("link", { name: "Refresh research" }).click();
      await page.getByRole("checkbox").check();
      await page
        .getByRole("button", { name: "Confirm and start research" })
        .click();
      await expect(
        page.getByRole("link", { name: "Open research report" }),
      ).toBeVisible({ timeout: 360_000 });
      expect(page.url()).not.toBe(jobUrl);
      await page.getByRole("link", { name: "Open research report" }).click();
      expect(page.url()).not.toBe(reportUrl);
      expect(
        await (await page.request.get("/api/v2/research-reports/" + id)).text(),
      ).toBe(original);
    }
  }
});
