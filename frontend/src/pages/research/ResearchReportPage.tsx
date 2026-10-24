import { useQuery } from "@tanstack/react-query";
import { useParams, useLocation } from "react-router-dom";
import { QueryState } from "../../components/Common";
import CompanyDossier from "./CompanyDossier";
import { fetchResearchReport, fetchStandaloneReport } from "./client";

/** Present the exact report without deriving model policy in the browser. */
export function ResearchWorkspace({
  report,
}: {
  report: Awaited<ReturnType<typeof fetchResearchReport>>;
}) {
  return (
    <CompanyDossier profile={report.inventory.saved_context} report={report} />
  );
}

function LegacyReportPage() {
  const { reportId = "" } = useParams();
  const query = useQuery({
    queryKey: ["research-report", reportId],
    queryFn: () => fetchResearchReport(reportId),
  });
  return (
    <>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && <ResearchWorkspace key={reportId} report={query.data} />}
    </>
  );
}

export default function ResearchReportPage() {
  const { pathname } = useLocation();
  return pathname.startsWith("/research/v2/") ? (
    <StandaloneReportPage />
  ) : (
    <LegacyReportPage />
  );
}
function StandaloneReportPage() {
  const { reportId = "" } = useParams();
  const query = useQuery({
    queryKey: ["research-v2-report", reportId],
    queryFn: () => fetchStandaloneReport(reportId),
  });
  return (
    <>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && (
        <CompanyDossier
          key={reportId}
          profile={query.data.identity.saved_context ?? undefined}
          standalone={query.data}
        />
      )}
    </>
  );
}
