import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import App from "../../src/App";

it("explains company outcomes without a repository, fixture or prediction request", () => {
  render(
    <MemoryRouter initialEntries={["/methodology"]}>
      <App />
    </MemoryRouter>,
  );

  expect(
    screen.getByRole("heading", { name: "How to read a company outlook" }),
  ).toBeVisible();
  for (const name of [
    "Operating and growing · 24 months",
    "Cash-flow self-sufficiency · 12 months",
    "Financing or acquisition · 24 months",
  ]) {
    expect(screen.getByRole("heading", { name })).toBeVisible();
  }
  expect(screen.getByText(/not a claim that a validated/)).toBeVisible();
  expect(screen.getByRole("link", { name: "Methodology" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByRole("link", { name: "Forecasts" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(vi.mocked(fetch)).not.toHaveBeenCalled();
});
