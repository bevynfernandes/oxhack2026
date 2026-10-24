import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

/** Audit the settled page and modal state; intermediate opacity is intentionally transient. */
export async function auditAccessibility(page: Page) {
  await page.waitForFunction(() =>
    Array.from(
      document.querySelectorAll<HTMLElement>(
        "[data-motion-page], dialog[open]",
      ),
    ).every((dialog) => {
      const style = getComputedStyle(dialog);
      const transform = new DOMMatrixReadOnly(style.transform);
      return (
        style.opacity === "1" &&
        Math.abs(transform.e) < 0.01 &&
        Math.abs(transform.f) < 0.01
      );
    }),
  );
  return new AxeBuilder({ page }).analyze();
}
