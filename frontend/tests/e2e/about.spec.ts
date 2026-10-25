import { auditAccessibility } from "../helpers/accessibility";
import { expect, test } from "@playwright/test";

test("About explains the current product without requiring published data", async ({
  page,
}, testInfo) => {
  const apiRequests: string[] = [];
  await page.route(/\/api\/v1\//, async (route) => {
    apiRequests.push(route.request().url());
    await route.abort();
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/about");

  await expect(
    page.getByRole("heading", {
      name: "Startup research with its evidence attached",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "About", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    page.getByRole("heading", { name: "What the Research library does" }),
  ).toBeVisible();
  expect(apiRequests).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("about-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("main")
    .getByRole("link", { name: "Data health", exact: true })
    .click();
  await expect(page).toHaveURL(/\/data-health$/);
});

test("the old methodology address redirects to About", async ({ page }) => {
  await page.goto("/methodology");
  await expect(page).toHaveURL(/\/about$/);
  await expect(
    page.getByRole("heading", {
      name: "Startup research with its evidence attached",
    }),
  ).toBeVisible();
});
