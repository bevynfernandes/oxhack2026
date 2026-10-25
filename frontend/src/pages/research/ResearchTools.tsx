import { useEffect, useRef, useState } from "react";
import {
  MotionButton,
  MotionDialog,
  MotionInput,
  MotionLink as Link,
  type MotionDialogHandle,
} from "../../motion";
import { date, SyntheticNotice } from "../../components/Common";
import {
  annotateResearch,
  rememberResearch,
  useResearchLibrary,
} from "./library";
import type { EvidenceSummary } from "./summary";

/** Keep decision context, personal notes and watchlist actions beside every dossier. */
export default function ResearchTools({
  path,
  summary,
}: {
  path: string;
  summary: EvidenceSummary;
}) {
  const { name, domain, asOf } = summary;
  const entries = useResearchLibrary();
  const entry = entries.find((row) => row.path === path);
  const dialog = useRef<MotionDialogHandle>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [notes, setNotes] = useState("");
  const [watched, setWatched] = useState(false);
  const [reviewOn, setReviewOn] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    try {
      rememberResearch({ path, name, domain, asOf });
    } catch {
      setMessage(
        "Browser storage is unavailable. Research remains readable, but local history and notes cannot be saved.",
      );
    }
  }, [path, name, domain, asOf]);
  return (
    <>
      <MotionButton
        ref={trigger}
        className="research-tools-trigger"
        aria-haspopup="dialog"
        onClick={() => {
          setNotes(entry?.notes ?? "");
          setWatched(entry?.watched ?? false);
          setReviewOn(entry?.reviewOn ?? "");
          dialog.current?.showModal();
        }}
      >
        Decision summary & notes
      </MotionButton>
      <MotionDialog
        ref={dialog}
        className="research-tools-dialog"
        aria-labelledby="research-tools-title"
        onClose={() => trigger.current?.focus()}
      >
        <header>
          <h2 id="research-tools-title">{name}: decision summary</h2>
          <MotionButton
            autoFocus
            className="secondary"
            onClick={() => dialog.current?.close()}
            aria-label="Close decision summary"
          >
            Close
          </MotionButton>
        </header>
        <SyntheticNotice synthetic={summary.synthetic} />
        <p>
          <strong>
            Evidence report. Validated success/failure predictions are
            unavailable.
          </strong>
        </p>
        <dl className="research-decision-summary">
          <div>
            <dt>Defined outcomes</dt>
            <dd>
              Use the outcome definitions and horizons published in this report.
              Proposed targets are not validated forecasts. Overall is a
              five-dimension index, not a probability. Legacy reports retain
              their original definitions.
            </dd>
          </div>
          <div>
            <dt>Confidence and coverage</dt>
            <dd>
              Predictive confidence is not calibrated. {summary.coverage}.
            </dd>
          </div>
          <div>
            <dt>Supporting signal</dt>
            <dd>{summary.supporting}</dd>
          </div>
          <div>
            <dt>Largest risk</dt>
            <dd>{summary.risk}</dd>
          </div>
          <div>
            <dt>Critical missing information</dt>
            <dd>
              {summary.gaps.length
                ? summary.gaps.join(", ")
                : "Inspect each metric's applicability, period and evidence; coverage does not establish completeness."}
            </dd>
          </div>
          <div>
            <dt>Research freshness</dt>
            <dd>
              <time dateTime={asOf ?? undefined}>{asOf ?? "Not recorded"}</time>{" "}
              · Individual source dates may be older.
            </dd>
          </div>
          <div>
            <dt>Company context</dt>
            <dd>{summary.context}</dd>
          </div>
          <div>
            <dt>Comparable peers</dt>
            <dd>
              No peer suitability is inferred. Choose reports in{" "}
              <Link to="/explore">Your research</Link> and check sector, stage,
              periods and definitions before comparing.
            </dd>
          </div>
        </dl>
        <p>
          Collected excerpts are attributed source material, which may include
          company claims or demonstrations. Auxiliary model estimates are
          experimental; neither establishes customers, revenue or a validated
          company outcome.
        </p>
        <h3>Your notes and watchlist</h3>
        <p>
          Saved only in this browser. Review dates do not schedule research or
          send alerts.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            try {
              rememberResearch({ path, name, domain, asOf });
              annotateResearch(path, { watched, notes, reviewOn });
              setMessage("Saved in this browser.");
            } catch {
              setMessage(
                "Could not save: browser storage is unavailable or full. Copy your notes before leaving.",
              );
            }
          }}
        >
          <label className="identity-confirm">
            <MotionInput
              type="checkbox"
              checked={watched}
              onChange={(event) => setWatched(event.target.checked)}
            />
            Keep on my watchlist
          </label>
          <label>
            Research notes
            <textarea
              maxLength={4000}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={4}
            />
          </label>
          <label>
            Review date (UTC)
            <MotionInput
              type="date"
              value={reviewOn}
              onChange={(event) => setReviewOn(event.target.value)}
            />
          </label>
          <MotionButton type="submit">Save notes and watchlist</MotionButton>
          {message && <p role="status">{message}</p>}
        </form>
        <p>
          Report date: {date(asOf)} ·{" "}
          <Link to="/explore">Open your research and compare</Link>
        </p>
      </MotionDialog>
    </>
  );
}
