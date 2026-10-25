import { MotionState, MotionButton, MotionDisclosure } from "../motion";
import type { ReactNode } from "react";
import type { DTO } from "../api/client";
import CompanySpinner from "./CompanySpinner";

export const count = (value: number | null | undefined): string =>
  value == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }).format(
        value,
      );
export const metricValue = (value: number | null | undefined): string =>
  value == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-GB", { maximumFractionDigits: 4 }).format(
        value,
      );
export const percent = (value: number | null | undefined): string =>
  value == null ? "Unavailable" : `${count(value)}%`;
export const date = (value: string | null): string =>
  value === null ? "Not recorded" : `${value.slice(0, 10)} UTC`;
export const windowLabel = (window: DTO<"Window">): string =>
  `${date(window.start)} to ${date(window.end)} (end excluded)`;
export const modeLabel = (mode: string): string =>
  mode === "reconstructed"
    ? "Reconstructed historical backtest"
    : "Prospective forecast";

/** Render safe source links as navigation only, without fetching their contents. */
export function SourceLink({
  url,
  children,
}: {
  url: string;
  children: ReactNode;
}) {
  let safe = false;
  try {
    const parsed = new URL(url);
    safe =
      parsed.protocol === "https:" &&
      !parsed.username &&
      !parsed.password &&
      (!parsed.search ||
        (parsed.host === "news.ycombinator.com" &&
          parsed.pathname === "/item" &&
          /^\?id=[1-9][0-9]*$/.test(parsed.search))) &&
      !parsed.hash;
  } catch {
    /* Invalid external text remains plain text. */
  }
  return safe ? (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {children} (opens new tab)
    </a>
  ) : (
    <span>{children}</span>
  );
}

export function QueryState({
  pending,
  error,
  retry,
}: {
  pending: boolean;
  error: Error | null;
  retry: () => void;
}) {
  if (pending)
    return (
      <MotionState stateKey="pending">
        <p role="status" className="loading-label">
          <CompanySpinner size="small" />
          Loading published data…
        </p>
      </MotionState>
    );
  if (error)
    return (
      <MotionState
        stateKey={error.message}
        role="alert"
        className="notice error"
      >
        <p>{error.message}</p>
        <MotionButton onClick={retry}>Retry</MotionButton>
      </MotionState>
    );
  return null;
}

export function SyntheticNotice({ synthetic }: { synthetic: boolean }) {
  return synthetic ? (
    <p className="notice warning" role="note">
      <strong>Synthetic test data.</strong> These examples are not real
      forecasts or research findings.
    </p>
  ) : null;
}

export function Reasons({ reasons }: { reasons: readonly string[] }) {
  const descriptions: Record<string, string> = {
    gemini_provider_internal_error:
      "The model provider returned an internal error (HTTP 500).",
    gemini_provider_bad_gateway:
      "The model provider returned a gateway error (HTTP 502).",
    gemini_provider_overloaded:
      "The model provider is temporarily unavailable (HTTP 503).",
    gemini_provider_timeout: "The model provider timed out (HTTP 504).",
    gemini_request_timeout: "The model request exceeded its time limit.",
    gemini_connection_failed:
      "The server could not connect to the model provider.",
    analysis_unsupported_statement:
      "Some generated statements failed citation or evidence checks and were omitted. Validated findings are retained.",
  };
  return reasons.length ? (
    <ul className="reasons">
      {reasons.map((reason, index) => (
        <li key={`${index}-${reason}`}>
          {descriptions[reason] ?? reason.replaceAll("_", " ")}
        </li>
      ))}
    </ul>
  ) : null;
}

export function EvidenceList({ evidence }: { evidence: DTO<"Evidence">[] }) {
  return (
    <>
      {(
        ["measurement", "interpretation", "limitation", "mapping"] as const
      ).map((kind) => {
        const items = evidence.filter((item) => item.kind === kind);
        return (
          items.length > 0 && (
            <section key={kind}>
              <h3>
                {
                  {
                    measurement: "Measured changes",
                    interpretation: "Predictive interpretations",
                    limitation: "Limitations",
                    mapping: "Mapping provenance",
                  }[kind]
                }
              </h3>
              <ul>
                {items.map((item) => (
                  <li key={item.evidence_id}>
                    <p>{item.text}</p>
                    <small>
                      {item.source} ·{" "}
                      {item.kind === "mapping" ? "verified" : "observed"}{" "}
                      {date(item.observed_at)} · available{" "}
                      {date(item.available_at)}
                    </small>
                    {item.url && (
                      <p>
                        <SourceLink url={item.url}>Original source</SourceLink>
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )
        );
      })}
    </>
  );
}

export function Provenance({ provenance }: { provenance: DTO<"Provenance"> }) {
  return (
    <MotionDisclosure summary={<>Versions and provenance</>}>
      <dl className="metadata">
        {Object.entries(provenance)
          .filter(([key]) => !["limitations", "synthetic"].includes(key))
          .map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
      </dl>
      <Reasons reasons={provenance.limitations ?? []} />
    </MotionDisclosure>
  );
}
