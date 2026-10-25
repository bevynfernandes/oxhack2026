import { expect, test } from "@playwright/test";
import fixture from "../../../tests/fixtures/api/research.json" with { type: "json" };
import { auditAccessibility } from "../helpers/accessibility";
const saved = "/companies/synthetic-assessments-v1/alpha";
const report = "/research/reports/" + fixture.report_id;
for (const width of [1440, 375]) {
  test(`research notes, history and mixed comparison remain usable at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/v1/research-reports/*", (route) =>
      route.fulfill({ json: fixture }),
    );
    await page.goto(saved);
    const trigger = page.getByRole("button", {
      name: "Decision summary & notes",
    });
    await trigger.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("coverage, not confidence");
    await page.getByLabel("Keep on my watchlist").check();
    await page
      .getByLabel("Research notes")
      .fill("Verify paying customer retention");
    await page.getByLabel("Review date (UTC)").fill("2026-10-26");
    await page
      .getByRole("button", { name: "Save notes and watchlist" })
      .click();
    await expect(dialog.getByRole("status")).toHaveText(
      "Saved in this browser.",
    );
    expect((await auditAccessibility(page)).violations).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await page.reload();
    await trigger.click();
    await expect(page.getByLabel("Research notes")).toHaveValue(
      "Verify paying customer retention",
    );
    await page.keyboard.press("Escape");
    await page.goto(report);
    await expect(trigger).toBeVisible();
    await page
      .getByRole("link", { name: "Compare & explore", exact: true })
      .click();
    const library = page.getByRole("region", { name: "Your research" });
    await expect(library).toContainText("Verify paying customer retention");
    await library.getByLabel("Watchlist only").check();
    await expect(
      library.getByRole("checkbox", { name: /Compare research for/ }),
    ).toHaveCount(1);
    await library.getByRole("searchbox").fill("Synthetic");
    await library.getByRole("button", { name: "Save this search" }).click();
    await page.reload();
    await library
      .getByRole("button", { name: "Use search: Synthetic · Watchlist" })
      .click();
    await expect(library.getByLabel("Watchlist only")).toBeChecked();
    await expect(library.getByRole("searchbox")).toHaveValue("Synthetic");
    await library.getByRole("searchbox").fill("");
    await library.getByLabel("Watchlist only").uncheck();
    const checks = library.getByRole("checkbox", {
      name: /Compare research for/,
    });
    await expect(checks).toHaveCount(2);
    await checks.nth(0).check();
    await checks.nth(1).check();
    await page.getByRole("link", { name: "Compare research (2)" }).click();
    await expect(
      page.getByRole("region", { name: "Research evidence comparison" }),
    ).toBeVisible();
    await expect(page.getByText(/Research date:/)).toHaveCount(2);
    await expect(
      page.getByText(/No validated success probabilities/),
    ).toBeVisible();
    await page
      .getByRole("button", { name: /Measurements/ })
      .first()
      .click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect((await auditAccessibility(page)).violations).toEqual([]);
  });
}
test("invalid, failed, empty and blocked-storage paths stay explicit", async ({
  page,
}) => {
  await page.goto("/explore");
  await expect(page.getByText(/No research history yet/)).toBeVisible();
  await page.goto(
    "/compare?record=https://evil.test&record=/research/v2/jobs/one",
  );
  await expect(page.getByRole("alert")).toContainText(
    "Choose two or three distinct dossiers",
  );
  await page.route("**/api/v1/research-reports/*", (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  await page.goto(
    `/compare?${new URLSearchParams([
      ["record", saved],
      ["record", report],
    ])}`,
  );
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Research evidence comparison" }),
  ).toHaveCount(0);
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new Error("Blocked");
    };
  });
  await page.goto(saved);
  await page.getByRole("button", { name: "Decision summary & notes" }).click();
  await page.getByLabel("Research notes").fill("Keep me");
  await page.getByRole("button", { name: "Save notes and watchlist" }).click();
  await expect(page.getByRole("dialog").getByRole("status")).toContainText(
    "Could not save",
  );
  await expect(page.getByLabel("Research notes")).toHaveValue("Keep me");
});
