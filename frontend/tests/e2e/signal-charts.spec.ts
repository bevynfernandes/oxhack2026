import { expect, test } from "@playwright/test";
import fixture from "../../../tests/fixtures/api/research.json" with { type: "json" };
import { auditAccessibility } from "../helpers/accessibility";

for (const width of [1440, 375]) {
  test(`signal charts distinguish observations, estimates and missing data at ${width}px`, async ({
    page,
  }) => {
    const profile = {
      ...fixture.inventory.saved_context,
      metrics: [
        [
          "previous",
          "npm_downloads_previous_30d_v1",
          2000,
          "2026-08-25",
          "2026-09-24",
        ],
        ["current", "npm_downloads_30d_v1", 3000, "2026-09-24", "2026-10-24"],
      ].map(([id, metric, value, start, end]) => ({
        observation_id: id,
        metric_id: metric,
        company_id: "alpha",
        value: { kind: "integer", value },
        state: "observed",
        reason: null,
        evidence_ids: [],
        measured_at: null,
        window: { start: `${start}T00:00:00Z`, end: `${end}T00:00:00Z` },
        available_at: "2026-10-24T00:00:00Z",
        collected_at: "2026-10-24T00:00:00Z",
      })),
      definitions: [
        "npm_downloads_previous_30d_v1",
        "npm_downloads_30d_v1",
      ].map((metric_id) => ({
        metric_id,
        family: "traction",
        label: metric_id,
        definition: "Synthetic test downloads",
        unit: "downloads",
        value_kind: "integer",
        scope: "product",
        applicability: "Test only",
        maximum_age_days: 35,
        currency: null,
      })),
      dimension_models: {
        schema_version: "experimental-dimensions-v1",
        company_id: "alpha",
        source_snapshot_id: "synthetic-companies-v1",
        as_of: "2026-10-24T00:00:00Z",
        model_bundle_sha256: "a".repeat(64),
        dimensions: [
          {
            group_id: "adoption_retention",
            architecture: "Ridge",
            model_status: "experimental_trained",
            model_sha256: "b".repeat(64),
            eligibility: "eligible",
            score: 34.2,
            predicted_value: Math.log(4001 / 3001),
            prediction_unit: "log download growth",
            metric_observation_ids: ["previous", "current"],
            target: "SDK download growth",
            limitations: ["Test fixture, not company success"],
            reason_codes: [],
          },
        ],
      },
    };
    let empty = false;
    await page.route("**/api/v1/company-snapshots/*/companies/alpha", (route) =>
      route.fulfill({
        json: empty
          ? { ...profile, metrics: [], dimension_models: null }
          : profile,
      }),
    );
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/companies/synthetic-assessments-v1/alpha");
    const chart = page.getByRole("region", { name: "SDK download chart" });
    await expect(chart.getByText("2,000", { exact: true })).toBeVisible();
    await expect(chart.getByText("≈ 4,000")).toBeVisible();
    await expect(
      chart.getByText(/uncertainty interval unavailable/),
    ).toBeVisible();
    const disclosure = chart.getByRole("button", {
      name: "How to read this estimate",
    });
    await disclosure.focus();
    await page.keyboard.press("Enter");
    await expect(disclosure).toHaveAttribute("aria-expanded", "true");
    await expect(
      chart.getByText(/not a probability or confidence rating/),
    ).toBeVisible();
    const evidence = chart.getByRole("button", {
      name: "Inspect chart evidence",
    });
    await evidence.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(evidence).toBeFocused();
    expect((await auditAccessibility(page)).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    empty = true;
    await page.reload();
    await expect(chart.getByText(/missing data is not zero/)).toBeVisible();
    await expect(chart.getByText("≈ 4,000")).toHaveCount(0);
  });
}
