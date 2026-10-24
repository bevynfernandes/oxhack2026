import { auditAccessibility } from "../helpers/accessibility";
import { expect, test } from "@playwright/test";

test("real company publication supports list, source inspection and accessible comparison", async ({
  page,
}, testInfo) => {
  const choicesResponse = await page.request.get("/api/v1/company-snapshots");
  expect(choicesResponse.ok()).toBe(true);
  const choices = await choicesResponse.json();
  expect(choices.items).toHaveLength(1);
  const source = choices.items[0].source;
  expect(source.synthetic).toBe(false);
  const snapshot = choices.items[0].assessment.publication_id;
  const prefix = `/api/v1/company-snapshots/${snapshot}/companies`;
  const rows = (await (await page.request.get(prefix)).json()).items;
  expect(rows.length).toBeGreaterThanOrEqual(2);
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));

  await page.goto("/");
  const firstCompany = rows[0].company.display_name;
  await page.getByLabel("Search companies").fill(firstCompany);
  await expect(
    page.getByRole("link", { name: `Open dossier for ${firstCompany}` }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("real-homepage.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page
    .getByRole("link", { name: `Open dossier for ${firstCompany}` })
    .click();
  await expect(
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
  await page.goto("/explore");
  await page.getByLabel("Assessment snapshot").selectOption(snapshot);
  await expect(
    page.getByText("Synthetic test data.", { exact: true }),
  ).toHaveCount(0);
  for (const row of rows.slice(0, 2)) {
    await expect(
      page.getByRole("link", { name: row.company.display_name, exact: true }),
    ).toBeVisible();
    await page.getByLabel(`Compare ${row.company.display_name}`).check();
  }
  await page.screenshot({
    path: testInfo.outputPath("real-company-list.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.getByRole("link", { name: "Compare selected companies" }).click();
  await expect(
    page.getByRole("heading", { name: "Compare companies" }),
  ).toBeVisible();
  await expect(
    page.getByText("Assessment unavailable", { exact: true }),
  ).toHaveCount(2);
  await expect(
    page.getByText("Stale at assessment date", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("real-company-comparison.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);

  await page
    .getByRole("link", { name: rows[0].company.display_name, exact: true })
    .click();
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
    page.getByRole("link", { name: "Original source (opens new tab)" }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Restricted source. Contents and attachment location are not public.",
    ),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("real-company-profile.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  const before = await (
    await page.request.get(`${prefix}/${rows[0].company.company_id}`)
  ).text();
  expect(before).not.toContain("raw_artifact");
  expect(before).not.toContain("label_state");
  expect(before).not.toContain("success_score");
  await page.reload();
  expect(
    await (
      await page.request.get(`${prefix}/${rows[0].company.company_id}`)
    ).text(),
  ).toBe(before);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(
    `/compare?${new URLSearchParams({ snapshot })}&company=${encodeURIComponent(rows[0].company.company_id)}&company=${encodeURIComponent(rows[1].company.company_id)}`,
  );
  await expect(page.getByRole("table")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const region = page.getByRole("region", { name: "Company comparison" });
  await region.focus();
  await expect(region).toBeFocused();
  await page.screenshot({
    path: testInfo.outputPath("real-company-comparison-mobile.png"),
    fullPage: true,
  });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  expect(requests.every((url) => new URL(url).hostname === "127.0.0.1")).toBe(
    true,
  );
});

test("each company dimension opens the matching backend evidence on desktop and mobile", async ({
  page,
}) => {
  const choices = await (
    await page.request.get("/api/v1/company-snapshots")
  ).json();
  const snapshot = choices.items[0].assessment.publication_id;
  const prefix = "/api/v1/company-snapshots/" + snapshot + "/companies";
  const rows = (await (await page.request.get(prefix)).json()).items;
  const names = [
    "Adoption & Retention",
    "Attention & Sentiment",
    "Financial Health",
    "Industry & Competition",
    "Team & Execution",
  ];
  const mobileNames = ["Adoption", "Attention", "Finance", "Industry", "Team"];
  for (const company of rows) {
    const profile = await (
      await page.request.get(prefix + "/" + company.company.company_id)
    ).json();
    await page.goto(
      "/companies/" + snapshot + "/" + company.company.company_id,
    );
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 800 });
      for (const [index, name] of names.entries()) {
        if (width === 390)
          await page
            .getByRole("group", { name: "Overview dimensions" })
            .getByRole("button", { name: mobileNames[index], exact: true })
            .click();
        const expand = page.getByRole("button", {
          name: "Expand dimension: " + name,
          exact: true,
        });
        await expand.focus();
        await page.keyboard.press("Enter");
        const dialog = page.getByRole("dialog", { name, exact: true });
        await expect(dialog).toBeVisible();
        const section = profile.outlook.specialists[index];
        for (const id of section.metric_observation_ids) {
          const metric = profile.metrics.find(
            (row: { observation_id: string }) => row.observation_id === id,
          );
          const definition = profile.definitions.find(
            (row: { metric_id: string }) => row.metric_id === metric.metric_id,
          );
          await expect(
            dialog.getByText(definition.label, { exact: true }),
          ).toBeVisible();
          if (metric.value?.kind === "decimal")
            await expect(
              dialog.getByText(metric.value.value, { exact: true }),
            ).toBeVisible();
        }
        if (!section.metric_observation_ids.length)
          await expect(
            dialog.getByText("No measurements published"),
          ).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(dialog).not.toBeVisible();
        await expect(expand).toBeFocused();
      }
    }
  }
});
