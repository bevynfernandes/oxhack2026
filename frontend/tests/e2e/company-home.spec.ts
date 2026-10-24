import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("company homepage searches and opens a saved analysis with keyboard", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Look beyond the hype." }),
  ).toBeVisible();
  await page.getByLabel("Search companies").fill("no-such-company");
  await expect(page.getByText(/No companies match your search/)).toBeVisible();
  await page.getByLabel("Search companies").fill("alpha");
  const analysis = page.getByRole("link", {
    name: "View saved analysis for Synthetic alpha",
  });
  await expect(analysis).toBeVisible();
  await expect(
    page.getByRole("link", { name: "View saved analysis for Synthetic beta" }),
  ).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
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
    page.getByRole("heading", { name: "Company outlook" }),
  ).toBeVisible();
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
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
