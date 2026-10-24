import { auditAccessibility } from "../helpers/accessibility";
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
  expect((await auditAccessibility(page)).violations).toEqual([]);
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
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("motion-reduced-mobile.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});

test("disclosures resize while open, become inert on collapse and keep focused content reachable", async ({
  page,
}, info) => {
  await page
    .getByRole("button", { name: "Source inventory", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("tab", { name: "Provenance", exact: true }).click();
  const trigger = dialog.getByRole("button", {
    name: "Snapshot limitations and versions",
    exact: true,
  });
  await trigger.click();
  const panel = page.locator(`#${await trigger.getAttribute("aria-controls")}`);
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await expect(panel).not.toHaveAttribute("inert", "");
  await expect
    .poll(() => panel.evaluate((node) => node.clientHeight))
    .toBeGreaterThan(30);
  const original = await panel.evaluate((node) => node.clientHeight);
  await panel.locator(".motion-disclosure-content").evaluate((node) => {
    const content = document.createElement("p");
    content.textContent =
      "Dynamic evidence remains inside the expanded disclosure. ".repeat(15);
    node.append(content);
  });
  await expect
    .poll(() => panel.evaluate((node) => node.clientHeight))
    .toBeGreaterThan(original + 40);
  await page.screenshot({ path: info.outputPath("disclosure-resized.png") });
  await trigger.click();
  await expect(panel).toHaveAttribute("inert", "");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  await trigger.click();
  await expect.poll(() => panel.evaluate((node) => node.clientHeight)).toBe(0);
  await expect(trigger).toBeFocused();
});

test("selection changes immediately while the shared indicator moves", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Source inventory", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const measurements = dialog.getByRole("tab", {
    name: "Measurements",
    exact: true,
  });
  await measurements.click();
  await expect(measurements).toHaveAttribute("aria-selected", "true");
  await expect(measurements.locator(".motion-indicator")).toHaveCount(1);
  await expect
    .poll(() =>
      measurements.evaluate((button) => {
        const indicator = button
          .querySelector(".motion-indicator")!
          .getBoundingClientRect();
        const bounds = button.getBoundingClientRect();
        return Math.abs(
          (indicator.left + indicator.right - bounds.left - bounds.right) / 2,
        );
      }),
    )
    .toBeLessThan(1);

  await expect(dialog.getByRole("tabpanel")).toHaveAttribute(
    "aria-labelledby",
    (await measurements.getAttribute("id")) || "",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page
    .getByRole("link", { name: "Methodology", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Methodology", exact: true }).first(),
  ).toHaveAttribute("aria-current", "page");
});

test("disabled controls remain still and repeated polling does not animate unchanged states", async ({
  page,
}) => {
  await page.route("**/api/v2/research-capabilities", (route) =>
    route.fulfill({
      json: {
        collection_enabled: false,
        worker_available: false,
        providers: [],
        storage_available: true,
        browser_available: false,
      },
    }),
  );
  await page.goto("/research/new");
  const preview = page.getByRole("button", {
    name: "Preview company",
    exact: true,
  });
  await expect(preview).toBeDisabled();
  await preview.hover();
  await expect
    .poll(() => preview.evaluate((node) => getComputedStyle(node).scale))
    .toMatch(/^(none|1)$/);
  let reads = 0;
  await page.route("**/api/v1/research-jobs/motion-job", (route) => {
    reads++;
    return route.fulfill({
      json: {
        job_id: "motion-job",
        requested_at: "2026-10-24T12:00:00Z",
        finished_at: null,
        state: reads < 3 ? "running" : "completed",
        request: { domain: "alpha.example" },
        sources: [],
        reason_codes: [],
      },
    });
  });
  await page.goto("/research/jobs/motion-job");
  const state = page.getByRole("status");
  await expect(state).toHaveText("Research in progress");
  const tracked = await state.elementHandle();
  await expect.poll(() => reads).toBeGreaterThanOrEqual(2);
  await expect(state).toHaveText("Research in progress");
  expect(await tracked!.evaluate((node) => node.isConnected)).toBe(true);
  expect(
    await state.evaluate(
      (node) => getComputedStyle(node.parentElement!).opacity,
    ),
  ).toBe("1");
  await expect(state).toHaveText("Research complete");
  await expect(page.getByRole("status")).toHaveCount(1);
});

test("native button press springs to its target and releases without delaying activation", async ({
  page,
}) => {
  const opener = page.getByRole("button", {
    name: "Source inventory",
    exact: true,
  });
  await opener.focus();
  await page.keyboard.down("Space");
  await expect
    .poll(() => opener.evaluate((node) => Number(getComputedStyle(node).scale)))
    .toBeLessThan(0.98);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.keyboard.up("Space");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect
    .poll(() => opener.evaluate((node) => Number(getComputedStyle(node).scale)))
    .toBeCloseTo(1, 3);
});
