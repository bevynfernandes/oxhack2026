import createClient from "openapi-fetch";
import { QueryClient } from "@tanstack/react-query";
import type { components, paths } from "./schema";

export type DTO<Name extends keyof components["schemas"]> =
  components["schemas"][Name];
export const api = createClient<paths>({ baseUrl: window.location.origin });

/** Carry only public status/messages; never expose an internal response body. */
export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(
      status === 409
        ? "Complete outcomes are not yet available for this batch."
        : status === 404
          ? "This published resource was not found."
          : status === 422
            ? "The request is invalid. Check the selected identifiers and filters."
            : "Published data is unavailable. Please retry.",
    );
  }
}

/** Unwrap a generated client response without substituting fixture data. */
export function unwrap<T>(result: { data?: T; response: Response }): T {
  if (!result.response.ok || result.data === undefined)
    throw new ApiError(result.response.status);
  return result.data;
}

/** Create an isolated cache with bounded retries and no retry for invalid requests. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        retry: (count, error) =>
          count < 1 && (!(error instanceof ApiError) || error.status >= 500),
      },
    },
  });
}
