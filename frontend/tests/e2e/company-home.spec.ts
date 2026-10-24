import AxeBuilder from "@axe-core/playwright";
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
  await expect(
    page.getByRole("link", { name: "Open dossier for Synthetic beta" }),
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
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
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

test("directory pagination keeps every company reachable without growing the viewport", async ({
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
  expect(
    await page.evaluate(() => {
      const main = document.querySelector("main")!;
      const footer = document
        .querySelector(".directory-footer")!
        .getBoundingClientRect();
      return (
        main.scrollHeight <= main.clientHeight &&
        footer.bottom <= main.getBoundingClientRect().bottom
      );
    }),
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
