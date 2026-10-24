import AxeBuilder from "@axe-core/playwright";
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
    .getByRole("button", { name: "Inspect Attention & Sentiment" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Unavailable", { exact: true })).toBeVisible();
  await dialog.getByText("hn_algolia source", { exact: true }).click();
  await expect(
    dialog.getByRole("link", { name: "Original source (opens new tab)" }),
  ).toHaveAttribute("href", "https://hn.algolia.com/api/v1/search_by_date");
  await page.keyboard.press("Escape");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
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
