import type { DTO } from "../../api/client";

export type DownloadObservation = {
  id: string;
  metric: string;
  value: number | null;
  definition?: string;
  window: { start: string; end: string } | null;
};
export type DownloadBar = {
  label: string;
  value: number;
  start: string;
  end: string;
  estimated: boolean;
  definition?: string;
};

/** Plot exact published windows; invert only the eligible model's documented log target. */
export function downloadBars(
  observations: DownloadObservation[],
  model?: DTO<"DimensionModelView">,
): DownloadBar[] {
  const metrics = [
    ["npm_downloads_previous_30d_v1", "npm_downloads_previous_30d"],
    ["npm_downloads_30d_v1", "npm_downloads_latest_30d"],
  ];
  const selected = metrics.map((aliases) => {
    const candidates = observations.filter((row) =>
      aliases.includes(row.metric),
    );
    const inputs =
      model?.eligibility === "eligible"
        ? candidates.filter((row) =>
            model.metric_observation_ids.includes(row.id),
          )
        : [];
    const matches = inputs.length ? inputs : candidates;
    return matches.length === 1 ? matches[0] : undefined;
  });
  const bars = selected.flatMap((row, index): DownloadBar[] => {
    if (
      !row?.window ||
      row.value == null ||
      !Number.isSafeInteger(row.value) ||
      row.value < 0 ||
      !Number.isFinite(Date.parse(row.window.start)) ||
      Date.parse(row.window.end) - Date.parse(row.window.start) !==
        30 * 86400000
    )
      return [];
    return [
      {
        label: index === 0 ? "Previous 30 days" : "Latest 30 days",
        value: row.value,
        start: row.window.start,
        end: row.window.end,
        estimated: false,
        definition: row.definition,
      },
    ];
  });
  const previous = selected[0];
  const current = selected[1];
  if (
    bars.length !== 2 ||
    !previous ||
    !current ||
    Date.parse(bars[0].end) !== Date.parse(bars[1].start) ||
    model?.group_id !== "adoption_retention" ||
    model.eligibility !== "eligible" ||
    model.prediction_unit !== "log download growth" ||
    model.predicted_value == null ||
    !Number.isFinite(model.predicted_value) ||
    ![previous.id, current.id].every((id) =>
      model.metric_observation_ids.includes(id),
    )
  )
    return bars;
  // Backend target: log((next_30d_downloads + 1) / (current_30d_downloads + 1)).
  const estimate = Math.exp(model.predicted_value) * (bars[1].value + 1) - 1;
  if (
    !Number.isFinite(estimate) ||
    estimate < 0 ||
    estimate > Number.MAX_SAFE_INTEGER
  )
    return bars;
  return [
    ...bars,
    {
      label: "Next 30 days · estimate",
      value: Math.round(estimate),
      start: bars[1].end,
      end: new Date(Date.parse(bars[1].end) + 30 * 86400000).toISOString(),
      estimated: true,
    },
  ];
}
