import { useEffect, useRef, useState } from "react";
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
import { useUi } from "./store";

function palette(theme: "dark" | "light") {
  return theme === "dark"
    ? {
        text: "#98a39d",
        grid: "rgba(255, 255, 255, 0.05)",
        up: "#3ddc97",
        down: "#f2555a",
        accent: "#3ddc97",
        accentTop: "rgba(61, 220, 151, 0.26)",
        accentBottom: "rgba(61, 220, 151, 0.01)",
        ddTop: "rgba(242, 85, 90, 0.22)",
        ddBottom: "rgba(242, 85, 90, 0.01)",
        series: ["#3ddc97", "#e8b45f", "#5aa9e6", "#f2555a", "#8fd694"],
      }
    : {
        text: "#55605b",
        grid: "rgba(9, 20, 14, 0.07)",
        up: "#0e9f64",
        down: "#d92d3a",
        accent: "#0e9f64",
        accentTop: "rgba(14, 159, 100, 0.22)",
        accentBottom: "rgba(14, 159, 100, 0.01)",
        ddTop: "rgba(217, 45, 58, 0.18)",
        ddBottom: "rgba(217, 45, 58, 0.01)",
        series: ["#0e9f64", "#b06f16", "#2563eb", "#d92d3a", "#0d9488"],
      };
}

function useChart(ref: React.RefObject<HTMLDivElement | null>, height: number): React.MutableRefObject<IChartApi | null> {
  const chartRef = useRef<IChartApi | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const c = palette(document.documentElement.dataset.theme === "light" ? "light" : "dark");
    const chart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: c.text },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
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

export function PriceChart({ bars, trades, height = 360 }: { bars: Bar[]; trades: Trade[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useChart(ref, height);
  const { theme } = useUi();

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || bars.length === 0) return;
    const c = palette(theme);
    const series: ISeriesApi<"Candlestick"> = chart.addSeries(CandlestickSeries, {
      upColor: c.up,
      downColor: c.down,
      wickUpColor: c.up,
      wickDownColor: c.down,
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
          color: t.direction === "long" ? c.up : c.down,
          shape: t.direction === "long" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: t.direction === "long" ? "L" : "S",
        });
      }
      if (t.exitTime) {
        out.push({
          time: Math.floor(t.exitTime / 1000) as UTCTimestamp,
          position: t.direction === "long" ? ("aboveBar" as const) : ("belowBar" as const),
          color: c.down,
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
  }, [chartRef, bars, trades, theme]);

  if (bars.length === 0) return <p className="muted" style={{ fontSize: "0.88rem" }}>No price data in range.</p>;
  return <div ref={ref} style={{ width: "100%" }} />;
}

export function EquityChart({ curve, height = 240 }: { curve: [number, string][]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useChart(ref, height);
  const { theme } = useUi();

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || curve.length === 0) return;
    const c = palette(theme);
    const data = curve.map(([t, e]) => ({ time: Math.floor(t / 1000) as UTCTimestamp, value: Number(e) }));
    const area = chart.addSeries(AreaSeries, {
      lineColor: c.accent,
      topColor: c.accentTop,
      bottomColor: c.accentBottom,
      lineWidth: 2,
    });
    area.setData(data);
    let peak = -Infinity;
    const dd = data.map((p) => {
      peak = Math.max(peak, p.value);
      return { time: p.time, value: p.value - peak };
    });
    const ddSeries = chart.addSeries(AreaSeries, {
      lineColor: c.down,
      topColor: c.ddTop,
      bottomColor: c.ddBottom,
      priceScaleId: "dd",
    });
    chart.priceScale("dd").applyOptions({ scaleMargins: { top: 0.72, bottom: 0 } });
    ddSeries.setData(dd);
    chart.timeScale().fitContent();
    return () => {
      chart.removeSeries(area);
      chart.removeSeries(ddSeries);
    };
  }, [chartRef, curve, theme]);

  if (curve.length === 0) return <p className="muted" style={{ fontSize: "0.88rem" }}>No equity data.</p>;
  return <div ref={ref} style={{ width: "100%" }} />;
}

const ALL_SERIES_COLORS = palette("dark").series.concat(palette("light").series);

export function MultiEquity({ curves, height = 280 }: { curves: { label: string; points: { t: number; pct: number }[] }[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useChart(ref, height);
  const { theme } = useUi();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const visible = curves.filter((c) => !hidden.has(c.label));

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const c = palette(theme);
    const series = visible.map((cv, i) => {
      const s = chart.addSeries(LineSeries, {
        color: c.series[i % c.series.length],
        title: cv.label,
        lineWidth: 2,
      });
      s.setData(cv.points.map((p) => ({ time: Math.floor(p.t / 1000) as UTCTimestamp, value: p.pct })));
      return s;
    });
    chart.timeScale().fitContent();
    return () => {
      series.forEach((s) => chart.removeSeries(s));
    };
  }, [chartRef, visible, theme]);

  if (curves.length === 0) return <p className="muted" style={{ fontSize: "0.88rem" }}>No curves to compare.</p>;

  return (
    <div>
      <div ref={ref} style={{ width: "100%" }} />
      <div className="legend" style={{ marginTop: "0.55rem" }}>
        {curves.map((cv, i) => {
          const off = hidden.has(cv.label);
          const color = ALL_SERIES_COLORS[i % ALL_SERIES_COLORS.length];
          return (
            <button
              key={cv.label}
              className={`legend-item${off ? " off" : ""}`}
              onClick={() =>
                setHidden((prev) => {
                  const next = new Set(prev);
                  if (next.has(cv.label)) next.delete(cv.label);
                  else next.add(cv.label);
                  return next;
                })
              }
            >
              <span className="legend-dot" style={{ background: color }} />
              <code>{cv.label}</code>
            </button>
          );
        })}
      </div>
    </div>
  );
}
