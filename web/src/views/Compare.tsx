import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { navigate } from "../router";
import { errText, useUi } from "../store";
import { MultiEquity } from "../charts";
import {
  Badge,
  CardHead,
  EmptyState,
  ErrorInline,
  Loading,
  Modal,
  PageHead,
  SectionLabel,
} from "../components/ui";
import { IcChart, IcPlus, IcSearch, IcX } from "../components/icons";
import { deltaClass, fmtMoney, normalize, shortHash } from "../format";

export function Compare({ seedRunId }: { seedRunId: string | null }) {
  const runs = useQuery({ queryKey: ["runs-50"], queryFn: () => api.runs(50) });
  const { toast } = useUi();

  const [ids, setIds] = useState<string[]>(seedRunId ? [seedRunId] : []);
  const [name, setName] = useState("comparison");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState("");
  const [experimentId, setExperimentId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => api.createExperiment({ name, runIds: ids, baselineRunId: ids[0] }),
    onSuccess: (data) => {
      setExperimentId(data.experiment.id);
      setError("");
      toast("Experiment created", "ok");
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
  });

  const experiment = useQuery({
    queryKey: ["experiment", experimentId],
    queryFn: () => api.experiment(experimentId!),
    enabled: experimentId !== null,
  });
  const detailRuns = useQuery({
    queryKey: ["compare-runs", experiment.data?.runs.map((r) => r.id).join(",")],
    queryFn: async () => Promise.all(experiment.data!.runs.map((r) => api.run(r.id))),
    enabled: !!experiment.data,
  });

  const pickerList = useMemo(() => {
    const all = runs.data?.runs ?? [];
    const needle = pickerSearch.trim().toLowerCase();
    return needle ? all.filter((r) => r.resultHash.toLowerCase().includes(needle)) : all;
  }, [runs.data, pickerSearch]);

  const toggleId = (rid: string) =>
    setIds((prev) => (prev.includes(rid) ? prev.filter((x) => x !== rid) : prev.length >= 32 ? prev : [...prev, rid]));

  const canCompare = ids.length >= 2 && ids.length <= 32;

  return (
    <div>
      <PageHead
        eyebrow="Experiments"
        title="Compare runs"
        sub="Material differences against the baseline first, then metric deltas and normalized equity."
        actions={
          <button className="btn glass" onClick={() => setPickerOpen(true)}>
            <IcPlus size={14} />
            Add runs
          </button>
        }
      />

      <div className="glass">
        <div className="field-row">
          <label className="field">
            <span className="field-label">Experiment name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} style={{ maxWidth: 240 }} />
          </label>
          <button
            className="btn primary"
            disabled={!canCompare || experimentId !== null}
            onClick={() => create.mutate()}
            title={canCompare ? "" : "Select 2–32 runs first"}
          >
            Compare {ids.length} run{ids.length === 1 ? "" : "s"}
          </button>
        </div>

        <SectionLabel>Selection</SectionLabel>
        {ids.length === 0 ? (
          <p className="muted" style={{ fontSize: "0.88rem" }}>
            No runs selected — pick at least two from the run list.
          </p>
        ) : (
          <div className="row-wrap">
            {ids.map((rid, i) => (
              <span key={rid} className="row-wrap" style={{ gap: "0.3rem", background: "var(--inset)", border: "1px solid var(--border)", borderRadius: 999, padding: "0.2rem 0.4rem 0.2rem 0.8rem" }}>
                {i === 0 && <Badge kind="acc">baseline</Badge>}
                <code>{rid.slice(0, 8)}</code>
                <button className="mini-btn danger" style={{ borderRadius: 999, padding: "0.05rem 0.45rem" }} onClick={() => toggleId(rid)} aria-label="Remove">
                  <IcX size={11} />
                </button>
              </span>
            ))}
          </div>
        )}
        {error && <ErrorInline text={error} />}
      </div>

      {experiment.isLoading && <Loading text="Building experiment…" />}

      {experiment.data && (
        <>
          <SectionLabel>What changed vs baseline</SectionLabel>
          <div className="glass">
            <div className="row-wrap">
              {experiment.data.diff.map((d) => (
                <span key={d} className="rule-chip" style={{ color: "var(--text-2)" }}>
                  {d}
                </span>
              ))}
            </div>
          </div>

          <SectionLabel>Metric deltas</SectionLabel>
          <div className="glass" style={{ padding: 0, overflow: "hidden" }}>
            <div className="card-head" style={{ padding: "0.9rem 0.95rem 0", marginBottom: 0 }}>
              <span className="card-icon">
                <IcChart size={14} />
              </span>
              <span className="card-title">Metric deltas vs baseline</span>
            </div>
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
                      <button className="link" onClick={() => navigate(`/run/${rid}`)} style={{ background: "none", border: "none", cursor: "pointer", font: "inherit" }}>
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

          {detailRuns.isLoading && <Loading text="Loading equity curves…" />}
          {detailRuns.data && (
            <div className="chart-panel glass">
              <CardHead
                icon={<IcChart size={14} />}
                title="Normalized equity"
                right={<span className="faint" style={{ fontSize: "0.75rem" }}>% from own start — comparable across capitals</span>}
              />
              <MultiEquity curves={detailRuns.data.map((r) => ({ label: r.run.id.slice(0, 8), points: normalize(r.run.equityCurve) }))} />
              <div className="row-wrap" style={{ marginTop: "0.5rem" }}>
                {detailRuns.data.map((r) => (
                  <span key={r.run.id} className="muted" style={{ fontSize: "0.83rem" }}>
                    <code>{r.run.id.slice(0, 8)}</code> net{" "}
                    <span className={deltaClass(Number(r.run.metrics.netProfit))}>{fmtMoney(r.run.metrics.netProfit)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {pickerOpen && (
        <Modal title="Pick runs to compare" onClose={() => setPickerOpen(false)} wide>
          <div className="row-wrap" style={{ marginBottom: "0.8rem" }}>
            <IcSearch size={14} />
            <input
              autoFocus
              value={pickerSearch}
              onChange={(e) => setPickerSearch(e.target.value)}
              placeholder="Filter by run hash…"
              style={{ flex: 1 }}
            />
            <Badge kind="neutral">{ids.length}/32 selected</Badge>
          </div>
          {runs.isLoading ? (
            <Loading text="Loading runs…" />
          ) : pickerList.length === 0 ? (
            <EmptyState title="No runs found">No run matches that hash filter.</EmptyState>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Pick</th>
                  <th>Run</th>
                  <th>Trades</th>
                  <th>Net</th>
                  <th>PF</th>
                </tr>
              </thead>
              <tbody>
                {pickerList.map((r) => {
                  const picked = ids.includes(r.id);
                  return (
                    <tr key={r.id} className={picked ? "selected" : ""}>
                      <td>
                        <input type="checkbox" checked={picked} onChange={() => toggleId(r.id)} />
                      </td>
                      <td>
                        <code>{shortHash(r.resultHash)}</code>
                      </td>
                      <td>{r.tradeCount ?? "—"}</td>
                      <td className={deltaClass(r.netProfit === null ? null : Number(r.netProfit))}>
                        {r.netProfit === null ? "—" : fmtMoney(r.netProfit)}
                      </td>
                      <td>{r.profitFactor === null ? "—" : r.profitFactor.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.9rem" }}>
            <button className="btn primary sm" onClick={() => setPickerOpen(false)}>
              Done
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
