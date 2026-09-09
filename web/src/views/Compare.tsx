import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { MultiEquity } from "../charts";
import { Badge, ErrorNotice, Loading, PageHead } from "../components/ui";
import { deltaClass, fmtMoney, normalize } from "../format";

export function Compare({ seedRunId, onOpenRun }: { seedRunId: string | null; onOpenRun: (id: string) => void }) {
  const [ids, setIds] = useState<string>(seedRunId ?? "");
  const [name, setName] = useState("comparison");
  const [experimentId, setExperimentId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => {
      const runIds = ids.split(/[,\s]+/).filter(Boolean);
      return api.createExperiment({ name, runIds, baselineRunId: runIds[0] });
    },
    onSuccess: (data) => {
      setExperimentId(data.experiment.id);
      setError("");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });
  const experiment = useQuery({
    queryKey: ["experiment", experimentId],
    queryFn: () => api.experiment(experimentId!),
    enabled: experimentId !== null,
  });
  const runs = useQuery({
    queryKey: ["compare-runs", experiment.data?.runs.map((r) => r.id).join(",")],
    queryFn: async () => Promise.all(experiment.data!.runs.map((r) => api.run(r.id))),
    enabled: !!experiment.data,
  });

  return (
    <div>
      <PageHead title="Compare runs" sub="Material differences against the baseline first, then metric deltas and normalized equity." />

      <div className="card" style={{ maxWidth: 860 }}>
        <div className="field-row">
          <label className="field">
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field" style={{ maxWidth: 460, flex: 1 }}>
            Run ids (comma/space separated, 2–32)
            <input value={ids} onChange={(e) => setIds(e.target.value)} placeholder="e.g. 1a2b3c4d, 5e6f7081" />
          </label>
          <button className="btn primary" onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? "Comparing…" : "Compare"}
          </button>
        </div>
        {error && <ErrorNotice message={error} />}
      </div>

      {experiment.isLoading && <Loading text="Building experiment…" />}

      {experiment.data && (
        <>
          <h3 className="section-title">What changed vs baseline</h3>
          <div className="card">
            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {experiment.data.diff.map((d) => (
                <Badge key={d} kind="neutral">
                  {d}
                </Badge>
              ))}
            </div>
          </div>

          <h3 className="section-title">Metric deltas</h3>
          <div className="card table-card">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Δ net</th>
                  <th>Δ PF</th>
                  <th>Δ maxDD</th>
                  <th>Δ win rate</th>
                  <th>Δ trades</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(experiment.data.deltas).map(([rid, d]) => (
                  <tr key={rid}>
                    <td>
                      <button className="link" onClick={() => onOpenRun(rid)}>
                        <code>{rid.slice(0, 8)}</code>
                      </button>
                    </td>
                    {(["netProfit", "profitFactor", "maxDrawdown", "winRate", "tradeCount"] as const).map((k) => (
                      <td key={k} className={deltaClass(d[k])}>
                        {d[k] === null || d[k] === undefined ? "—" : Number(d[k]).toFixed(2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {runs.isLoading && <Loading text="Loading equity curves…" />}
          {runs.data && (
            <div className="chart-card card">
              <div className="chart-title">
                <span>Normalized equity</span>
                <span className="faint">% from own start — comparable across capitals</span>
              </div>
              <MultiEquity curves={runs.data.map((r) => ({ label: r.run.id.slice(0, 8), points: normalize(r.run.equityCurve) }))} />
              <div style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", marginTop: "0.4rem" }}>
                {runs.data.map((r) => (
                  <span key={r.run.id} className="muted" style={{ fontSize: "0.85rem" }}>
                    <code>{r.run.id.slice(0, 8)}</code> net <span className={deltaClass(Number(r.run.metrics.netProfit))}>{fmtMoney(r.run.metrics.netProfit)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
