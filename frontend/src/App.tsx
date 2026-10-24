import type { ReactElement } from "react";

/** Render the static project-template landing page. */
export default function App(): ReactElement {
  return (
    <main>
      <p className="status">Project template</p>
      <h1>SignalShift</h1>
      <p>
        The frontend scaffold is ready. Product screens, data connections, and
        forecasts have not been implemented.
      </p>
      <section aria-labelledby="planned-views">
        <h2 id="planned-views">Planned views</h2>
        <ul>
          <li>Rankings</li>
          <li>Tool detail</li>
          <li>Historical replay</li>
          <li>Evaluation</li>
          <li>Data health</li>
        </ul>
      </section>
    </main>
  );
}
