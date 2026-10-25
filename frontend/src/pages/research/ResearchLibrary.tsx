import { useState } from "react";
import {
  loadSavedSearches,
  storeSavedSearches,
  type SavedSearch,
} from "./savedSearches";
import { MotionButton, MotionInput, MotionLink as Link } from "../../motion";
import { date } from "../../components/Common";
import { forgetResearch, useResearchLibrary } from "./library";

/** One discoverable place for visited dossiers, fresh research and local watchlists. */
export default function ResearchLibrary() {
  const entries = useResearchLibrary();
  const [query, setQuery] = useState("");
  const [watchOnly, setWatchOnly] = useState(false);
  const [selection, setSelection] = useState<string[]>([]);
  const [limit, setLimit] = useState(6);
  const [error, setError] = useState("");
  const [savedSearches, setSavedSearches] = useState(loadSavedSearches);
  function saveFilters(next: SavedSearch[]) {
    try {
      storeSavedSearches(next);
      setSavedSearches(next);
      setError("");
    } catch {
      setError(
        "Browser storage is unavailable. This search could not be saved or removed.",
      );
    }
  }
  const rows = entries.filter(
    (row) =>
      (!watchOnly || row.watched) &&
      `${row.name} ${row.domain} ${row.notes}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const selected = selection.filter((path) =>
    entries.some((row) => row.path === path),
  );
  const comparison = new URLSearchParams();
  selected.forEach((path) => comparison.append("record", path));
  return (
    <section
      className="research-library panel"
      aria-labelledby="research-library-title"
    >
      <h2 id="research-library-title">Your research</h2>
      <p>
        Visited reports, saved dossiers and research jobs in this browser. Notes
        and watchlists are local to this browser, not an account; clearing
        browser data removes them.
      </p>
      <p>
        Review dates are manual reminders shown here. Background refreshes,
        alerts and cross-device sync are not available.
      </p>
      <div className="research-library-controls">
        <label>
          Find in your research
          <MotionInput
            type="search"
            maxLength={200}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setLimit(6);
            }}
          />
        </label>
        <label className="identity-confirm">
          <MotionInput
            type="checkbox"
            checked={watchOnly}
            onChange={(event) => setWatchOnly(event.target.checked)}
          />
          Watchlist only
        </label>
        {selected.length >= 2 ? (
          <Link className="button" to={`/compare?${comparison}`}>
            Compare research ({selected.length})
          </Link>
        ) : (
          <span>Select two or three dossiers to compare evidence.</span>
        )}
      </div>
      <div className="research-saved-searches">
        <MotionButton
          className="secondary"
          disabled={!query.trim() && !watchOnly}
          onClick={() =>
            saveFilters([
              { query: query.trim(), watched: watchOnly },
              ...savedSearches.filter(
                (row) =>
                  row.query !== query.trim() || row.watched !== watchOnly,
              ),
            ])
          }
        >
          Save this search
        </MotionButton>
        {savedSearches.length > 0 && (
          <>
            <h3>Saved searches in this browser</h3>
            <ul>
              {savedSearches.map((row, index) => (
                <li key={JSON.stringify(row)}>
                  <MotionButton
                    className="secondary"
                    onClick={() => {
                      setQuery(row.query);
                      setWatchOnly(row.watched);
                      setLimit(6);
                    }}
                  >
                    Use search: {row.query || "All research"}
                    {row.watched ? " · Watchlist" : ""}
                  </MotionButton>
                  <MotionButton
                    className="secondary"
                    aria-label={`Remove saved search ${row.query || "All research"}${row.watched ? " from watchlist" : ""}`}
                    onClick={() =>
                      saveFilters(savedSearches.filter((_, i) => i !== index))
                    }
                  >
                    Remove search
                  </MotionButton>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {!rows.length && (
        <p role="status">
          {entries.length
            ? "No research matches these filters."
            : "No research history yet. Open a saved dossier or research a company to keep its link here."}
        </p>
      )}
      <ul className="research-library-list">
        {rows.slice(0, limit).map((row) => (
          <li key={row.path}>
            {row.kind !== "job" && (
              <label className="identity-confirm">
                <MotionInput
                  type="checkbox"
                  aria-label={`Compare research for ${row.name} from ${row.asOf ?? "unknown date"}`}
                  checked={selected.includes(row.path)}
                  disabled={
                    !selected.includes(row.path) && selected.length >= 3
                  }
                  onChange={(event) =>
                    setSelection(
                      event.target.checked
                        ? [...selected, row.path]
                        : selected.filter((path) => path !== row.path),
                    )
                  }
                />
                Compare
              </label>
            )}
            <div>
              <Link to={row.path}>{row.name}</Link>
              <small>
                {row.domain} ·{" "}
                {row.kind === "saved"
                  ? "Published dossier"
                  : row.kind === "job"
                    ? "Research progress"
                    : "Research report"}{" "}
                · {date(row.asOf)}
              </small>
              {row.watched && <strong>On watchlist</strong>}
              {row.reviewOn && (
                <p>
                  {row.reviewOn <= new Date().toISOString().slice(0, 10)
                    ? "Review due"
                    : "Review on"}
                  : {row.reviewOn} UTC
                </p>
              )}
              {row.notes && (
                <p className="research-note">Your note: {row.notes}</p>
              )}
            </div>
            <MotionButton
              className="secondary"
              onClick={() => {
                try {
                  forgetResearch(row.path);
                } catch {
                  setError(
                    "Browser storage is unavailable. This research link could not be removed.",
                  );
                }
              }}
              aria-label={`Remove ${row.name} from local history`}
            >
              Remove link
            </MotionButton>
          </li>
        ))}
      </ul>
      {rows.length > limit && (
        <MotionButton className="secondary" onClick={() => setLimit(limit + 6)}>
          Show more research
        </MotionButton>
      )}
      <Link to="/">Research another company</Link>
    </section>
  );
}
