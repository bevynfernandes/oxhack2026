import { expect, test } from "@playwright/test";
import { auditAccessibility } from "../helpers/accessibility";

for (const name of ["Qdrant", "Weaviate"]) {
  test(`${name} opens all five populated views with source-backed local inference`, async ({
    page,
  }, info) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/");
    await page.getByLabel("Search companies").fill(name);
    await page.getByRole("link", { name: `Open dossier for ${name}` }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "What the evidence tells us" }),
    ).toBeVisible();
    const meters = page.getByRole("meter");
    await expect(meters).toHaveCount(3);
    const scores = name === "Qdrant" ? [76, 84, 58] : [72, 86, 60];
    for (let index = 0; index < scores.length; index++) {
      await expect(meters.nth(index)).toHaveAttribute(
        "aria-valuenow",
        String(scores[index]),
      );
    }
    await expect(
      page.getByText("AI outlook estimate", { exact: true }),
    ).toHaveCount(3);
    for (const group of [
      "Adoption & Retention",
      "Attention & Sentiment",
      "Financial Health",
      "Industry & Competition",
      "Team & Execution",
    ]) {
      await page
        .getByRole("button", { name: `Expand dimension: ${group}` })
        .click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await expect(
        dialog.getByText("Data: Evidence available", { exact: false }),
      ).toBeVisible();
      if (group === "Adoption & Retention") {
        await expect(dialog.getByText(/SDK demand percentile:/)).toBeVisible();
      }
      if (group === "Attention & Sentiment") {
        await expect(dialog.getByText(/Title sentiment index:/)).toBeVisible();
        await expect(
          dialog.getByRole("link", {
            name: "Classified source title (opens new tab)",
          }),
        ).toHaveCount(5);
      }
      if (group === "Financial Health") {
        await expect(dialog.getByText("Missing", { exact: true })).toHaveCount(
          2,
        );
        await expect(
          dialog.getByText(
            /public issuer model not validated for private startups/i,
          ),
        ).toBeVisible();
      }
      await page.keyboard.press("Escape");
      await expect(dialog).not.toBeVisible();
    }
    expect((await auditAccessibility(page)).violations).toEqual([]);
    await page
      .getByRole("heading", { name, exact: true })
      .scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath(`${name}-desktop.png`),
      fullPage: true,
    });
    await page
      .getByRole("heading", { name: "Three perspectives on what comes next" })
      .scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath(`${name}-outlooks-desktop.png`),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole("heading", { name, exact: true })
      .scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath(`${name}-mobile.png`),
      fullPage: true,
    });
    await page
      .getByRole("heading", { name: "Growth outlook", exact: true })
      .scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath(`${name}-outlooks-mobile.png`),
    });
    expect((await auditAccessibility(page)).violations).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("both packaged companies compare without collecting sources", async ({
  page,
}, info) => {
  const choices = await (
    await page.request.get("/api/v1/company-snapshots")
  ).json();
  const snapshot = choices.items[0].assessment.publication_id;
  await page.goto(
    `/compare?snapshot=${snapshot}&company=qdrant&company=weaviate`,
  );
  await expect(
    page.getByRole("heading", { name: "Compare companies" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Qdrant", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Weaviate", exact: true }),
  ).toBeVisible();
  const table = page.getByRole("table");
  await expect(table.locator("tr[data-metric-id]")).toHaveCount(11);
  await expect(
    table.getByRole("row", { name: /^Growth outlook/ }),
  ).toContainText("76");
  await expect(
    table.getByRole("row", { name: /^Growth outlook/ }),
  ).toContainText("72");
  await expect(
    table.getByRole("row", { name: /^SDK demand index/ }),
  ).toContainText("34.8");
  await expect(
    table.getByRole("row", { name: /^SDK demand index/ }),
  ).toContainText("34.2");
  await expect(table.getByRole("cell", { name: /^Missing/ })).toHaveCount(6);
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("comparison-desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: info.outputPath("comparison-mobile.png") });
  const records = new URLSearchParams();
  records.append("record", `/companies/${snapshot}/qdrant`);
  records.append("record", `/companies/${snapshot}/weaviate`);
  await page.goto(`/compare?${records}`);
  await expect(
    page.getByRole("heading", { name: "Compare companies" }),
  ).toBeVisible();
  await expect(
    page.getByRole("table").locator("tr[data-metric-id]"),
  ).toHaveCount(11);
});
