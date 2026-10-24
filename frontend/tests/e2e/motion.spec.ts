import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import fixture from "../../../tests/fixtures/api/research.json" with { type: "json" };

test.use({ video: "on" });
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/research-reports/*", (route) =>
    route.fulfill({ json: fixture }),
  );
  await page.goto(`/research/reports/${fixture.report_id}`);
});

test("spring drawer reverses on Escape, retains focus and survives repeated keyboard tabs", async ({
  page,
}, info) => {
  const opener = page.getByRole("button", {
    name: "Source inventory",
    exact: true,
  });
  for (let index = 0; index < 3; index++) {
    await opener.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(opener).toBeFocused();
  }
  await opener.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("tab").first().focus();
  await page.keyboard.press("End");
  await expect(dialog.getByRole("tab").last()).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("Home");
  await expect(dialog.getByRole("tab").first()).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("motion-drawer.png") });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog).not.toBeVisible();
});

test("reduced motion updates an active modal and keeps mobile and zoom layouts usable", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Source inventory", exact: true })
    .click();
  await page.emulateMedia({ reducedMotion: "reduce" });
  const dialog = page.getByRole("dialog");
  await expect
    .poll(() => dialog.evaluate((node) => getComputedStyle(node).opacity))
    .toBe("1");
  await expect
    .poll(() => dialog.evaluate((node) => getComputedStyle(node).transform))
    .toMatch(/none|matrix\(1, 0, 0, 1, 0, 0\)/);
  await page.evaluate(() => (document.documentElement.style.fontSize = "200%"));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("motion-reduced-mobile.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});
