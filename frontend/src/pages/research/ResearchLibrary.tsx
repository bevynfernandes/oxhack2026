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
  const selectedEntries = selected.flatMap((path) => {
    const entry = entries.find((row) => row.path === path);
    return entry ? [entry] : [];
  });
  const comparison = new URLSearchParams();
  selected.forEach((path) => comparison.append("record", path));
  return (
    <section
      className="research-library panel"
      aria-label="Startup research comparison"
    >
      <header className="research-library-header">
        <div>
          <p className="eyebrow">YOUR RESEARCH</p>
          <h2 id="research-library-title">Compare two startups side by side</h2>
          <p className="research-library-lede">
            Choose research you have already opened, then compare its evidence,
            dates and missing information. The comparison does not pick a
            winner.
          </p>
        </div>
        <Link className="button secondary" to="/">
          Research another startup
        </Link>
      </header>

      <ol className="research-library-steps" aria-label="How comparison works">
        <li>
          <strong>Find</strong>
          <span>Search your saved research</span>
        </li>
        <li>
          <strong>Choose</strong>
          <span>Select two startups</span>
        </li>
        <li>
          <strong>Compare</strong>
          <span>Review equivalent evidence</span>
        </li>
      </ol>

      <div className="research-library-controls">
        <label>
          Find a startup
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
          Save filter
        </MotionButton>
      </div>
      {savedSearches.length > 0 && (
        <div className="research-saved-searches">
          <h3>Saved filters in this browser</h3>
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
        </div>
      )}
      {error && <p role="alert">{error}</p>}

      <section
        className="research-compare-builder"
        aria-labelledby="research-selection-title"
      >
        <header>
          <div>
            <p className="eyebrow">COMPARISON</p>
            <h3 id="research-selection-title">Your startup selection</h3>
          </div>
          <span className="research-selection-count" aria-live="polite">
            {selected.length} of 3 selected
          </span>
        </header>
        <div className="research-compare-slots">
          {[0, 1].map((index) => {
            const row = selectedEntries[index];
            return (
              <article
                className={row ? "is-filled" : "is-empty"}
                key={row?.path ?? `empty-${index}`}
              >
                <span className="research-slot-number">0{index + 1}</span>
                {row ? (
                  <>
                    <div>
                      <strong>{row.name}</strong>
                      <small>
                        {row.domain} · {date(row.asOf)}
                      </small>
                    </div>
                    <MotionButton
                      className="secondary"
                      aria-label={`Remove ${row.name} from comparison`}
                      onClick={() =>
                        setSelection(
                          selected.filter((path) => path !== row.path),
                        )
                      }
                    >
                      Remove
                    </MotionButton>
                  </>
                ) : (
                  <div>
                    <strong>
                      {index === 0 ? "First startup" : "Second startup"}
                    </strong>
                    <small>Select one from the research cards below.</small>
                  </div>
                )}
              </article>
            );
          })}
          {selectedEntries[2] && (
            <article className="is-filled optional">
              <span className="research-slot-number">03</span>
              <div>
                <strong>{selectedEntries[2].name}</strong>
                <small>
                  Optional third startup · {selectedEntries[2].domain} ·{" "}
                  {date(selectedEntries[2].asOf)}
                </small>
              </div>
              <MotionButton
                className="secondary"
                aria-label={`Remove ${selectedEntries[2].name} from comparison`}
                onClick={() =>
                  setSelection(
                    selected.filter((path) => path !== selectedEntries[2].path),
                  )
                }
              >
                Remove
              </MotionButton>
            </article>
          )}
        </div>
        <div className="research-compare-action">
          <p>
            {selected.length < 2
              ? `Choose ${2 - selected.length} more startup${selected.length === 1 ? "" : "s"} to continue.`
              : "Your comparison is ready. You can optionally add one more startup."}
          </p>
          {selected.length >= 2 && (
            <Link className="button" to={`/compare?${comparison}`}>
              Compare {selected.length} startups
            </Link>
          )}
        </div>
      </section>

      <div className="research-library-list-heading">
        <div>
          <p className="eyebrow">AVAILABLE DOSSIERS</p>
          <h3>Choose startups to compare</h3>
        </div>
        <p>Each startup must have a completed report or saved dossier.</p>
      </div>
      {!rows.length && (
        <p role="status">
          {entries.length
            ? "No research matches these filters."
            : "No research history yet. Open a saved dossier or research a company to keep its link here."}
        </p>
      )}
      <ul className="research-library-list">
        {rows.slice(0, limit).map((row) => {
          const position = selected.indexOf(row.path);
          return (
            <li key={row.path} className={position >= 0 ? "is-selected" : ""}>
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
                  {position >= 0 ? `Selected 0${position + 1}` : "Select"}
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
          );
        })}
      </ul>
      {rows.length > limit && (
        <MotionButton className="secondary" onClick={() => setLimit(limit + 6)}>
          Show more research
        </MotionButton>
      )}
      <p className="research-library-storage-note">
        Notes, watchlists and review dates are stored only in this browser.
        Clearing browser data removes them; automatic alerts and cross-device
        sync are not available.
      </p>
    </section>
  );
}
