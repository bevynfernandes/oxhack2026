import { NavLink, Route, Routes } from "react-router-dom";
import BatchPicker from "./pages/rankings/BatchPicker";
import BatchPage from "./pages/rankings/BatchPage";
import EvaluationPage from "./pages/evaluation/EvaluationPage";
import DataHealthPage from "./pages/data-health/DataHealthPage";
import MethodologyPage from "./pages/methodology/MethodologyPage";
import CompanyHomePage from "./pages/companies/CompanyHomePage";
import CompanyListPage from "./pages/companies/CompanyListPage";
import CompanyProfilePage from "./pages/companies/CompanyProfilePage";
import ComparePage from "./pages/companies/ComparePage";

/** Route the scouting workflow without bundling or silently loading test fixtures. */
export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <NavLink to="/" className="brand">
          SignalShift<span>Startup outlook</span>
        </NavLink>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            Companies
          </NavLink>
          <NavLink to="/explore">Compare & explore</NavLink>
          <NavLink to="/methodology">Methodology</NavLink>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<CompanyHomePage />} />
          <Route path="/explore" element={<CompanyListPage />} />
          <Route
            path="/companies/:snapshotId/:companyId"
            element={<CompanyProfilePage />}
          />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/traction" element={<BatchPicker />} />
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
          <Route path="/methodology" element={<MethodologyPage />} />
          <Route
            path="*"
            element={
              <>
                <h1>Page not found</h1>
                <NavLink to="/">Browse company assessments</NavLink>
              </>
            }
          />
        </Routes>
      </main>
      <footer>
        Company outlooks describe published evidence and its limits. Package
        activity alone does not establish company growth.{" "}
        <NavLink to="/traction">Traction research</NavLink>
        {" · "}
        <NavLink to="/data-health">Data health</NavLink>
      </footer>
    </>
  );
}
