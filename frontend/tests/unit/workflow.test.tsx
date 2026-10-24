import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import App from "../../src/App";
import { createQueryClient, type DTO } from "../../src/api/client";
import { count, SourceLink } from "../../src/components/Common";
import { initialSelection } from "../../src/pages/replay/selection";
import raw from "../../../tests/fixtures/api/scouting.json";

const batch = raw.forecast.batch_id;
const fetchMock = vi.mocked(fetch);

beforeEach(() => {
  history.replaceState(null, "", "/");
  fetchMock.mockImplementation(async (input) => {
    const request = input as Request;
    const path = new URL(request.url).pathname;
    let data: unknown;
    if (path.endsWith("/cutoffs")) data = raw.cutoffs;
    else if (path.includes("/forecasts/")) data = raw.forecast;
    else if (path.includes("/rankings/")) data = raw.rankings;
    else if (path.endsWith("/catalog")) data = raw.catalog;
    else if (path.endsWith("/data-health")) data = raw.data_health;
    else if (path.includes("/evaluations/")) data = raw.evaluation;
    else if (path.endsWith("/reveal")) {
      const selection = (await request.json()) as DTO<"RevealRequest">;
      data = {
        ...raw.reveal,
        selected_organization_ids: selection.organization_ids,
        selection_score: {
          ...raw.reveal.selection_score,
          organization_ids: selection.organization_ids,
        },
      };
    }
    return new Response(JSON.stringify(data), {
      status: data ? 200 : 404,
      headers: { "Content-Type": "application/json" },
    });
  });
});

function mount(path: string) {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false, gcTime: 0 } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("shows only published combinations and an empty second ecosystem", async () => {
  mount("/traction");
  expect(
    await screen.findByRole("link", { name: /Open forecast/ }),
  ).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Ecosystem"), "pypi");
  expect(screen.getByText(/No published batches/)).toBeVisible();
});

it("keeps outcomes absent until reveal, freezes earlier scores and marks edits informed", async () => {
  mount(`/batches/${batch}`);
  expect(
    await screen.findByRole("heading", { name: "Your scouting shortlist" }),
  ).toBeVisible();
  expect(screen.getByText(/Synthetic test data/)).toBeVisible();
  expect(screen.queryByText("Actual downloads")).toBeNull();
  expect(screen.getByLabelText("Select Fixture Company 6")).toBeDisabled();
  await userEvent.click(
    screen.getByRole("button", { name: "Reveal outcomes" }),
  );
  const first = await screen.findByRole("article", {
    name: "Scored selection 1",
  });
  const frozen = within(first).getByText(/Frozen organizations/).textContent;
  await userEvent.click(screen.getByLabelText("Select Fixture Company 1"));
  await userEvent.click(screen.getByLabelText("Select Fixture Company 6"));
  await userEvent.click(
    screen.getByRole("button", { name: "Score a new selection" }),
  );
  const second = await screen.findByRole("article", {
    name: "Scored selection 2",
  });
  expect(within(first).getByText(/Frozen organizations/)).toHaveTextContent(
    frozen!,
  );
  expect(within(second).getByText(/Frozen organizations/)).toHaveTextContent(
    "Fixture Company 6",
  );
  expect(within(second).getByRole("heading")).toHaveTextContent("After reveal");
});

it("renders baseline wins and failed coverage without a superiority claim", async () => {
  mount("/evaluations/synthetic-evaluation-v1");
  expect(await screen.findByText(/Baseline wins/)).toBeVisible();
  expect(screen.getByText(/Coverage gate failed/)).toBeVisible();
  expect(screen.getByText(/Insufficient origins/)).toBeVisible();
});

it("renders safe service errors and supports retry", async () => {
  fetchMock.mockResolvedValue(
    new Response('{"code":"repository_unavailable"}', { status: 503 }),
  );
  mount("/traction");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Published data is unavailable",
  );
  expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
});

it("reports source degradation and preserves explicit zero", async () => {
  mount("/data-health");
  expect(await screen.findByText("degraded")).toBeVisible();
  expect(count(null)).toBe("Unavailable");
  expect(count(0)).toBe("0");
});

it("does not turn external script or credential URLs into links", () => {
  render(
    <SourceLink url="javascript:alert(1)">
      {"<img src=x onerror=alert(1)>"}
    </SourceLink>,
  );
  expect(screen.queryByRole("link")).toBeNull();
  expect(document.querySelector("img")).toBeNull();
});

it("sanitizes URL and stored selections without copying numerical policy", () => {
  localStorage.setItem(
    `signalshift:${batch}`,
    JSON.stringify({ selected: ["org-2"], revealed: true }),
  );
  history.replaceState(
    null,
    "",
    "/?selection=org-1&selection=org-1&selection=unknown",
  );
  expect(initialSelection(batch, ["org-1", "org-2"], [])).toMatchObject({
    selected: ["org-1"],
    revealed: true,
  });
});

it("preserves a captured request when a selection changes during reveal", async () => {
  mount(`/batches/${batch}`);
  await screen.findByRole("heading", { name: "Your scouting shortlist" });
  const pending = (() => {
    let resolve!: (response: Response) => void;
    const promise = new Promise<Response>((finish) => {
      resolve = finish;
    });
    return { promise, resolve };
  })();
  fetchMock.mockImplementation(() => pending.promise);
  await userEvent.click(
    screen.getByRole("button", { name: "Reveal outcomes" }),
  );
  await userEvent.click(screen.getByLabelText("Select Fixture Company 1"));
  await userEvent.click(screen.getByLabelText("Select Fixture Company 6"));
  pending.resolve(
    new Response(JSON.stringify(raw.reveal), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("article", { name: "Scored selection 1" }),
    ).toBeVisible(),
  );
  expect(
    within(
      screen.getByRole("article", { name: "Scored selection 1" }),
    ).getByText(/Frozen organizations/),
  ).toHaveTextContent("Fixture Company 1");
  expect(screen.getByLabelText("Select Fixture Company 6")).toBeChecked();
});

it("labels retrospective mapping verification explicitly", async () => {
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => {
    const request = input as Request;
    if (new URL(request.url).pathname.endsWith("/catalog")) {
      const catalog = {
        ...raw.catalog,
        tools: raw.catalog.tools.map((tool) => ({
          ...tool,
          mapping_verification: "retrospective",
        })),
      };
      return new Response(JSON.stringify(catalog), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return previous(input, init);
  });
  mount(`/batches/${batch}`);
  expect(
    await screen.findByText(/Some identities were verified retrospectively/),
  ).toBeVisible();
});

it("does not invent a date for an unavailable source", async () => {
  fetchMock.mockResolvedValue(
    new Response(
      JSON.stringify({
        synthetic: true,
        sources: raw.data_health.sources.map((source) => ({
          ...source,
          freshness: { ...source.freshness, as_of: null },
        })),
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  mount("/data-health");
  expect(await screen.findByText(/Not recorded/)).toBeVisible();
});
