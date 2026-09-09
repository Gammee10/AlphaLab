import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "../api";
import { PriceChart } from "../charts";

interface Props {
  presetVersionId: string | null;
  onDone: (runId: string) => void;
}

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

  return (
    <div>
      <h2>Backtest</h2>
      <div className="card">
        <h4>1 · Strategy version</h4>
        <label>
          Version id
          <input value={versionId} onChange={(e) => setVersionId(e.target.value)} size={40} placeholder="paste from strategy page" />
        </label>
      </div>
      <div className="card">
        <h4>2 · Dataset</h4>
        <label>
          Choose
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            <option value="">— pick —</option>
            {(datasets.data?.datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.symbol} {d.timeframe} · {d.barCount} bars
              </option>
            ))}
          </select>
        </label>
        {preview.data && (
          <div className="chart-wrap">
            <h4>Preview (downsampled candles)</h4>
            <PriceChart bars={preview.data.bars} trades={[]} height={220} />
          </div>
        )}
        <details>
          <summary>…or import CSV (open_time,open,high,low,close,volume)</summary>
          <div className="row">
            <label>
              Symbol
              <input value={csvSymbol} onChange={(e) => setCsvSymbol(e.target.value)} />
            </label>
            <label>
              Timeframe
              <select value={csvTf} onChange={(e) => setCsvTf(e.target.value)}>
                {["M5", "M15", "H1", "H4", "D1"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label>
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
            <button className="ghost" disabled={!csvText || doImport.isPending} onClick={() => doImport.mutate()}>
              Import
            </button>
          </div>
        </details>
      </div>
      <div className="card">
        <h4>3 · Assumptions (stored with the run — history never rewrites them)</h4>
        <div className="row">
          <label>
            Period
            <span>
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)} /> →{" "}
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </span>
          </label>
          <label>
            Initial capital
            <input value={capital} onChange={(e) => setCapital(e.target.value)} />
          </label>
          <label>
            Spread bps (blank = preset)
            <input value={spread} onChange={(e) => setSpread(e.target.value)} />
          </label>
          <label>
            Slippage bps
            <input value={slippage} onChange={(e) => setSlippage(e.target.value)} />
          </label>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={() => run.mutate()} disabled={run.isPending || !versionId || !datasetId}>
        Run backtest
      </button>
      {job && (
        <p>
          Job <code>{job.id.slice(0, 8)}</code>: <strong>{job.state}</strong> ({job.progress?.barsProcessed ?? 0}/
          {job.progress?.barTotal ?? 0})
        </p>
      )}
    </div>
  );
}
