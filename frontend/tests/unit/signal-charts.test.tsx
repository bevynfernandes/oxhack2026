import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { DTO } from "../../src/api/client";
import SignalCharts from "../../src/pages/research/SignalCharts";
import {
  downloadBars,
  type DownloadObservation,
} from "../../src/pages/research/signalChartData";

const observations: DownloadObservation[] = [
  {
    id: "previous",
    metric: "npm_downloads_previous_30d_v1",
    value: 2000,
    window: { start: "2026-08-25T00:00:00Z", end: "2026-09-24T00:00:00Z" },
  },
  {
    id: "current",
    metric: "npm_downloads_30d_v1",
    value: 3000,
    window: { start: "2026-09-24T00:00:00Z", end: "2026-10-24T00:00:00Z" },
  },
];
const model: DTO<"DimensionModelView"> = {
  group_id: "adoption_retention",
  architecture: "Ridge",
  model_status: "experimental_trained",
  model_sha256: "test",
  eligibility: "eligible",
  score: 34.2,
  predicted_value: Math.log(4001 / 3001),
  prediction_unit: "log download growth",
  metric_observation_ids: ["previous", "current"],
  target: "SDK downloads",
  limitations: ["Not company-success odds."],
  reason_codes: [],
};

it("reconstructs the model target in download units and preserves the forecast window", () => {
  const bars = downloadBars(observations, model);
  expect(bars.map((row) => row.value)).toEqual([2000, 3000, 4000]);
  expect(bars[2]).toMatchObject({
    estimated: true,
    start: observations[1].window!.end,
    end: "2026-11-23T00:00:00.000Z",
  });
});

it("never treats missing counts as zero and preserves real zero observations", () => {
  expect(downloadBars([{ ...observations[0], value: null }], model)).toEqual(
    [],
  );
  expect(downloadBars([{ ...observations[0], value: 0 }])[0].value).toBe(0);
});

it("uses exact model inputs when fresh reports contain multiple SDK packages", () => {
  const fresh = observations.map((row, index) => ({
    ...row,
    metric:
      index === 0 ? "npm_downloads_previous_30d" : "npm_downloads_latest_30d",
    definition: "Downloads for the verified client SDK",
  }));
  const multiple = [
    ...fresh,
    ...fresh.map((row) => ({ ...row, id: row.id + "-other-sdk", value: 9999 })),
  ];
  expect(downloadBars(multiple, model).map((row) => row.value)).toEqual([
    2000, 3000, 4000,
  ]);
  expect(downloadBars(multiple)).toEqual([]);
  expect(downloadBars(fresh)[0].definition).toContain("verified client SDK");
});

it.each([
  { ...model, eligibility: "unreliable" as const },
  { ...model, prediction_unit: "unknown" },
  { ...model, predicted_value: null },
  { ...model, predicted_value: Infinity },
  { ...model, predicted_value: 1000 },
  { ...model, predicted_value: -1000 },
  { ...model, metric_observation_ids: ["old-current", "old-previous"] },
])("withholds invalid or mismatched forecasts %#", (invalid) => {
  expect(downloadBars(observations, invalid)).toHaveLength(2);
});

it("does not attach an estimate to duplicate, nonadjacent or malformed periods", () => {
  expect(
    downloadBars([...observations, observations[0]], model).every(
      (row) => !row.estimated,
    ),
  ).toBe(true);
  expect(
    downloadBars(
      [
        observations[0],
        {
          ...observations[1],
          window: {
            start: "2026-09-25T00:00:00Z",
            end: "2026-10-25T00:00:00Z",
          },
        },
      ],
      model,
    ),
  ).toHaveLength(2);
  expect(
    downloadBars(
      [{ ...observations[0], window: { start: "bad-date", end: "bad-date" } }],
      model,
    ),
  ).toEqual([]);
});

it("provides exact readable values, forecast caveats and keyboard-accessible evidence", () => {
  const inspect = vi.fn();
  render(
    <SignalCharts
      observations={observations}
      models={
        {
          dimensions: [model],
          as_of: "2026-10-24T00:00:00Z",
        } as DTO<"CompanyDimensionModels">
      }
      onEvidence={inspect}
    />,
  );
  expect(screen.getByText("2,000")).toBeVisible();
  expect(screen.getByText("≈ 4,000")).toBeVisible();
  expect(screen.getByText(/uncertainty interval unavailable/)).toBeVisible();
  screen.getByRole("button", { name: "Inspect chart evidence" }).click();
  expect(inspect).toHaveBeenCalledOnce();
});

it("shows an honest empty state without inventing a timeline", () => {
  render(<SignalCharts observations={[]} onEvidence={vi.fn()} />);
  expect(screen.getByText(/missing data is not zero/)).toBeVisible();
  expect(screen.queryByText("Next 30 days · estimate")).toBeNull();
});
