import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../api/client";
import {
  date,
  QueryState,
  SyntheticNotice,
  Reasons,
} from "../../components/Common";

export default function DataHealthPage() {
  const query = useQuery({
    queryKey: ["data-health"],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/data-health", { signal })),
  });
  return (
    <>
      <h1>Data health</h1>
      <p>
        Source freshness, coverage and mapping quality are separate from
        forecast validation.
      </p>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && (
        <>
          <SyntheticNotice synthetic={query.data.synthetic} />
          {query.data.sources.length === 0 && (
            <p>No source health report has been published.</p>
          )}
          {query.data.sources.map((source, index) => (
            <section className="panel" key={index}>
              <h2>
                {source.source} {source.ecosystem && `· ${source.ecosystem}`}
              </h2>
              <dl className="metadata">
                <div>
                  <dt>Connector</dt>
                  <dd>{source.connector_status}</dd>
                </div>
                <div>
                  <dt>Freshness</dt>
                  <dd>
                    {source.freshness.stale ? "Stale" : "Current"} ·{" "}
                    {date(source.freshness.as_of)}
                  </dd>
                </div>
                <div>
                  <dt>Completeness</dt>
                  <dd>{source.freshness.completeness}</dd>
                </div>
                <div>
                  <dt>Missing partitions</dt>
                  <dd>{source.missing_partitions}</dd>
                </div>
                <div>
                  <dt>Revisions</dt>
                  <dd>{source.revisions}</dd>
                </div>
                <div>
                  <dt>Mapping</dt>
                  <dd>{source.mapping_status}</dd>
                </div>
              </dl>
              <Reasons reasons={source.freshness.reasons ?? []} />
            </section>
          ))}
        </>
      )}
    </>
  );
}
