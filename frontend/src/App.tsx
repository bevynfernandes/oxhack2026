import { NavLink, Route, Routes } from "react-router-dom";
import BatchPicker from "./pages/rankings/BatchPicker";
import BatchPage from "./pages/rankings/BatchPage";
import EvaluationPage from "./pages/evaluation/EvaluationPage";
import DataHealthPage from "./pages/data-health/DataHealthPage";

/** Route the scouting workflow without bundling or silently loading test fixtures. */
export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <NavLink to="/" className="brand">
          SignalShift<span>Developer-tool scouting</span>
        </NavLink>
        <nav aria-label="Main navigation">
          <NavLink to="/">Forecasts</NavLink>
          <NavLink to="/data-health">Data health</NavLink>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<BatchPicker />} />
          <Route path="/batches/:batchId" element={<BatchPage />} />
          <Route
            path="/batches/:batchId/tools/:toolId"
            element={<BatchPage />}
          />
          <Route
            path="/evaluations/:evaluationId"
            element={<EvaluationPage />}
          />
          <Route path="/data-health" element={<DataHealthPage />} />
          <Route
            path="*"
            element={
              <>
                <h1>Page not found</h1>
                <NavLink to="/">Choose a published forecast</NavLink>
              </>
            }
          />
        </Routes>
      </main>
      <footer>
        Package activity is a scouting signal, not a measure of users, revenue
        or investment quality.
      </footer>
    </>
  );
}
