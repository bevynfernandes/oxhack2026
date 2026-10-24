import { auditAccessibility } from "../helpers/accessibility";
import { expect, test } from "@playwright/test";
import raw from "../../../tests/fixtures/api/scouting.json" with { type: "json" };

const batch = raw.forecast.batch_id;

test("retrospective membership is disclosed in rankings and tool evidence", async ({
  page,
}) => {
  await page.route("**/api/v1/catalog?*", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        membership_basis: "contemporary_reconstruction",
        recorded_at: "2026-10-24T12:00:00Z",
      },
    });
  });
  await page.goto(`/batches/${batch}`);
  await expect(
    page.getByText(/This reconstruction uses a contemporary/),
  ).toBeVisible();
  await page.goto(`/batches/${batch}/tools/tool-1`);
  await expect(
    page.getByText(/Membership uses the contemporary catalogue/),
  ).toBeVisible();
  await expect(
    page.getByText(/Historical membership is unverified/),
  ).toBeVisible();
});

test("complete scouting replay keeps future truth separate and freezes the submitted selection", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("/traction");
  await page.getByRole("link", { name: /Open forecast/ }).click();
  await expect(
    page.getByRole("heading", { name: "Your scouting shortlist" }),
  ).toBeVisible();
  await expect(page.getByText(/Synthetic test data/)).toBeVisible();
  const forecast = await page.request.get(`/api/v1/forecasts/${batch}`);
  const before = await forecast.text();
  expect(before).not.toContain("actual_downloads");
  expect(before).not.toContain("realized_growth");
  await expect(page.getByText("Actual downloads", { exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByLabel("Select Fixture Company 6")).toBeDisabled();
  await expect(page.getByLabel("Select Fixture Company 7")).toBeDisabled();
  await page
    .getByRole("button", { name: "Reveal outcomes", exact: true })
    .click();
  const first = page.getByRole("article", { name: "Scored selection 1" });
  await expect(first).toContainText("Before reveal");
  const blind = await first.getByText(/Frozen organizations/).textContent();
  await page.getByLabel("Select Fixture Company 1").uncheck();
  await page.getByLabel("Select Fixture Company 6").check();
  await page.getByRole("button", { name: "Score a new selection" }).click();
  await expect(
    page.getByRole("article", { name: "Scored selection 2" }),
  ).toContainText("After reveal");
  await expect(first.getByText(/Frozen organizations/)).toHaveText(blind!);
  expect(
    await (await page.request.get(`/api/v1/forecasts/${batch}`)).text(),
  ).toBe(before);
  await page
    .getByRole("link", { name: "Inspect evaluation and baseline comparisons" })
    .click();
  await expect(page.getByText(/Baseline wins/)).toBeVisible();
  await expect(page.getByText(/Coverage gate failed/)).toBeVisible();
  expect(requests.every((url) => new URL(url).hostname === "127.0.0.1")).toBe(
    true,
  );
  expect((await auditAccessibility(page)).violations).toEqual([]);
});

test("detail shows measured zero and missing history, escapes evidence and renders aggregate estimates", async ({
  page,
}, testInfo) => {
  await page.goto(`/batches/${batch}/tools/tool-1`);
  await expect(
    page.getByRole("heading", { name: "Fixture Tool 1", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/No validated prediction interval/),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "0", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Unavailable", exact: true }),
  ).toBeVisible();
  await expect(page.locator("main script")).toHaveCount(0);
  await expect(page.getByText(/<script>alert/).first()).toBeVisible();
  await expect(page.locator(".history-chart svg")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("tool-detail.png"),
    fullPage: true,
  });
});

test("selection survives reload and remains marked informed after an earlier reveal", async ({
  page,
}) => {
  await page.goto(`/batches/${batch}`);
  await page
    .getByRole("button", { name: "Reveal outcomes", exact: true })
    .click();
  await expect(
    page.getByRole("article", { name: "Scored selection 1" }),
  ).toBeVisible();
  await page.getByLabel("Select Fixture Company 1").uncheck();
  await page.getByLabel("Select Fixture Company 6").check();
  await page.reload();
  await expect(page.getByLabel("Select Fixture Company 6")).toBeChecked();
  await expect(page.getByLabel("Select Fixture Company 1")).not.toBeChecked();
  await expect(
    page.getByRole("button", { name: "Score a new selection" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Choose another forecast" }).click();
  await page.getByLabel("Ecosystem", { exact: true }).selectOption("pypi");
  await expect(page.getByText(/No published batches/)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Ecosystem", { exact: true })).toHaveValue(
    "pypi",
  );
});

test("immature reveal and repository failure are actionable and never turn into fixtures", async ({
  page,
}) => {
  await page.route("**/api/v1/replays/*/reveal", (route) =>
    route.fulfill({
      status: 409,
      json: { code: "outcome_immature", message: "Immature" },
    }),
  );
  await page.goto(`/batches/${batch}`);
  await page
    .getByRole("button", { name: "Reveal outcomes", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Complete outcomes are not yet available",
  );
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.route("**/api/v1/cutoffs", (route) =>
    route.fulfill({ status: 503, json: { code: "repository_unavailable" } }),
  );
  await page.goto("/traction");
  await expect(page.getByRole("alert")).toContainText(
    "Published data is unavailable",
  );
  await expect(page.getByRole("link", { name: /Open forecast/ })).toHaveCount(
    0,
  );
  await page.unroute("**/api/v1/cutoffs");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("link", { name: /Open forecast/ })).toBeVisible();
});

test("unknown batch does not silently select a different cutoff", async ({
  page,
}) => {
  await page.goto("/batches/unknown");
  await expect(page.getByRole("alert")).toContainText("not found");
  await expect(
    page.getByRole("heading", { name: "Your scouting shortlist" }),
  ).toHaveCount(0);
});

test("narrow screens, keyboard navigation and reduced motion retain the workflow", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/traction");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await page.getByRole("link", { name: /Open forecast/ }).click();
  await expect(
    page.getByRole("heading", { name: "Your scouting shortlist" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("rankings-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Data health", exact: true }).click();
  await expect(page.getByText("degraded", { exact: true })).toBeVisible();
});

test("rankings and detail satisfy automated accessibility checks", async ({
  page,
}) => {
  await page.goto(`/batches/${batch}`);
  await expect(
    page.getByRole("heading", { name: "Your scouting shortlist" }),
  ).toBeVisible();
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.getByRole("link", { name: "Fixture Tool 1", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Observed history" }),
  ).toBeVisible();
  expect((await auditAccessibility(page)).violations).toEqual([]);
});
