import { useEffect, useRef } from "react";
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Bar, Trade } from "./api";

const TEXT = "#8b93a3";
const GRID = "rgba(35, 44, 61, 0.6)";
const UP = "#26a69a";
const DOWN = "#ef5350";

function useChart(ref: React.RefObject<HTMLDivElement>, height: number): React.MutableRefObject<IChartApi | null> {
  const chartRef = useRef<IChartApi | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: TEXT },
      grid: { vertLines: { color: GRID }, horzLines: { color: GRID } },
      width: el.clientWidth || 640,
      height,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth || 640 }));
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [ref, height]);
  return chartRef;
}

function exitLabel(reason: string): string {
  if (reason === "stop") return "SL";
  if (reason === "target") return "TP";
  if (reason === "trailing") return "TS";
  if (reason === "time") return "T";
  if (reason === "opposite") return "REV";
  return "×";
}

export function PriceChart({ bars, trades, height = 380 }: { bars: Bar[]; trades: Trade[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useChart(ref, height);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || bars.length === 0) return;
    const series: ISeriesApi<"Candlestick"> = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
      borderVisible: false,
    });
    series.setData(
      bars.map((b) => ({ time: b.time as UTCTimestamp, open: b.open, high: b.high, low: b.low, close: b.close })),
    );
    const markers = trades.flatMap((t) => {
      const out = [];
      if (t.entryTime) {
        out.push({
          time: Math.floor(t.entryTime / 1000) as UTCTimestamp,
          position: t.direction === "long" ? ("belowBar" as const) : ("aboveBar" as const),
          color: t.direction === "long" ? UP : DOWN,
          shape: t.direction === "long" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: t.direction === "long" ? "L" : "S",
        });
      }
      if (t.exitTime) {
        out.push({
          time: Math.floor(t.exitTime / 1000) as UTCTimestamp,
          position: t.direction === "long" ? ("aboveBar" as const) : ("belowBar" as const),
          color: DOWN,
          shape: t.direction === "long" ? ("arrowDown" as const) : ("arrowUp" as const),
          text: exitLabel(t.exitReason),
        });
      }
      return out;
    });
    if (markers.length > 0) createSeriesMarkers(series, markers);
    chart.timeScale().fitContent();
    return () => {
      chart.removeSeries(series);
    };
  }, [chartRef, bars, trades]);

  if (bars.length === 0) return <p className="muted">No price data in range.</p>;
  return <div ref={ref} style={{ width: "100%" }} />;
}

export function EquityChart({ curve, height = 220 }: { curve: [number, string][]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useChart(ref, height);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || curve.length === 0) return;
    const data = curve.map(([t, e]) => ({ time: Math.floor(t / 1000) as UTCTimestamp, value: Number(e) }));
    const area = chart.addSeries(AreaSeries, { lineColor: "#2f81f7", topColor: "rgba(47,129,247,0.35)", bottomColor: "rgba(47,129,247,0.02)" });
    area.setData(data);
    // Drawdown pane (equity minus running peak) on an overlay scale.
    let peak = -Infinity;
    const dd = data.map((p) => {
      peak = Math.max(peak, p.value);
      return { time: p.time, value: p.value - peak };
    });
    const ddSeries = chart.addSeries(AreaSeries, {
      lineColor: DOWN,
      topColor: "rgba(239,83,80,0.25)",
      bottomColor: "rgba(239,83,80,0.02)",
      priceScaleId: "dd",
    });
    chart.priceScale("dd").applyOptions({ scaleMargins: { top: 0.7, bottom: 0 } });
    ddSeries.setData(dd);
    chart.timeScale().fitContent();
    return () => {
      chart.removeSeries(area);
      chart.removeSeries(ddSeries);
    };
  }, [chartRef, curve]);

  if (curve.length === 0) return <p className="muted">No equity data.</p>;
  return <div ref={ref} style={{ width: "100%" }} />;
}

export function MultiEquity({ curves, height = 260 }: { curves: { label: string; points: { t: number; pct: number }[] }[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useChart(ref, height);
  const colors = ["#26a69a", "#2f81f7", "#ef5350", "#7a5af8", "#e2a63d"];

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const series = curves.map((c, i) => {
      const s = chart.addSeries(LineSeries, { color: colors[i % colors.length], title: c.label, lineWidth: 2 });
      s.setData(c.points.map((p) => ({ time: Math.floor(p.t / 1000) as UTCTimestamp, value: p.pct })));
      return s;
    });
    chart.timeScale().fitContent();
    return () => {
      series.forEach((s) => chart.removeSeries(s));
    };
  }, [chartRef, curves]);

  return <div ref={ref} style={{ width: "100%" }} />;
}
