import { auditAccessibility } from "../helpers/accessibility";
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
  await expect(page.getByText("12 months")).toHaveCount(0);
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
  expect((await auditAccessibility(page)).violations).toEqual([]);
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
  expect((await auditAccessibility(page)).violations).toEqual([]);
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

const providers = [
  "website",
  "github",
  "npm",
  "hiring",
  "hn",
  "news",
  "sec",
  "companies_house",
];
const capabilities = {
  storage_available: true,
  collection_enabled: true,
  worker_available: true,
  browser_available: false,
  providers: providers.map((provider) => ({
    provider,
    available: provider !== "sec",
    reason: provider === "sec" ? "Reviewed mapping required" : null,
  })),
};
const standaloneIdentity = {
  identity_id: "identity-example",
  request: { domain: "old.example" },
  state: "ready",
  requested_at: "2026-10-24T17:00:00Z",
  requested_domain: "old.example",
  canonical_domain: "new.example",
  company_name: "Synthetic standalone",
  evidence: [],
  captures: [],
  conflicts: [
    "Homepage redirected from old.example to new.example; confirm this destination explicitly.",
  ],
  limitations: ["Website identity is not legal verification."],
  official_links: [],
  saved_context: null,
};
const sourceStates = providers.map((provider) => ({
  provider,
  name: provider === "hn" ? "Hacker News" : provider,
  state:
    provider === "website"
      ? "completed"
      : provider === "hn"
        ? "partial"
        : "skipped",
  reason_codes:
    provider === "hn"
      ? ["hn_non_exhaustive_or_truncated"]
      : provider === "website"
        ? []
        : ["unverified_account_mapping"],
  captures: [],
  evidence: [],
  observations: [],
  claims: [],
  events: [],
  links: [],
}));
const standaloneReport = {
  schema_version: "research-report-v2",
  report_id: "standalone-report",
  job_id: "standalone-job",
  researched_at: "2026-10-24T17:05:00Z",
  identity: standaloneIdentity,
  sources: sourceStates,
  observations: [
    {
      observation_id: "fresh-count",
      metric_id: "hn_complete_exact_domain_count_30d",
      definition:
        "Complete-window count; retrieved records are separate. Not users or sentiment.",
      unit: "story_links",
      value: null,
      collected_at: "2026-10-24T17:05:00Z",
      missing_reason: "non_exhaustive_or_truncated",
      evidence_ids: [],
      origin: "fresh",
    },
  ],
  claims: [
    {
      claim_id: "claim",
      text: "Company reports growth; no normalized revenue supplied.",
      category: "revenue",
      attribution: "company_reported",
      evidence_ids: [],
      conflicts_with: ["other-claim"],
    },
  ],
  events: [],
  evidence: [],
  captures: [],
  outlook: {
    ...fixture.outlook,
    specialists: fixture.outlook.specialists.map((row) => ({
      ...row,
      metric_observation_ids: [],
      usable_metric_observation_ids: [],
      reason_codes: ["no_approved_metric_group_mapping", "model_not_trained"],
    })),
  },
  limitations: ["Bounded collection; no trained prediction."],
};

test("directory research previews v2 with exact saved context before confirmation", async ({
  page,
}) => {
  let discoveries = 0;
  const jobPosts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("research-jobs")
    ) {
      jobPosts.push(request.url());
    }
  });
  await page.route("**/api/v2/research-capabilities", (route) =>
    route.fulfill({ json: capabilities }),
  );
  await page.route("**/api/v2/research-identities", (route) => {
    discoveries++;
    expect(route.request().postDataJSON()).toEqual({
      domain: "alpha.example",
      company_id: "alpha",
      assessment_publication_id: "synthetic-assessments-v1",
    });
    return route.fulfill({ status: 202, json: standaloneIdentity });
  });
  await page.route("**/api/v2/research-identities/*", (route) =>
    route.fulfill({ json: standaloneIdentity }),
  );
  await page.goto("/");
  const research = page.getByRole("link", {
    name: "Research company Synthetic alpha",
  });
  await expect(research).toHaveAttribute(
    "href",
    "/research/new?domain=alpha.example&company=alpha&publication=synthetic-assessments-v1",
  );
  await research.click();
  await expect(page.getByLabel("Company domain")).toHaveValue("alpha.example");
  expect(discoveries).toBe(0);
  await page.getByRole("button", { name: "Preview company" }).click();
  await expect(page.getByRole("status")).toHaveText("Identity preview ready");
  await expect(
    page.getByRole("button", { name: "Confirm and start research" }),
  ).toBeDisabled();
  expect(discoveries).toBe(1);
  expect(jobPosts).toEqual([]);
});

test("homepage domain discovery bypasses unavailable name lookup, confirms redirected identity, retains partial results and explicitly refreshes", async ({
  page,
}) => {
  let discoveries = 0,
    starts = 0,
    polls = 0;
  await page.route("**/api/v2/research-capabilities", (route) =>
    route.fulfill({ json: capabilities }),
  );
  await page.route("**/api/v2/research-identities", (route) => {
    discoveries++;
    expect(route.request().postDataJSON()).toEqual({ domain: "old.example" });
    return route.fulfill({
      status: 202,
      json: { ...standaloneIdentity, state: "queued" },
    });
  });
  await page.route("**/api/v2/research-identities/*", (route) =>
    route.fulfill({ json: standaloneIdentity }),
  );
  await page.route("**/api/v2/research-jobs", (route) => {
    starts++;
    expect(route.request().postDataJSON()).toEqual({
      identity_id: standaloneIdentity.identity_id,
      identity_confirmed: true,
      profile: starts === 1 ? "deep" : "thorough",
    });
    return route.fulfill({
      status: 202,
      json: {
        job_id: starts === 1 ? "standalone-job" : "refreshed-job",
        state: "queued",
      },
    });
  });
  await page.route("**/api/v2/research-jobs/*", (route) => {
    polls++;
    return route.fulfill({
      json: {
        job_id: "standalone-job",
        identity_id: standaloneIdentity.identity_id,
        state: polls === 1 ? "running" : "partial",
        report_id: polls === 1 ? null : standaloneReport.report_id,
        sources: sourceStates,
        reason_codes: [],
      },
    });
  });
  await page.route("**/api/v2/research-reports/*", (route) =>
    route.fulfill({ json: standaloneReport }),
  );
  let nameLookups = 0;
  await page.route("**/api/v2/company-search", (route) => {
    nameLookups++;
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/");
  await page.getByLabel("Search companies").fill("old.example");
  await expect(
    page.getByRole("link", { name: /Open dossier for/ }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Research company", exact: true })
    .click();
  await expect(page).toHaveURL(/\/research\/identities\/identity-example$/);
  await expect(
    page.getByRole("status").filter({ hasText: "Identity preview ready" }),
  ).toHaveText("Identity preview ready");
  await expect(page.getByText("new.example", { exact: true })).toBeVisible();
  const confirm = page.getByRole("button", {
    name: "Confirm and start research",
  });
  await expect(confirm).toBeDisabled();
  expect(starts).toBe(0);
  await page
    .getByRole("combobox", { name: "Research depth" })
    .selectOption("deep");
  await page.getByRole("checkbox").check();
  await confirm.click();
  await expect(page.getByRole("status")).toHaveText("Research in progress");
  await expect(page.getByRole("status")).toHaveText("Partial results");
  await expect(page.getByText("Hacker News", { exact: true })).toBeVisible();
  await expect(
    page.getByText("unverified account mapping").first(),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open research report" }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic standalone", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  expect(
    await page.locator(".pillar-card").evaluateAll((cards) =>
      cards.every((card) => {
        const bounds = card.getBoundingClientRect();
        const footer = card.querySelector("footer")!.getBoundingClientRect();
        const measurements = card
          .querySelector(".pillar-measurements")!
          .getBoundingClientRect();
        return (
          footer.bottom <= bounds.bottom && measurements.bottom <= footer.top
        );
      }),
    ),
  ).toBe(true);
  await expect(
    page.getByRole("button", { name: "Saved assessment", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Source inventory", exact: true })
    .click();
  await page.getByRole("tab", { name: "Measurements", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByText("Unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText(/Complete-window count/),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Refresh research" }).click();
  expect(starts).toBe(1);
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Confirm and start research" })
    .click();
  await expect(page).toHaveURL(/refreshed-job/);
  expect(starts).toBe(2);
  expect(discoveries).toBe(1);
  expect(nameLookups).toBe(0);
});

test("standalone queue errors never retry POST and disabled collection stays readable", async ({
  page,
}) => {
  let writes = 0;
  await page.route("**/api/v2/research-capabilities", (route) =>
    route.fulfill({ json: capabilities }),
  );
  await page.route("**/api/v2/research-identities", (route) => {
    writes++;
    return route.fulfill({
      status: 429,
      headers: { "Retry-After": "30" },
      json: {},
    });
  });
  await page.goto("/research/new");
  await page.getByLabel("Company domain").fill("new.example");
  await page.getByRole("button", { name: "Preview company" }).click();
  await expect(page.getByRole("alert")).toContainText("Retry after 30 seconds");
  expect(writes).toBe(1);
  await page.route("**/api/v2/research-capabilities", (route) =>
    route.fulfill({
      json: {
        ...capabilities,
        collection_enabled: false,
        worker_available: false,
      },
    }),
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Preview company" }),
  ).toBeDisabled();
  await page.route("**/api/v2/research-reports/*", (route) =>
    route.fulfill({ json: standaloneReport }),
  );
  await page.goto("/research/v2/reports/standalone-report");
  await expect(
    page.getByRole("heading", { name: "Synthetic standalone", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect((await auditAccessibility(page)).violations).toEqual([]);
  await page
    .getByRole("button", { name: "Sources & limitations", exact: true })
    .click();
  expect((await auditAccessibility(page)).violations).toEqual([]);
  expect(writes).toBe(1);
});

test("source drawer wraps focus past collapsed provenance and includes expanded links", async ({
  page,
}) => {
  await page.route("**/api/v2/research-reports/*", (route) =>
    route.fulfill({
      json: {
        ...standaloneReport,
        captures: [
          {
            capture_id: "keyboard-capture",
            final_url: "https://new.example/evidence",
            collected_at: standaloneReport.researched_at,
            parser_version: "test-v1",
            artifact: { sha256: "test-capture-sha256" },
          },
        ],
      },
    }),
  );
  await page.goto("/research/v2/reports/standalone-report");
  await page
    .getByRole("button", { name: "Source inventory", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const close = dialog.getByRole("button", { name: "Close", exact: true });
  const trigger = dialog.getByRole("button", {
    name: "Capture provenance (1)",
  });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await close.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(trigger).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await trigger.click();
  const source = dialog.getByRole("link", { name: "Captured source" });
  await expect(source).toBeVisible();
  await close.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(source).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
});

for (const width of [1440, 375]) {
  test(`source coverage, Gemini accounting and explicit continuation work at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    let submissions = 0;
    await page.route("**/api/v2/research-capabilities", (route) =>
      route.fulfill({ json: capabilities }),
    );
    await page.route("**/api/v2/research-identities/*", (route) =>
      route.fulfill({ json: standaloneIdentity }),
    );
    await page.route("**/api/v2/research-jobs/progress", (route) =>
      route.fulfill({
        json: {
          job_id: "progress",
          identity_id: standaloneIdentity.identity_id,
          state: "partial",
          sources: sourceStates.map((source) =>
            source.provider === "website"
              ? {
                  ...source,
                  details: {
                    execution: "completed",
                    applicability: "applicable",
                    scope: "planned_sample",
                    coverage: "limited",
                    collected: 20,
                    outstanding: 1,
                    frontier: [{ url: "https://new.example/about", depth: 1 }],
                    visited: [],
                    accounts: [],
                    retained_capture_ids: [],
                    issues: [
                      {
                        code: "website_page_limit",
                        severity: "warning",
                        message: "The selected company-page limit was reached.",
                        remedy: "Continue research to collect remaining pages.",
                      },
                    ],
                  },
                }
              : source,
          ),
          reason_codes: [],
          mapping: {
            state: "partial",
            completed_batches: 4,
            reason_codes: [],
            statistics: {
              mode: "rules_gemini",
              model: "acceptance-model",
              stage: "finished",
              candidates: 100,
              processed: 60,
              deferred: 40,
              batches: 4,
              failed_batches: 0,
              cached_batches: 3,
              provider_requests: 1,
              accepted_proposals: 7,
              rejected_proposals: 2,
              input_tokens: null,
              output_tokens: null,
            },
          },
        },
      }),
    );
    await page.route("**/api/v2/research-jobs/progress/continue", (route) => {
      submissions++;
      expect(route.request().postDataJSON()).toEqual({ profile: "deep" });
      return route.fulfill({ status: 202, json: { job_id: "continued" } });
    });
    await page.route("**/api/v2/research-jobs/continued", (route) =>
      route.fulfill({
        json: {
          job_id: "continued",
          identity_id: standaloneIdentity.identity_id,
          state: "queued",
          sources: [],
          reason_codes: [],
        },
      }),
    );
    await page.goto("/research/v2/jobs/progress");
    await expect(
      page.getByText("Coverage: limited · planned sample"),
    ).toBeVisible();
    await expect(
      page.getByText(/1 new provider requests · 3 cached batches/),
    ).toBeVisible();
    await expect(
      page.getByText(/input not reported, output not reported/),
    ).toBeVisible();
    expect(submissions).toBe(0);
    const profile = page.getByRole("combobox", { name: "Research depth" });
    await profile.selectOption("deep");
    expect((await auditAccessibility(page)).violations).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("research-progress.png"),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Continue research", exact: true })
      .click();
    await expect(page).toHaveURL(/\/jobs\/continued$/);
    await expect(page.getByRole("status")).toHaveText("Queued");
    expect(submissions).toBe(1);
  });
}
