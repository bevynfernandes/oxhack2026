import { expect, test, type Page } from "@playwright/test";
import { auditAccessibility } from "../helpers/accessibility";

test.use({ video: "on" });
async function settled(page: Page) {
  await expect
    .poll(() =>
      page.locator("main").evaluate((node) => {
        const style = getComputedStyle(node);
        return (
          style.opacity === "1" &&
          new DOMMatrixReadOnly(style.transform).f === 0
        );
      }),
    )
    .toBe(true);
}

test("route navigation springs the page while retaining a single accessible main and fixed header", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByLabel("Search companies")).toBeVisible();
  await settled(page);
  const header = await page.locator("header.site-header").boundingBox();
  const samples = await page.evaluate(async () => {
    const link = Array.from(
      document.querySelectorAll<HTMLAnchorElement>("nav a"),
    ).find((link) => link.textContent === "Methodology")!;
    link.click();
    const values: number[] = [];
    for (let i = 0; i < 24; i++) {
      await new Promise(requestAnimationFrame);
      values.push(
        new DOMMatrixReadOnly(
          getComputedStyle(document.querySelector("main")!).transform,
        ).f,
      );
    }
    return values;
  });
  expect(samples.some((value) => value > 1)).toBe(true);
  await expect(page).toHaveURL(/\/methodology$/);
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page.getByRole("main")).toBeFocused();
  await settled(page);
  expect(await page.locator("header.site-header").boundingBox()).toEqual(
    header,
  );
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("page-methodology.png") });
});

test("rapid navigation and browser back/forward settle on the current route", async ({
  page,
}) => {
  await page.goto("/");
  const main = await page.locator("main").elementHandle();
  await page
    .getByRole("link", { name: "Methodology", exact: true })
    .first()
    .click();
  await page
    .getByRole("link", { name: "Compare & explore", exact: true })
    .click();
  await page.getByRole("link", { name: "Companies", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByLabel("Search companies")).toBeVisible();
  await settled(page);
  expect(await main!.evaluate((node) => node.isConnected)).toBe(true);
  await page.goBack();
  await expect(page).toHaveURL(/\/explore$/);
  await settled(page);
  await page.goForward();
  await expect(page).toHaveURL(/\/$/);
  await settled(page);
  await expect(page.getByRole("main")).toHaveCount(1);
});

test("same-page filters and hashes retain focus and do not replay the page entrance", async ({
  page,
}) => {
  await page.goto("/");
  const input = page.getByLabel("Search companies");
  await input.fill("alpha");
  await expect(input).toBeFocused();
  await settled(page);
  await input.fill("beta");
  await expect(input).toBeFocused();
  expect(
    await page
      .locator("main")
      .evaluate((node) => getComputedStyle(node).opacity),
  ).toBe("1");
  await page.evaluate(() => {
    location.hash = "main";
  });
  await settled(page);
  expect(
    await page
      .locator("main")
      .evaluate((node) => getComputedStyle(node).transform),
  ).toMatch(/none|matrix\(1, 0, 0, 1, 0, 0\)/);
});

test("reduced motion remains immediate during route changes and a live preference change", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("link", { name: "Methodology", exact: true })
    .first()
    .click();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await settled(page);
  await page.getByRole("link", { name: "Companies", exact: true }).click();
  await expect(page.getByLabel("Search companies")).toBeVisible();
  await settled(page);
  await page.setViewportSize({ width: 375, height: 667 });
  await page
    .getByRole("link", {
      name: "Open dossier for Synthetic alpha",
      exact: true,
    })
    .click();
  await settled(page);
  await expect(
    page.getByRole("heading", { name: "Synthetic alpha", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <= innerWidth &&
        document.documentElement.scrollHeight <= innerHeight,
    ),
  ).toBe(true);
  expect((await auditAccessibility(page)).violations).toEqual([]);
});
