import { auditAccessibility } from "../helpers/accessibility";
import { expect, test } from "@playwright/test";

const snapshot = "synthetic-assessments-v1";
const listUrl = `/explore?snapshot=${snapshot}`;

test("company research searches, inspects sources and compares the same published profiles", async ({
  page,
}, testInfo) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("/explore");
  await expect(
    page.getByRole("heading", { name: "Research library", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Assessment snapshot").selectOption(snapshot);
  await expect(
    page.getByRole("status").filter({ hasText: "2 of 2 companies" }),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic test data.", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search companies").fill("beta");
  await expect(page).toHaveURL(/q=beta/);
  await expect(
    page.getByRole("link", { name: "Synthetic alpha", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Search companies")).toHaveValue("beta");
  await page.getByLabel("Search companies").fill("");
  await page
    .getByRole("combobox", { name: "Stage", exact: true })
    .selectOption("unknown");
  await page.getByLabel("Evidence coverage").selectOption("gaps");
  await page.getByLabel("Compare Synthetic alpha").check();
  await page.getByLabel("Compare Synthetic beta").check();
  await page.getByRole("link", { name: "Compare selected companies" }).click();
  await expect(
    page.getByRole("heading", { name: "Compare companies" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Stage or business model differs or is unknown/),
  ).toBeVisible();
  const table = page.getByRole("table");
  await expect(
    table.getByRole("columnheader", { name: "Synthetic alpha" }),
  ).toBeVisible();
  await expect(
    table.getByRole("columnheader", { name: "Synthetic beta" }),
  ).toBeVisible();
  await expect(table.getByRole("cell", { name: /^Missing/ })).toHaveCount(2);
  await expect(table.getByRole("cell", { name: /^0/ }).first()).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("company-compare.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page
    .getByRole("link", { name: "Synthetic alpha", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Saved assessment", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cash-flow self-sufficiency" }),
  ).toBeVisible();
  await expect(
    page.getByText("Assessment unavailable", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Inspect \d+ supporting source/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Original source (opens new tab)" }),
  ).toBeVisible();
  await expect(page.getByText(/platform observed · verified/)).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("company-profile.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  expect(requests.every((url) => new URL(url).hostname === "127.0.0.1")).toBe(
    true,
  );
  const response = await page.request.get(
    `/api/v1/company-snapshots/${snapshot}/companies/alpha`,
  );
  const payload = await response.text();
  for (const forbidden of [
    "raw_artifact",
    "locator",
    "label_state",
    "success_score",
  ])
    expect(payload).not.toContain(forbidden);
});

test("company errors, unknown publications and invalid comparison selection are explicit", async ({
  page,
}) => {
  await page.goto("/explore?snapshot=unknown");
  await expect(page.getByRole("alert")).toContainText("not found");
  await expect(
    page.getByRole("link", { name: "Synthetic alpha", exact: true }),
  ).toHaveCount(0);
  await page.goto(`/compare?snapshot=${snapshot}&company=alpha&company=alpha`);
  await expect(page.getByRole("alert")).toContainText("distinct companies");
  await page.goto(
    `/compare?snapshot=${snapshot}&company=alpha&company=unknown`,
  );
  await expect(page.getByRole("alert")).toContainText("not found");
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.route("**/api/v1/company-snapshots", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page.goto("/explore");
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("company tables and comparison remain usable on narrow screens with a three-company cap", async ({
  page,
}, testInfo) => {
  await page.route(
    `**/api/v1/company-snapshots/${snapshot}/companies`,
    async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const extra = ["gamma", "delta"].map((id) => ({
        ...body.items[0],
        company: {
          ...body.items[0].company,
          company_id: id,
          display_name: `Synthetic ${id}`,
        },
      }));
      await route.fulfill({
        response,
        json: { ...body, items: [...body.items, ...extra] },
      });
    },
  );
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(listUrl);
  await page.getByLabel("Compare Synthetic alpha").check();
  await page.getByLabel("Compare Synthetic beta").check();
  await page.getByLabel("Compare Synthetic gamma").check();
  await expect(page.getByLabel("Compare Synthetic delta")).toBeDisabled();
  await page.getByLabel("Compare Synthetic gamma").uncheck();
  await page.getByRole("link", { name: "Compare selected companies" }).click();
  await expect(
    page.getByRole("heading", { name: "Compare companies" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("region", { name: "Company comparison" }).focus();
  await expect(
    page.getByRole("region", { name: "Company comparison" }),
  ).toBeFocused();
  await page.screenshot({
    path: testInfo.outputPath("company-compare-mobile.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
});
