import { expect, test } from "@playwright/test";

const icon =
  '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><path d="M8 4h4v24H8zm12 0h4v24h-4z"/></svg>';

for (const domain of ["elevenlabs.io", "github.com"]) {
  test(`research spinner centres ${domain}'s favicon and stops for reduced motion`, async ({
    page,
  }, info) => {
    let state = "running";
    await page.route("**/api/v2/research-jobs/spinner-job", (route) =>
      route.fulfill({
        json: {
          job_id: "spinner-job",
          identity_id: "spinner-identity",
          state,
          requested_at: "2026-10-25T00:00:00Z",
          sources: [],
          reason_codes: [],
        },
      }),
    );
    await page.route(
      "**/api/v2/research-identities/spinner-identity",
      (route) =>
        route.fulfill({
          json: {
            identity_id: "spinner-identity",
            canonical_domain: domain,
          },
        }),
    );
    await page.route(`https://${domain}/favicon.ico`, (route) => route.abort());
    const favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
    await page.route(favicon, (route) =>
      route.fulfill({ contentType: "image/svg+xml", body: icon }),
    );
    await page.goto("/research/v2/jobs/spinner-job");
    await expect(page.getByRole("status")).toHaveText("Research in progress");
    const image = page.locator(".company-spinner__favicon img");
    await expect(image).toHaveAttribute("src", favicon);
    await expect
      .poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth))
      .toBeGreaterThan(0);
    const ring = page.locator(".company-spinner__ring");
    await expect
      .poll(() => ring.evaluate((node) => getComputedStyle(node).animationName))
      .toBe("company-spinner-orbit");
    const offset = await image.evaluate((node) => {
      const image = node.getBoundingClientRect();
      const spinner = node.closest(".company-spinner")!.getBoundingClientRect();
      return (
        Math.abs(image.x + image.width / 2 - spinner.x - spinner.width / 2) +
        Math.abs(image.y + image.height / 2 - spinner.y - spinner.height / 2)
      );
    });
    expect(offset).toBeLessThan(1);
    await page.screenshot({ path: info.outputPath(`${domain}-spinner.png`) });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect
      .poll(() => ring.evaluate((node) => getComputedStyle(node).animationName))
      .toBe("none");
    await expect(image).toBeVisible();
    state = "completed";
    await expect(page.getByRole("status")).toHaveText("Research complete");
    await expect(page.locator(".company-spinner")).toHaveCount(0);
  });
}
