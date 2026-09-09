import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { OverlayChart } from "../charts";
import { deltaClass, fmtMoney, normalize } from "../format";

export function Compare({ seedRunId }: { seedRunId: string | null }) {
  const [ids, setIds] = useState<string>(seedRunId ?? "");
  const [name, setName] = useState("comparison");
  const [experimentId, setExperimentId] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => {
      const runIds = ids.split(/[,\s]+/).filter(Boolean);
      return api.createExperiment({ name, runIds, baselineRunId: runIds[0] });
    },
    onSuccess: (data) => setExperimentId(data.experiment.id),
  });
  const experiment = useQuery({
    queryKey: ["experiment", experimentId],
    queryFn: () => api.experiment(experimentId!),
    enabled: experimentId !== null,
  });
  const runs = useQuery({
    queryKey: ["compare-runs", experiment.data?.runs.map((r) => r.id).join(",")],
    queryFn: async () => {
      const list = experiment.data!.runs;
      return Promise.all(list.map((r) => api.run(r.id)));
    },
    enabled: !!experiment.data,
  });

  return (
    <div>
      <h2>Compare</h2>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Run ids (comma/space separated, 2–32)
        <input value={ids} onChange={(e) => setIds(e.target.value)} size={60} />
      </label>
      <button onClick={() => create.mutate()}>Compare</button>
      {experiment.data && (
        <>
          <h3>What changed vs baseline</h3>
          <ul>
            {experiment.data.diff.map((d) => (
              <li key={d}>
                <code>{d}</code>
              </li>
            ))}
          </ul>
          <h3>Metric deltas</h3>
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
                    <code>{rid.slice(0, 8)}</code>
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
          {runs.data && (
            <>
              <h3>Normalized equity (% from own start)</h3>
              <OverlayChart
                curves={runs.data.map((r) => ({ label: r.run.id.slice(0, 8), points: normalize(r.run.equityCurve) }))}
              />
              <ul>
                {runs.data.map((r) => (
                  <li key={r.run.id}>
                    <code>{r.run.id.slice(0, 8)}</code> net {fmtMoney(r.run.metrics.netProfit)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
