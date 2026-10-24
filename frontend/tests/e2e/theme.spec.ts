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
      expect(
        await page
          .getByRole("main")
          .evaluate((node) => node.scrollWidth <= node.clientWidth),
        `${name} main region must not hide controls off screen`,
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

test("theme preserves keyboard scrolling, native focus and reduced motion at narrow zoom layouts", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/batches/${scouting.forecast.batch_id}/tools/tool-1`);
  const history = page.getByRole("region", {
    name: "Observed download history",
  });
  await expect(history).toBeVisible();
  expect(
    await history.evaluate((node) => node.scrollWidth > node.clientWidth),
  ).toBe(true);
  await history.focus();
  await expect(history).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() => history.evaluate((node) => node.scrollLeft))
    .toBeGreaterThan(0);
  expect((await auditAccessibility(page)).violations).toEqual([]);
  // A 720×450 CSS viewport exercises the reflow available at 200% of 1440×900.
  await page.setViewportSize({ width: 720, height: 450 });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page
    .getByRole("link", { name: "Open dossier for Synthetic alpha" })
    .focus();
  await page.keyboard.press("Enter");
  const measurements = page.getByRole("region", {
    name: "Adoption & Retention measurements",
  });
  await measurements.focus();
  await expect(measurements).toBeFocused();
  await page
    .getByRole("button", { name: "Expand dimension: Adoption & Retention" })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Expand dimension: Adoption & Retention",
    }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await auditAccessibility(page)).violations).toEqual([]);
  const main = page.getByRole("main");
  expect(
    await main.evaluate((node) => node.scrollHeight > node.clientHeight),
  ).toBe(true);
  const ledger = page.locator(".dossier-ledger");
  await ledger.scrollIntoViewIfNeeded();
  expect(
    await ledger.evaluate((node) => {
      const bounds = node.getBoundingClientRect();
      const viewport = document.querySelector("main")!.getBoundingClientRect();
      return bounds.top >= viewport.top && bounds.bottom <= viewport.bottom;
    }),
  ).toBe(true);
  await page.screenshot({ path: info.outputPath("zoom-layout.png") });
});

test("theme can roll back to the preserved light styles and respects forced colours", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByLabel("Search companies")).toBeVisible();
  const canvas = () =>
    page
      .locator("html")
      .evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(await canvas()).toBe("rgb(13, 13, 36)");
  await page.evaluate(() =>
    document.documentElement.classList.remove("theme-techno-classical"),
  );
  expect(await canvas()).toBe("rgb(247, 249, 252)");
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.evaluate(() =>
    document.documentElement.classList.add("theme-techno-classical"),
  );
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await page.getByLabel("Search companies").focus();
  await expect(page.getByLabel("Search companies")).toBeFocused();
  expect(
    await page
      .locator(".app-shell")
      .evaluate((node) => getComputedStyle(node).backgroundImage),
  ).toBe("none");
  await page.screenshot({ path: info.outputPath("forced-colours.png") });
});
