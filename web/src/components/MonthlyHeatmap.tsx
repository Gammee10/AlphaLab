export function MonthlyHeatmap({ buckets, label }: { buckets: { period: string; netPnl: string; trades: number }[]; label: string }) {
  if (buckets.length === 0) return null;
  return (
    <div className="chart-card card">
      <div className="chart-title">
        <span>{label}</span>
        <span className="faint">{buckets.length} months</span>
      </div>
      <div className="heatmap">
        {buckets.map((b) => {
          const v = Number(b.netPnl);
          const cls = v > 0 ? "heat-up" : v < 0 ? "heat-down" : "heat-flat";
          return (
            <div key={b.period} className={`heat-cell ${cls}`}>
              <small>{b.period}</small>
              <span className="p">
                {v > 0 ? "+" : ""}
                {v.toFixed(0)}
              </span>
              <small>{b.trades} trades</small>
            </div>
          );
        })}
      </div>
    </div>
  );
}
