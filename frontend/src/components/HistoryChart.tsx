import { useEffect, useRef } from "react";
import { init, use } from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  TooltipComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { DTO } from "../api/client";

use([LineChart, GridComponent, TooltipComponent, AriaComponent, SVGRenderer]);

/** Plot observed intervals only; gaps remain gaps and no forecast curve is invented. */
export default function HistoryChart({
  points,
}: {
  points: DTO<"HistoryPoint">[];
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current || points.length === 0) return;
    const styles = getComputedStyle(element.current);
    const themed = styles.getPropertyValue("--theme-canvas").trim() !== "";
    const colour = (token: string) => styles.getPropertyValue(token).trim();
    const axisTheme = themed
      ? {
          axisLabel: { color: colour("--theme-muted") },
          axisLine: { lineStyle: { color: colour("--theme-control-line") } },
          splitLine: { lineStyle: { color: colour("--theme-line") } },
        }
      : {};
    const chart = init(element.current, undefined, { renderer: "svg" });
    chart.setOption({
      animation: false,
      aria: {
        enabled: true,
        description:
          "Observed package downloads. Missing observations are gaps. Exact values follow in the history table.",
      },
      grid: { left: 64, right: 24, top: 24, bottom: 48 },
      tooltip: {
        trigger: "axis",
        renderMode: "richText",
        ...(themed
          ? {
              backgroundColor: colour("--theme-raised"),
              borderColor: colour("--theme-control-line"),
              textStyle: { color: colour("--theme-text") },
            }
          : {}),
      },
      xAxis: {
        type: "category",
        ...axisTheme,
        data: points.map((point) => point.window.start.slice(0, 10)),
      },
      yAxis: { type: "value", min: 0, ...axisTheme },
      series: [
        {
          type: "line",
          data: points.map((point) => point.downloads),
          connectNulls: false,
          symbol: "circle",
          symbolSize: 8,
          lineStyle: {
            color: themed ? colour("--theme-accent") : "#187153",
            width: 2,
          },
          ...(themed ? { itemStyle: { color: colour("--theme-accent") } } : {}),
        },
      ],
    });
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(element.current);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  }, [points]);
  return <div className="history-chart" ref={element} />;
}
