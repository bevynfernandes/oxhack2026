import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import CompanyHomePage from "../../src/pages/companies/CompanyHomePage";
import { api } from "../../src/api/client";
import {
  previewCompany,
  searchCompanies,
} from "../../src/pages/research/client";

vi.mock("../../src/api/client", async (original) => {
  const actual = await original<typeof import("../../src/api/client")>();
  return { ...actual, api: { GET: vi.fn() } };
});
vi.mock("../../src/pages/research/client", () => ({
  previewCompany: vi.fn(),
  searchCompanies: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(api.GET).mockResolvedValue({
    data: { items: [] },
    response: new Response("{}", { status: 200 }),
  } as never);
  vi.mocked(previewCompany).mockResolvedValue({
    identity_id: "chosen",
  } as never);
});

function workspace() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false } },
        })
      }
    >
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<CompanyHomePage />} />
          <Route
            path="/research/identities/:identityId"
            element={<p>Check this company identity</p>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it.each(["example.com", "https://example.com/about", "www.example.com"])(
  "previews an unsaved website directly without name lookup: %s",
  async (domain) => {
    workspace();
    fireEvent.change(screen.getByLabelText("Search companies"), {
      target: { value: domain },
    });
    fireEvent.click(screen.getByRole("button", { name: "Research company" }));
    expect(
      await screen.findByText("Check this company identity"),
    ).toBeVisible();
    expect(searchCompanies).not.toHaveBeenCalled();
    expect(previewCompany).toHaveBeenCalledWith(domain, expect.anything());
  },
);

it("requires a website choice for ambiguous company names", async () => {
  vi.mocked(searchCompanies).mockResolvedValue({
    query: "Example",
    reason_codes: [],
    candidates: ["example.com", "example.co.uk"].map((domain) => ({
      name: "Example",
      domain,
      website: `https://${domain}`,
      source: "public_directory" as const,
    })),
  });
  workspace();
  fireEvent.change(screen.getByLabelText("Search companies"), {
    target: { value: "Example" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Research company" }));
  const choice = await screen.findByRole("button", {
    name: "Inspect example.co.uk",
  });
  expect(previewCompany).not.toHaveBeenCalled();
  fireEvent.click(choice);
  expect(await screen.findByText("Check this company identity")).toBeVisible();
  expect(previewCompany).toHaveBeenCalledWith(
    "https://example.co.uk",
    expect.anything(),
  );
});

it("asks for a domain when no supported name match exists", async () => {
  vi.mocked(searchCompanies).mockResolvedValue({
    query: "Unknown",
    candidates: [],
    reason_codes: ["no_supported_name_match"],
  });
  workspace();
  fireEvent.change(screen.getByLabelText("Search companies"), {
    target: { value: "Unknown" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Research company" }));
  await waitFor(() =>
    expect(screen.getByText(/No reliable website match/)).toBeVisible(),
  );
  expect(previewCompany).not.toHaveBeenCalled();
});

it("keeps new research available when saved assessments cannot be loaded", async () => {
  vi.mocked(api.GET).mockResolvedValue({
    response: new Response("{}", { status: 503 }),
  } as never);
  workspace();
  expect(
    await screen.findByText(/Saved company assessments are unavailable/),
  ).toBeVisible();
  expect(screen.getByLabelText("Search companies")).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Retry saved assessments" }),
  ).toBeEnabled();
});

it("shows the supplied website favicon while company lookup is pending", async () => {
  vi.mocked(searchCompanies).mockReturnValue(new Promise(() => {}));
  workspace();
  fireEvent.change(screen.getByLabelText("Search companies"), {
    target: { value: "elevenlabs.io" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Research company" }));
  const pending = await screen.findByRole("button", {
    name: "Finding company…",
  });
  expect(pending).toBeDisabled();
  expect(pending.querySelector("img")).toHaveAttribute(
    "src",
    "https://elevenlabs.io/favicon.ico",
  );
});
