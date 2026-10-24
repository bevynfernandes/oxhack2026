import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import Icon from "./components/WorkspaceIcon";
import BatchPicker from "./pages/rankings/BatchPicker";
import BatchPage from "./pages/rankings/BatchPage";
import EvaluationPage from "./pages/evaluation/EvaluationPage";
import DataHealthPage from "./pages/data-health/DataHealthPage";
import MethodologyPage from "./pages/methodology/MethodologyPage";
import CompanyHomePage from "./pages/companies/CompanyHomePage";
import CompanyListPage from "./pages/companies/CompanyListPage";
import CompanyProfilePage from "./pages/companies/CompanyProfilePage";
import StartResearchPage from "./pages/research/StartResearchPage";
import ResearchJobPage from "./pages/research/ResearchJobPage";
import ResearchReportPage from "./pages/research/ResearchReportPage";
import ComparePage from "./pages/companies/ComparePage";

/** Route the scouting workflow without bundling or silently loading test fixtures. */
export default function App() {
  const { pathname } = useLocation();
  const terminal =
    pathname === "/" ||
    pathname.startsWith("/companies/") ||
    pathname.startsWith("/research/");
  return (
    <div className={`app-shell ${terminal ? "terminal-view" : ""}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <NavLink to="/" className="brand">
          <span className="brand-symbol">
            <Icon name="activity" />
          </span>
          <strong>SignalShift</strong>
          <span className="terminal-tag">RESEARCH</span>
        </NavLink>
        <div className="terminal-breadcrumb">
          Company intelligence <span>/</span> Startup outlook
        </div>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            Companies
          </NavLink>
          <NavLink to="/explore">Compare & explore</NavLink>
          <NavLink to="/methodology">Methodology</NavLink>
        </nav>
      </header>
      <main id="main" tabIndex={terminal ? -1 : 0}>
        <Routes>
          <Route path="/" element={<CompanyHomePage />} />
          <Route
            path="/research/new/:snapshotId/:companyId"
            element={<StartResearchPage />}
          />
          <Route path="/research/new" element={<StartResearchPage />} />
          <Route
            path="/research/identities/:identityId"
            element={<StartResearchPage />}
          />
          <Route
            path="/research/v2/jobs/:jobId"
            element={<ResearchJobPage />}
          />
          <Route
            path="/research/v2/reports/:reportId"
            element={<ResearchReportPage />}
          />
          <Route path="/research/jobs/:jobId" element={<ResearchJobPage />} />
          <Route
            path="/research/reports/:reportId"
            element={<ResearchReportPage />}
          />
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
        <span>
          Evidence-backed research · Forecasts unavailable until validated
        </span>
        <div>
          <NavLink to="/traction">Traction research</NavLink>
          {" · "}
          <NavLink to="/data-health">Data health</NavLink>
        </div>
      </footer>
    </div>
  );
}
