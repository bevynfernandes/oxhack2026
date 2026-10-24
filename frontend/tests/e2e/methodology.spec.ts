import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("methodology remains accessible on mobile while published data is unavailable", async ({
  page,
}, testInfo) => {
  const apiRequests: string[] = [];
  await page.route(/\/api\/v1\//, async (route) => {
    apiRequests.push(route.request().url());
    await route.abort();
  });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/methodology");

  await expect(
    page.getByRole("heading", { name: "How to read a company outlook" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Methodology", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    page.getByRole("heading", {
      name: "Cash-flow self-sufficiency · 12 months",
    }),
  ).toBeVisible();
  expect(apiRequests).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("methodology-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Data health", exact: true }).click();
  await expect(page).toHaveURL(/\/data-health$/);
});
