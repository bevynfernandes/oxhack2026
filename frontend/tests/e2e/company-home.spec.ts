import { auditAccessibility } from "../helpers/accessibility";
import { expect, test } from "@playwright/test";

test("company homepage searches and opens a saved analysis with keyboard", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Company research workspace" }),
  ).toBeVisible();
  await page.getByLabel("Search companies").fill("no-such-company");
  await expect(page.getByText(/No companies match your search/)).toBeVisible();
  await page.getByLabel("Search companies").fill("alpha");
  const analysis = page.getByRole("link", {
    name: "Open dossier for Synthetic alpha",
  });
  await expect(analysis).toBeVisible();
  await expect(analysis).toHaveCSS("display", /^(inline-)?flex$/);
  await expect(analysis).toHaveCSS("align-items", "center");
  await expect(analysis).toHaveCSS("justify-content", "center");
  await expect(
    page.getByRole("link", { name: "Open dossier for Synthetic beta" }),
  ).toHaveCount(0);
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("homepage-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("homepage-mobile.png"),
    fullPage: true,
  });
  await page.getByLabel("Search companies").fill("https://www.alpha.example/");
  await expect(analysis).toBeVisible();
  await page.getByLabel("Search companies").fill("alpha.example.attacker.test");
  await expect(page.getByText(/No companies match your search/)).toBeVisible();
  await page.getByLabel("Search companies").fill("alpha.example");
  await expect(page.getByText("alpha.example", { exact: true })).toBeVisible();
  await analysis.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
});

test("unavailable name lookup explains how to research a website without a saved-link error", async ({
  page,
}) => {
  await page.route("**/api/v2/company-search", (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  await page.goto("/");
  await page.getByLabel("Search companies").fill("Posthog");
  await page
    .getByRole("button", { name: "Research company", exact: true })
    .click();
  await expect(page.getByRole("alert")).toHaveText(
    "Company-name lookup is unavailable. Enter the company’s exact website domain to research it directly.",
  );
});

test("homepage honestly handles empty and failed publication lists", async ({
  page,
}) => {
  await page.route("**/api/v1/company-snapshots", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText(
    "No company assessments",
  );
  await page.route("**/api/v1/company-snapshots", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page.reload();
  await expect(page.getByRole("status")).toContainText("unavailable");
  const retry = page.getByRole("button", { name: "Retry saved assessments" });
  await expect(retry).toBeVisible();
  await page.route("**/api/v1/company-snapshots", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await retry.click();
  await expect(page.getByRole("status")).toContainText(
    "No company assessments",
  );
});

test("directory pagination remains reachable on a small mobile screen", async ({
  page,
}) => {
  await page.route("**/api/v1/company-snapshots/*/companies", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const gamma = {
      ...body.items[0],
      company: {
        ...body.items[0].company,
        company_id: "gamma",
        display_name: "Synthetic gamma",
      },
    };
    await route.fulfill({
      response,
      json: { ...body, items: [...body.items, gamma] },
    });
  });
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: /Open dossier for/ }),
  ).toHaveCount(2);
  await expect(page.getByText("Page 1 of 2")).toBeVisible();
  const next = page.getByRole("button", { name: "Next", exact: true });
  await next.scrollIntoViewIfNeeded();
  await expect(next).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Open dossier for Synthetic gamma" }),
  ).toBeVisible();
  await page.getByLabel("Search companies").fill("alpha");
  await expect(
    page.getByRole("link", { name: "Open dossier for Synthetic alpha" }),
  ).toBeVisible();
});

test("search covers every configured publication and dotted company names", async ({
  page,
}) => {
  await page.route("**/api/v1/company-snapshots", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      json: {
        items: [
          ...body.items,
          {
            ...body.items[0],
            assessment: {
              ...body.items[0].assessment,
              publication_id: "older-publication",
              recorded_at: "2024-01-01T00:00:00Z",
            },
          },
        ],
      },
    });
  });
  await page.route(
    "**/api/v1/company-snapshots/older-publication/companies",
    async (route) => {
      const response = await page.request.get(
        "/api/v1/company-snapshots/synthetic-assessments-v1/companies",
      );
      const body = await response.json();
      await route.fulfill({
        json: {
          items: [
            {
              ...body.items[0],
              company: {
                ...body.items[0].company,
                company_id: "node-js",
                display_name: "Node.js",
                website_url: "https://nodejs.example",
              },
            },
          ],
        },
      });
    },
  );
  await page.goto("/");
  await page.getByLabel("Search companies").fill("Node.js");
  await expect(
    page.getByRole("link", { name: "Open dossier for Node.js" }),
  ).toHaveAttribute("href", "/companies/older-publication/node-js");
  await page
    .getByLabel("Search companies")
    .fill("nodejs.example.attacker.test");
  await expect(
    page.getByRole("link", { name: "Open dossier for Node.js" }),
  ).toHaveCount(0);
});

test("desktop homepage fits without footer clutter and keeps background motion visible", async ({
  page,
}, info) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "Open dossier for Synthetic alpha" }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".directory-footer")).toHaveCount(0);
  await expect(page.locator(".app-shell > footer")).toBeHidden();
  for (const [width, height] of [
    [1280, 720],
    [1366, 768],
    [1440, 900],
    [1920, 1080],
  ]) {
    await page.setViewportSize({ width, height });
    await expect
      .poll(
        () =>
          page
            .locator("main")
            .evaluate((node) => node.scrollHeight <= node.clientHeight),
        { message: `${width}x${height} homepage must fit` },
      )
      .toBe(true);
    await expect(
      page.getByRole("link", { name: "Open dossier for Synthetic beta" }),
    ).toBeInViewport();
    await page.screenshot({ path: info.outputPath(`home-fit-${width}.png`) });
  }
  const pattern = page.locator('[data-motion-ambient="drift"]');
  expect(
    await pattern.evaluate((node) => Number(getComputedStyle(node).opacity)),
  ).toBeGreaterThanOrEqual(0.6);
  expect(
    await page
      .locator(".home-pattern-region-left")
      .evaluate((node) => getComputedStyle(node).position),
  ).toBe("fixed");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const start = await pattern.evaluate(
    (node) => getComputedStyle(node).transform,
  );
  await expect
    .poll(() => pattern.evaluate((node) => getComputedStyle(node).transform))
    .not.toBe(start);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect
    .poll(() =>
      pattern.evaluate(
        (node) =>
          new DOMMatrixReadOnly(getComputedStyle(node).transform).isIdentity,
      ),
    )
    .toBe(true);
  await page.setViewportSize({ width: 375, height: 667 });
  await expect(
    page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Compare & explore" }),
  ).toBeVisible();
  expect((await auditAccessibility(page)).violations).toEqual([]);
});
