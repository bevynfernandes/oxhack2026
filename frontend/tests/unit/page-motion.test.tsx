import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { MotionPage, MotionProvider } from "../../src/motion";

it("keeps the main element and child state on query/hash-only updates", () => {
  const view = render(
    <MotionProvider reducedMotion>
      <MotionPage id="main" tabIndex={-1} routeKey="/companies/alpha">
        <input aria-label="Local filter" />
      </MotionPage>
    </MotionProvider>,
  );
  const main = screen.getByRole("main");
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "retained" } });
  input.focus();
  view.rerender(
    <MotionProvider reducedMotion>
      <MotionPage id="main" tabIndex={-1} routeKey="/companies/alpha">
        <input aria-label="Local filter" />
      </MotionPage>
    </MotionProvider>,
  );
  expect(screen.getByRole("main")).toBe(main);
  expect(input).toHaveValue("retained");
  expect(input).toHaveFocus();
});

it("focuses the new page without retaining the old accessible content", () => {
  const view = render(
    <MotionProvider reducedMotion>
      <MotionPage tabIndex={-1} routeKey="/one">
        <h1>First</h1>
      </MotionPage>
    </MotionProvider>,
  );
  const main = screen.getByRole("main");
  main.scrollTo = () => {};
  view.rerender(
    <MotionProvider reducedMotion>
      <MotionPage tabIndex={-1} routeKey="/two">
        <h1>Second</h1>
      </MotionPage>
    </MotionProvider>,
  );
  expect(main).toHaveFocus();
  expect(screen.queryByRole("heading", { name: "First" })).toBeNull();
  expect(screen.getByRole("heading", { name: "Second" })).toBeVisible();
  expect(screen.getAllByRole("main")).toHaveLength(1);
});
