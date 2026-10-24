import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import {
  metricValue,
  windowLabel,
  modeLabel,
  QueryState,
  SyntheticNotice,
  Reasons,
  SourceLink,
  Provenance,
} from "../../components/Common";

export default function EvaluationPage() {
  const { evaluationId = "" } = useParams();
  const query = useQuery({
    queryKey: ["evaluation", evaluationId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/evaluations/{evaluation_id}", {
          params: { path: { evaluation_id: evaluationId } },
          signal,
        }),
      ),
  });
  const report = query.data;
  return (
    <>
      <h1>Evaluation</h1>
      <QueryState
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {report && (
        <>
          <SyntheticNotice synthetic={report.provenance.synthetic} />
          <p className="eyebrow">
            {report.ecosystem} · {report.status} · {modeLabel(report.mode)}
          </p>
          <section className="panel">
            <h2>What the evidence supports</h2>
            <p>{report.conclusion}</p>
            <p>Test period: {windowLabel(report.test_window)}</p>
            <p>
              {report.origin_count} origins · {report.organization_count}{" "}
              organizations · {report.sample_count} samples
            </p>
            <h3>Limitations</h3>
            <Reasons reasons={report.limitations} />
            <h3>Exclusions</h3>
            <Reasons reasons={report.exclusions} />
            <h3>Missingness</h3>
            <Reasons reasons={report.missingness} />
          </section>
          <section className="panel">
            <h2>Model, baseline and source comparisons</h2>
            <div className="table-scroll">
              <table>
                <caption>
                  Published metrics on their stated candidate sets
                </caption>
                <thead>
                  <tr>
                    <th>Model / ablation</th>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Direction</th>
                    <th>Sample count</th>
                    <th>Common rows</th>
                    <th>Limitations</th>
                  </tr>
                </thead>
                <tbody>
                  {report.metrics.map((metric, index) => (
                    <tr key={index}>
                      <th scope="row">{metric.model_id}</th>
                      <td>{metric.name}</td>
                      <td>
                        {metricValue(metric.value)} {metric.unit}
                      </td>
                      <td>
                        {metric.lower_is_better === null
                          ? "Descriptive"
                          : metric.lower_is_better
                            ? "Lower is better"
                            : "Higher is better"}
                      </td>
                      <td>{metric.sample_count}</td>
                      <td>{metric.common_rows_id ?? "Not supplied"}</td>
                      <td>
                        <Reasons reasons={metric.limitations} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {report.metrics.length === 0 && (
              <p>No evaluation metrics were published.</p>
            )}
            <h3>Interval validation</h3>
            <Reasons reasons={report.interval_findings} />
          </section>
          <section className="panel">
            <h2>Reproduce the evaluation</h2>
            <ul>
              {report.reports.map((link) => (
                <li key={link.url}>
                  <SourceLink url={link.url}>{link.label}</SourceLink>
                </li>
              ))}
            </ul>
            <Provenance provenance={report.provenance} />
          </section>
        </>
      )}
    </>
  );
}
