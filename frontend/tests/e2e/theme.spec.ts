import { expect, test } from "@playwright/test";
import { auditAccessibility } from "../helpers/accessibility";
import scouting from "../../../tests/fixtures/api/scouting.json" with { type: "json" };
import report from "../../../tests/fixtures/api/research.json" with { type: "json" };

const screens = [
  ["home", "/", "Company research workspace"],
  ["domain", "/research/new", "Research a startup domain"],
  [
    "directory",
    "/explore?snapshot=synthetic-assessments-v1",
    "Research library",
  ],
  [
    "comparison",
    "/compare?snapshot=synthetic-assessments-v1&company=alpha&company=beta",
    "Compare companies",
  ],
  ["report", `/research/reports/${report.report_id}`, "Synthetic alpha"],
  ["about", "/about", "Startup research with its evidence attached"],
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
  expect(await canvas()).toBe("rgb(255, 226, 199)");
  for (const selector of [
    ".home-terminal-heading",
    ".home-directory",
    ".home-fundamentals",
  ]) {
    expect(
      await page
        .locator(selector)
        .evaluate((node) => getComputedStyle(node).backgroundImage),
    ).toContain("repeating-linear-gradient");
  }
  await page.evaluate(() =>
    document.documentElement.classList.remove("theme-techno-classical"),
  );
  expect(await canvas()).toBe("rgb(247, 249, 252)");
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.locator(".home-space-scene")).toBeHidden();
  for (const region of await page.locator(".home-pattern-region").all()) {
    await expect(region).toBeHidden();
  }
  expect(
    await page
      .locator("main")
      .evaluate((node) => node.scrollWidth <= node.clientWidth),
  ).toBe(true);
  await page.getByLabel("Search companies").scrollIntoViewIfNeeded();
  await expect(page.getByLabel("Search companies")).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
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

for (const viewport of [
  { width: 320, height: 740 },
  { width: 768, height: 1024 },
  { width: 1024, height: 768 },
]) {
  test(`research entry keeps readable controls and reachable actions at ${viewport.width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    const search = page.getByLabel("Search companies");
    await expect(search).toHaveAccessibleDescription(
      "Enter a name or website. You’ll confirm the company before research begins.",
    );
    await expect(
      page.getByRole("heading", { name: "Saved research" }),
    ).toBeVisible();
    for (const control of [
      search,
      page.getByRole("button", { name: "Research company", exact: true }),
      page.getByRole("link", { name: "Open dossier for Synthetic alpha" }),
    ]) {
      const bounds = await control.boundingBox();
      expect(bounds!.height).toBeGreaterThanOrEqual(44);
      expect(bounds!.width).toBeGreaterThanOrEqual(44);
    }
    await search.fill("alpha");
    const open = page.getByRole("link", {
      name: "Open dossier for Synthetic alpha",
    });
    await open.scrollIntoViewIfNeeded();
    await expect(open).toBeInViewport();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect((await auditAccessibility(page)).violations).toEqual([]);
    await page.screenshot({
      path: info.outputPath(`entry-${viewport.width}.png`),
      fullPage: true,
    });
    await open.focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("button", {
        name: "Expand dimension: Adoption & Retention",
      }),
    ).toBeVisible();
  });
}
