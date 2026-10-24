import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixture from "../../../tests/fixtures/api/research.json" with { type: "json" };

const reportUrl = "/research/reports/" + fixture.report_id;
async function serveReport(page: Page, legacy = false) {
  const report = structuredClone(fixture);
  if (legacy) delete (report.outlook as { forecasts?: unknown }).forecasts;
  await page.route("**/api/v1/research-reports/*", (route) =>
    route.fulfill({ json: report }),
  );
}

test("prediction workspace exposes three outcomes, five drivers and accessible evidence details", async ({
  page,
}, info) => {
  await serveReport(page);
  await page.goto(reportUrl);
  await expect(
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
  await expect(page.getByText("24 months")).toHaveCount(2);
  await expect(page.getByText("12 months")).toBeVisible();
  await expect(page.getByText(/Partial source results/)).toBeVisible();
  const downloadReady = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export report" }).click();
  const download = await downloadReady;
  await download.saveAs(info.outputPath("exported-report.json"));
  const stream = await download.createReadStream();
  let exported = "";
  for await (const chunk of stream) exported += chunk.toString();
  expect(JSON.parse(exported)).toEqual(fixture);
  const inspect = page.getByRole("button", {
    name: "Inspect evidence: Attention & Sentiment",
  });
  await page
    .getByRole("button", { name: "Expand dimension: Attention & Sentiment" })
    .click();
  await page.keyboard.press("Escape");
  await inspect.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(
    dialog.getByText("Fresh collection · story links"),
  ).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  expect(
    await dialog.evaluate((el) => el.contains(document.activeElement)),
  ).toBe(true);
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
  await dialog
    .getByRole("tab", { name: "Financial Health", exact: true })
    .click();
  await expect(dialog.getByText(/Saved context/).first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(inspect).toBeFocused();
  await page.screenshot({
    path: info.outputPath("workspace-desktop.png"),
    fullPage: true,
  });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "";
  });
  for (const width of [768, 390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: info.outputPath("workspace-mobile.png"),
    fullPage: true,
  });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("group", { name: "Overview dimensions" })
    .getByRole("button", { name: "Attention", exact: true })
    .click();
  await inspect.click();
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await expect(
    dialog.getByRole("tab", { name: "Attention & Sentiment" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("driver-mobile.png"),
    fullPage: false,
  });
});

test("dossier overview fits laptop and mobile viewports without scrolling or overlapping metrics", async ({
  page,
}) => {
  await serveReport(page);
  await page.goto(reportUrl);
  await expect(
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
  for (const [width, height] of [
    [1440, 900],
    [1366, 768],
    [1280, 720],
    [390, 844],
    [375, 667],
  ]) {
    await page.setViewportSize({ width, height });
    const layout = await page.evaluate(() => {
      const main = document.querySelector("main")!;
      const ledger = document
        .querySelector(".dossier-ledger")!
        .getBoundingClientRect();
      const cards = [
        ...document.querySelectorAll<HTMLElement>(".pillar-card"),
      ].filter((el) => el.getClientRects().length > 0);
      return {
        pageFits:
          document.documentElement.scrollHeight <= innerHeight &&
          document.documentElement.scrollWidth <= innerWidth,
        mainFits: main.scrollHeight <= main.clientHeight,
        ledgerVisible: ledger.bottom <= innerHeight - 24,
        cardsFit: cards.every((card) => {
          const metrics = card
            .querySelector(".pillar-measurements")!
            .getBoundingClientRect();
          const footer = card.querySelector("footer")!.getBoundingClientRect();
          return metrics.bottom <= footer.top && footer.bottom <= ledger.top;
        }),
      };
    });
    expect(layout, `${width}x${height}`).toEqual({
      pageFits: true,
      mainFits: true,
      ledgerVisible: true,
      cardsFit: true,
    });
  }
});

test("legacy reports retain original meanings and unavailable reports show a retry", async ({
  page,
}) => {
  await serveReport(page, true);
  await page.goto(reportUrl);
  await expect(page.getByText(/Legacy report:/)).toBeVisible();
  await expect(page.getByText("24 months")).toHaveCount(0);
  await page.route("**/api/v1/research-reports/*", (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("not found");
});

test("research requires confirmation and polls actual queued/running/partial states", async ({
  page,
}) => {
  let writes = 0;
  let reads = 0;
  const job = {
    schema_version: "research-job-v1",
    job_id: "ui-job",
    request: {
      assessment_publication_id: "synthetic-assessments-v1",
      company_id: "alpha",
      domain: "alpha.example",
      identity_confirmed: true,
    },
    requested_at: "2026-10-24T17:00:00Z",
    sources: [{ provider: "hn_algolia", state: "pending", reason_codes: [] }],
    reason_codes: [],
    report_id: null,
  };
  await page.route("**/api/v1/research-jobs", async (route) => {
    writes++;
    expect(route.request().postDataJSON()).toEqual(job.request);
    await route.fulfill({ status: 202, json: { ...job, state: "queued" } });
  });
  await page.route("**/api/v1/research-jobs/ui-job", (route) => {
    reads++;
    const state = reads === 1 ? "queued" : reads === 2 ? "running" : "partial";
    return route.fulfill({
      json: {
        ...job,
        state,
        report_id: state === "partial" ? fixture.report_id : null,
        sources: [
          {
            provider: "hn_algolia",
            state: state === "queued" ? "pending" : state,
            reason_codes: [],
          },
        ],
      },
    });
  });
  await serveReport(page);
  await page.goto("/research/new/synthetic-assessments-v1/alpha");
  const start = page.getByRole("button", {
    name: "Confirm and start research",
  });
  await expect(start).toBeDisabled();
  expect(writes).toBe(0);
  await page.getByRole("checkbox").check();
  await start.click();
  await expect(page.getByRole("status")).toHaveText("Queued");
  await expect(page.getByRole("status")).toHaveText("Research in progress");
  await expect(page.getByRole("status")).toHaveText("Partial results");
  expect(writes).toBe(1);
  await page.getByRole("link", { name: "Open research report" }).click();
  await expect(
    page.getByRole("heading", { name: "Overall outlook unavailable" }),
  ).toBeVisible();
});

test("identity and service failures are actionable without automatic resubmission", async ({
  page,
}) => {
  let status = 409;
  let writes = 0;
  await page.route("**/api/v1/research-jobs", (route) => {
    writes++;
    return route.fulfill({ status, json: { detail: "private diagnostic" } });
  });
  await page.goto("/research/new/synthetic-assessments-v1/alpha");
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Confirm and start research" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "identity could not be confirmed",
  );
  expect(writes).toBe(1);
  status = 503;
  await page
    .getByRole("button", { name: "Confirm and start research" })
    .click();
  await expect(page.getByRole("alert")).toContainText("local research service");
  await expect(page.getByText("private diagnostic")).toHaveCount(0);
  expect(writes).toBe(2);
});

test("terminal failed and completed jobs remain distinct from model readiness", async ({
  page,
}) => {
  let state = "failed";
  await page.route("**/api/v1/research-jobs/terminal", (route) =>
    route.fulfill({
      json: {
        job_id: "terminal",
        state,
        request: {
          assessment_publication_id: "synthetic-assessments-v1",
          company_id: "alpha",
          domain: "alpha.example",
          identity_confirmed: true,
        },
        requested_at: "2026-10-24T17:00:00Z",
        finished_at: "2026-10-24T17:01:00Z",
        report_id: state === "completed" ? fixture.report_id : null,
        reason_codes: [],
        sources: [
          {
            provider: "hn_algolia",
            state: state === "completed" ? "succeeded" : "failed",
            reason_codes: [],
          },
        ],
      },
    }),
  );
  await page.goto("/research/jobs/terminal");
  await expect(page.getByRole("status")).toHaveText("Research failed");
  await expect(
    page.getByRole("link", { name: "Confirm a new research job" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open research report" }),
  ).toHaveCount(0);
  state = "completed";
  await page.reload();
  await expect(page.getByRole("status")).toHaveText("Research complete");
  await expect(
    page.getByRole("link", { name: "Open research report" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Model readiness is shown separately/),
  ).toBeVisible();
});
