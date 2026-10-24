import { useParams } from "react-router-dom";
import { QueryState } from "../../components/Common";
import CompanyDossier from "../research/CompanyDossier";
import { useCompany } from "./shared";

/** Open an exact saved company in the same dossier as fresh research. */
export default function CompanyProfilePage() {
  const { snapshotId = "", companyId = "" } = useParams();
  const query = useCompany(snapshotId, companyId);
  return (
    <>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && <CompanyDossier profile={query.data} />}
    </>
  );
}
