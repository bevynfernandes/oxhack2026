import { ApiError, unwrap } from "../../api/client";

/** Keep research errors actionable without exposing response bodies. */
export function researchResult<T>(result: { data?: T; response: Response }): T {
  try {
    return unwrap(result);
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    error.message =
      error.status === 409
        ? "The company identity could not be confirmed. Return to the company and check its website."
        : error.status === 503
          ? "Research is unavailable. The local research service must be enabled and running; you can still view saved analyses."
          : error.status === 404
            ? "This research job or report was not found. Check the saved link."
            : error.status === 422
              ? "Check the company details and explicitly confirm its identity before starting research."
              : "Research could not be loaded. Please retry.";
    throw error;
  }
}
