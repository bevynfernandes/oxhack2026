/** Explain the company outcome policy without fetching or inventing assessments. */
export default function MethodologyPage() {
  return (
    <article className="methodology">
      <header className="page-heading">
        <h1>How to read a company outlook</h1>
        <p>
          Assess a company through its commercial performance, traction,
          execution and financing evidence. Each outcome answers a different
          question, with its own time horizon and evidence requirements.
        </p>
      </header>

      <section aria-labelledby="outcomes-heading">
        <h2 id="outcomes-heading">Three separate outcomes</h2>
        <p>
          There is no combined success score. A company can raise funding while
          spending more cash than it generates, or continue operating without
          growing.
        </p>
        <h3>Operating and growing · 24 months</h3>
        <p>
          Continuing operation at the endpoint and growth in a predeclared
          company measure: revenue or active paying customers. The comparison
          uses equivalent twelve-month periods and consistent definitions.
          Package downloads alone cannot establish this outcome.
        </p>
        <h3>Cash-flow self-sufficiency · 12 months</h3>
        <p>
          Continuing operation with operating cash flow of at least zero over
          the ending twelve-month period. Negative cash flow is distinct from
          shutdown; it does not by itself establish that a startup will fail.
        </p>
        <h3>Financing or acquisition · 24 months</h3>
        <p>
          A completed primary equity or convertible financing, or a completed
          change-of-control acquisition, within the horizon. Announced and
          completed events are different. An acquisition can be distressed;
          neither funding nor acquisition establishes profitability.
        </p>
        <p>
          Horizons use calendar anniversaries, with leap-day anniversaries
          ending on the last day of February. Events already known at the
          assessment date are supporting evidence, rather than future outcomes.
        </p>
      </section>

      <section aria-labelledby="assessment-heading">
        <h2 id="assessment-heading">Evidence and probabilities</h2>
        <dl className="methodology-definitions">
          <div>
            <dt>Evidence-only assessment</dt>
            <dd>
              A provisional account of supported signals, risks and unknowns. It
              is not a numerical probability of success.
            </dd>
          </div>
          <div>
            <dt>Validated probability</dt>
            <dd>
              Requires an outcome-specific published model that passes a
              reviewed release gate using historical labels, chronological
              evaluation and calibration. The evaluation must describe the
              companies and time periods it supports.
            </dd>
          </div>
          <div>
            <dt>Unavailable assessment</dt>
            <dd>
              The published evidence or assessment is insufficient. Missing
              financials, an absent funding announcement or a dead website does
              not become a failure prediction.
            </dd>
          </div>
        </dl>
        <p>
          These are publication requirements, not a claim that a validated
          company prediction model is available. Download forecasts measure
          package activity and remain a separate research workflow.
        </p>
      </section>

      <section aria-labelledby="evidence-heading">
        <h2 id="evidence-heading">Check the evidence in context</h2>
        <p>
          Compare companies using the same metric definitions, units and
          periods, with their stage and business model in view. Traction,
          commercial health, execution and market or financing records each
          describe part of the business.
        </p>
        <ul>
          <li>
            An observed zero is a measurement. Missing, not applicable,
            conflicting and stale evidence have different meanings.
          </li>
          <li>
            A source states who reported a fact and whether it has been
            reviewed. Company-reported claims remain identifiable.
          </li>
          <li>
            The date an event occurred, the date it became available and the
            date it was collected are separate. Historical reconstructions must
            disclose evidence collected later.
          </li>
          <li>
            A snapshot fixes the records used for an assessment. A later source
            update cannot silently rewrite that historical view.
          </li>
        </ul>
      </section>

      <section aria-labelledby="followup-heading">
        <h2 id="followup-heading">What later outcomes can establish</h2>
        <p>
          Future results stay separate from the evidence available at the
          assessment date. Binary evaluation requires the full horizon to have
          elapsed, including for an early funding or shutdown event. Immature,
          unobserved and conflicting follow-up remain explicit.
        </p>
        <p>
          An absent funding announcement leaves the financing outcome unknown. A
          surviving-company sample cannot establish how well a model predicts
          startup failure. Evaluation needs dated follow-up and coverage of
          inactive companies as well as surviving peers.
        </p>
      </section>
    </article>
  );
}
