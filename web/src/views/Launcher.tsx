import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "../api";
import { PriceChart } from "../charts";
import { Badge, ErrorNotice, IconAlert, PageHead } from "../components/ui";

interface Props {
  presetVersionId: string | null;
  onDone: (runId: string) => void;
}

const STATES: Record<string, "ok" | "bad" | "accent" | "neutral"> = {
  completed: "ok",
  failed: "bad",
  cancelled: "neutral",
  running: "accent",
  queued: "accent",
};

export function Launcher({ presetVersionId, onDone }: Props) {
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const [datasetId, setDatasetId] = useState("");
  const [versionId, setVersionId] = useState(presetVersionId ?? "");
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState("2024-06-01");
  const [capital, setCapital] = useState("10000");
  const [spread, setSpread] = useState("");
  const [slippage, setSlippage] = useState("5");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [csvName, setCsvName] = useState("");
  const [csvText, setCsvText] = useState("");
  const [csvSymbol, setCsvSymbol] = useState("EURUSD");
  const [csvTf, setCsvTf] = useState("M15");
  const client = useQueryClient();

  useEffect(() => {
    if (presetVersionId) setVersionId(presetVersionId);
  }, [presetVersionId]);

  const preview = useQuery({
    queryKey: ["preview-bars", datasetId],
    queryFn: () => api.datasetBars(datasetId, 0, 2 ** 62, 300),
    enabled: datasetId !== "",
  });

  const doImport = useMutation({
    mutationFn: () => api.importDataset({ filename: csvName || "upload.csv", csvText, symbol: csvSymbol, timeframe: csvTf }),
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ["datasets"] });
      setDatasetId(data.dataset.id);
      setError("");
      setCsvText("");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  const run = useMutation({
    mutationFn: () =>
      api.backtest({
        strategyVersionId: versionId,
        datasetId,
        config: {
          startTime: Date.parse(`${start}T00:00:00Z`),
          endTime: Date.parse(`${end}T00:00:00Z`),
          initialCapital: capital,
          costs: {
            ...(spread === "" ? {} : { spreadBps: Number(spread) }),
            slippageBps: Number(slippage),
            commissionPerUnit: 0,
          },
        },
      }),
    onSuccess: (data) => {
      setError("");
      if ("run" in data) onDone(data.run.id);
      else setJob(data.job);
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled"].includes(job.state)) return;
    let stop = false;
    let source: EventSource | null = null;
    try {
      source = new EventSource(`/api/jobs/${job.id}/events`);
      source.onmessage = (ev) => {
        const snap = JSON.parse(ev.data);
        setJob((j) => (j ? { ...j, state: snap.state, progress: snap.progress } : j));
        if (snap.state === "completed" && snap.progress?.runId) {
          source?.close();
          if (!stop) onDone(snap.progress.runId);
        }
      };
      source.onerror = () => {
        source?.close();
        source = null;
      };
    } catch {
      source = null;
    }
    const poll = setInterval(async () => {
      if (source) return;
      try {
        const current = await api.job(job.id);
        setJob(current.job);
        if (current.job.state === "completed" && current.job.progress?.runId && !stop) onDone(current.job.progress.runId);
      } catch {
        /* keep polling */
      }
    }, 1000);
    return () => {
      stop = true;
      source?.close();
      clearInterval(poll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.id]);

  const barsDone = job?.progress ? `${job.progress.barsProcessed}/${job.progress.barTotal}` : "";
  const pct = job?.progress && job.progress.barTotal > 0 ? (job.progress.barsProcessed / job.progress.barTotal) * 100 : 0;

  return (
    <div>
      <PageHead title="Backtest launcher" sub="Historical simulation with pessimistic fills. Assumptions are stored with the run — history never rewrites them." />

      <div className="card step-card">
        <div className="step-head">
          <span className="step-num">1</span>
          <h4 className="step-title">Strategy version <span className="step-hint">— paste the id from the strategy page</span></h4>
        </div>
        <label className="field">
          Version id
          <input value={versionId} onChange={(e) => setVersionId(e.target.value)} size={40} placeholder="e.g. 3f9a… (from strategy detail)" />
        </label>
      </div>

      <div className="card step-card">
        <div className="step-head">
          <span className="step-num">2</span>
          <h4 className="step-title">Dataset</h4>
        </div>
        <label className="field">
          Choose
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            <option value="">— pick a dataset —</option>
            {(datasets.data?.datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.symbol} {d.timeframe} · {d.barCount} bars
              </option>
            ))}
          </select>
        </label>
        {preview.isLoading && <p className="muted">Loading preview…</p>}
        {preview.data && (
          <div className="chart-card card" style={{ margin: "0.8rem 0 0" }}>
            <div className="chart-title">
              Preview (downsampled candles)
            </div>
            <PriceChart bars={preview.data.bars} trades={[]} height={200} />
          </div>
        )}
        <details style={{ marginTop: "0.8rem" }}>
          <summary>…or import CSV (open_time,open,high,low,close,volume)</summary>
          <div className="field-row">
            <label className="field">
              Symbol
              <input value={csvSymbol} onChange={(e) => setCsvSymbol(e.target.value)} />
            </label>
            <label className="field">
              Timeframe
              <select value={csvTf} onChange={(e) => setCsvTf(e.target.value)}>
                {["M5", "M15", "H1", "H4", "D1"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              File
              <input
                type="file"
                accept=".csv"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  setCsvName(f.name);
                  f.text().then(setCsvText);
                }}
              />
            </label>
            <button className="btn ghost" disabled={!csvText || doImport.isPending} onClick={() => doImport.mutate()}>
              Import
            </button>
          </div>
        </details>
      </div>

      <div className="card step-card">
        <div className="step-head">
          <span className="step-num">3</span>
          <h4 className="step-title">Assumptions <span className="step-hint">— stored with the run</span></h4>
        </div>
        <div className="field-row">
          <label className="field">
            Start date
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="field">
            End date
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <label className="field">
            Initial capital
            <input value={capital} onChange={(e) => setCapital(e.target.value)} />
          </label>
          <label className="field">
            Spread bps <span className="faint">(blank = preset)</span>
            <input value={spread} onChange={(e) => setSpread(e.target.value)} />
          </label>
          <label className="field">
            Slippage bps
            <input value={slippage} onChange={(e) => setSlippage(e.target.value)} />
          </label>
        </div>
      </div>

      {error && <ErrorNotice message={error} />}
      <button className="btn primary" onClick={() => run.mutate()} disabled={run.isPending || !versionId || !datasetId}>
        {run.isPending ? "Starting…" : "Run backtest"}
      </button>

      {job && (
        <div className="card" style={{ marginTop: "1.2rem", maxWidth: 560 }}>
          <div className="job-line">
            <Badge kind={STATES[job.state] ?? "neutral"}>{job.state}</Badge>
            <code>{job.id.slice(0, 8)}</code>
            <span>
              {barsDone} bars{job.progress?.barsProcessed != null && job.progress?.barTotal > 0 ? ` (${pct.toFixed(0)}%)` : ""}
            </span>
          </div>
          <div className="progress">
            <i style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
          {job.error && (
            <p className="error-text" style={{ marginBottom: 0, display: "flex", gap: "0.4rem", alignItems: "center" }}>
              <IconAlert size={14} />
              {job.error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
