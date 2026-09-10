export function MonthlyHeatmap({ buckets }: { buckets: { period: string; netPnl: string; trades: number }[] }) {
  if (buckets.length === 0) return <p className="muted" style={{ fontSize: "0.88rem" }}>No monthly data.</p>;
  return (
    <div className="glass">
      <div className="heat-grid">
        {buckets.map((b) => {
          const v = Number(b.netPnl);
          const cls = v > 0 ? "heat-up" : v < 0 ? "heat-down" : "";
          return (
            <div key={b.period} className={`heat-cell${cls ? ` ${cls}` : ""}`}>
              <small>{b.period}</small>
              <span className="hp">
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
