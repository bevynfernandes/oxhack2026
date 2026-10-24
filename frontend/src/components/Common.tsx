import type { ReactNode } from "react";
import type { DTO } from "../api/client";

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
  if (pending) return <p role="status">Loading published data…</p>;
  if (error)
    return (
      <div role="alert" className="notice error">
        <p>{error.message}</p>
        <button onClick={retry}>Retry</button>
      </div>
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
  return reasons.length ? (
    <ul className="reasons">
      {reasons.map((reason, index) => (
        <li key={`${index}-${reason}`}>{reason.replaceAll("_", " ")}</li>
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
    <details>
      <summary>Versions and provenance</summary>
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
    </details>
  );
}
