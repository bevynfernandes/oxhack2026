import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

vi.stubGlobal("fetch", vi.fn());
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});
