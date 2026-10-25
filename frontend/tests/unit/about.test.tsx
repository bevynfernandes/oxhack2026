import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import App from "../../src/App";

it("lists the product's current functions without requesting published data", () => {
  render(
    <MemoryRouter initialEntries={["/about"]}>
      <App />
    </MemoryRouter>,
  );

  expect(
    screen.getByRole("heading", {
      name: "Startup research with its evidence attached",
    }),
  ).toBeVisible();
  for (const name of [
    "What you can do",
    "Sources the research worker can check",
    "What the Research library does",
    "What the results currently mean",
    "Secondary tools",
  ]) {
    expect(screen.getByRole("heading", { name })).toBeVisible();
  }
  expect(screen.getByText(/not a success score/)).toBeVisible();
  expect(screen.getByRole("link", { name: "About" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByRole("link", { name: "Companies" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(vi.mocked(fetch)).not.toHaveBeenCalled();
});
