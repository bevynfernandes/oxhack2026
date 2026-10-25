import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import {
  annotateResearch,
  forgetResearch,
  parseLibrary,
  rememberResearch,
  useResearchLibrary,
} from "../../src/pages/research/library";
import ResearchLibrary from "../../src/pages/research/ResearchLibrary";

const record = {
  path: "/research/v2/reports/one",
  name: "One",
  domain: "one.example",
  asOf: "2026-10-25T01:00:00Z",
};
it("retains personal notes and watchlist while recording an immutable report again", () => {
  rememberResearch(record);
  annotateResearch(record.path, {
    watched: true,
    notes: "Check paying customers",
    reviewOn: "2026-11-01",
  });
  rememberResearch({ ...record, asOf: null });
  const rows = parseLibrary(
    localStorage.getItem("signalshift.research-library.v1"),
  );
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({
    ...record,
    watched: true,
    notes: "Check paying customers",
    reviewOn: "2026-11-01",
  });
  forgetResearch(record.path);
  expect(
    parseLibrary(localStorage.getItem("signalshift.research-library.v1")),
  ).toEqual([]);
});
it("rejects corrupt entries and external or script routes", () => {
  rememberResearch(record);
  const entry = parseLibrary(
    localStorage.getItem("signalshift.research-library.v1"),
  )[0];
  expect(parseLibrary("not json")).toEqual([]);
  for (const path of [
    "https://evil.test",
    "javascript:alert(1)",
    "/data-health",
    "/research/v2/reports/one?redirect=evil",
  ]) {
    expect(parseLibrary(JSON.stringify([{ ...entry, path }]))).toEqual([]);
  }
  expect(
    parseLibrary(JSON.stringify([{ ...entry, path: "/nope", kind: null }])),
  ).toEqual([]);
});
it("reacts to local saves and filters without changing report data", () => {
  rememberResearch(record);
  rememberResearch({
    ...record,
    path: "/companies/publication/two",
    name: "Two",
  });
  render(
    <MemoryRouter>
      <ResearchLibrary />
    </MemoryRouter>,
  );
  fireEvent.click(
    screen.getAllByRole("checkbox", { name: /Compare research for/ })[0],
  );
  fireEvent.click(
    screen.getAllByRole("checkbox", { name: /Compare research for/ })[1],
  );
  expect(
    screen.getByRole("link", { name: "Compare research (2)" }),
  ).toHaveAttribute("href", expect.stringContaining("/compare?record="));
  fireEvent.change(
    screen.getByRole("searchbox", { name: "Find in your research" }),
    { target: { value: "missing" } },
  );
  expect(screen.getByRole("status")).toHaveTextContent("No research matches");
});
it("keeps reading usable when browser storage is unavailable and fails writes explicitly", () => {
  const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  function Count() {
    return <p>{useResearchLibrary().length} records</p>;
  }
  render(<Count />);
  expect(screen.getByText("0 records")).toBeVisible();
  expect(() => rememberResearch(record)).toThrow("blocked");
  get.mockRestore();
  set.mockRestore();
});

it("saves and restores local search filters after remount without starting research", () => {
  rememberResearch(record);
  const mount = () =>
    render(
      <MemoryRouter>
        <ResearchLibrary />
      </MemoryRouter>,
    );
  const first = mount();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "One" } });
  fireEvent.click(screen.getByLabelText("Watchlist only"));
  fireEvent.click(screen.getByRole("button", { name: "Save this search" }));
  first.unmount();
  mount();
  fireEvent.click(
    screen.getByRole("button", { name: "Use search: One · Watchlist" }),
  );
  expect(screen.getByRole("searchbox")).toHaveValue("One");
  expect(screen.getByLabelText("Watchlist only")).toBeChecked();
  fireEvent.click(
    screen.getByRole("button", {
      name: "Remove saved search One from watchlist",
    }),
  );
  expect(screen.queryByText("Saved searches in this browser")).toBeNull();
});
