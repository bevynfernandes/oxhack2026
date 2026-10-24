import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { QueryState } from "../../components/Common";
import CompanyDossier from "./CompanyDossier";
import { fetchResearchReport } from "./client";

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

export default function ResearchReportPage() {
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
