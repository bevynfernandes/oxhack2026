import { expect, test } from "@playwright/test";
import { auditAccessibility } from "../helpers/accessibility";
import scouting from "../../../tests/fixtures/api/scouting.json" with { type: "json" };
import report from "../../../tests/fixtures/api/research.json" with { type: "json" };

const screens = [
  ["home", "/", "Company research workspace"],
  ["domain", "/research/new", "Research a startup domain"],
  ["directory", "/explore?snapshot=synthetic-assessments-v1", "Companies"],
  [
    "comparison",
    "/compare?snapshot=synthetic-assessments-v1&company=alpha&company=beta",
    "Compare companies",
  ],
  ["report", `/research/reports/${report.report_id}`, "Synthetic alpha"],
  ["methodology", "/methodology", "How to read a company outlook"],
  [
    "legacy",
    `/batches/${scouting.forecast.batch_id}/tools/tool-1`,
    "Fixture Tool 1",
  ],
] as const;

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 375, height: 812 },
]) {
  for (const [name, path, heading] of screens) {
    test(`${name} surface preserves readable content at ${viewport.width}px`, async ({
      page,
    }, info) => {
      await page.setViewportSize(viewport);
      await page.route("**/api/v1/research-reports/*", (route) =>
        route.fulfill({ json: report }),
      );
      await page.route("**/api/v2/research-capabilities", (route) =>
        route.fulfill({
          json: {
            collection_enabled: true,
            worker_available: true,
            browser_available: false,
            providers: [],
          },
        }),
      );
      await page.goto(path);
      await expect(
        page.getByRole("heading", { name: heading, exact: true }),
      ).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      if (name === "legacy")
        await expect(page.locator(".history-chart svg")).toBeVisible();
      await page.screenshot({
        path: info.outputPath(`${name}-${viewport.width}.png`),
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        name,
      ).toBe(true);
      expect((await auditAccessibility(page)).violations, name).toEqual([]);
      if (name === "report") {
        await page
          .getByRole("button", { name: "Source inventory", exact: true })
          .click();
        expect((await auditAccessibility(page)).violations).toEqual([]);
        await page.screenshot({
          path: info.outputPath(`drawer-${viewport.width}.png`),
        });
        await page.keyboard.press("Escape");
        await expect(page.getByRole("dialog")).not.toBeVisible();
      }
    });
  }
}
