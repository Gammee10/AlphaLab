import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Job } from "../api";

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

  useEffect(() => {
    if (presetVersionId) setVersionId(presetVersionId);
  }, [presetVersionId]);

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
    if (!job || job.state === "completed" || job.state === "failed" || job.state === "cancelled") return;
    // SSE primary, polling fallback.
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
  }, [job?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const chosen = datasets.data?.datasets.find((d) => d.id === datasetId);

  return (
    <div>
      <h2>Backtest</h2>
      <label>
        Strategy version id
        <input value={versionId} onChange={(e) => setVersionId(e.target.value)} size={40} />
      </label>
      <label>
        Dataset
        <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
          <option value="">— pick —</option>
          {(datasets.data?.datasets ?? []).map((d) => (
            <option key={d.id} value={d.id}>
              {d.symbol} {d.timeframe} · {d.barCount} bars
            </option>
          ))}
        </select>
      </label>
      {chosen && <DatasetManifest id={chosen.id} />}
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
        Spread bps (blank = symbol preset)
        <input value={spread} onChange={(e) => setSpread(e.target.value)} />
      </label>
      <label>
        Slippage bps
        <input value={slippage} onChange={(e) => setSlippage(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <button onClick={() => run.mutate()} disabled={run.isPending || !versionId || !datasetId}>
        Run backtest
      </button>
      {job && (
        <p>
          Job {job.id}: <strong>{job.state}</strong> ({job.progress?.barsProcessed ?? 0}/{job.progress?.barTotal ?? 0})
        </p>
      )}
    </div>
  );
}

function DatasetManifest({ id }: { id: string }) {
  const detail = useQuery({ queryKey: ["dataset", id], queryFn: () => api.dataset(id) });
  if (!detail.data) return null;
  const manifest = detail.data.manifest as { gaps?: { missing_bars?: number }[]; rowsRejected?: unknown[]; duplicatesDropped?: number };
  return (
    <p className="muted">
      {(manifest.gaps as { missing_bars?: number }[] | undefined)?.length ?? 0} gaps ·{" "}
      {manifest.duplicatesDropped ?? 0} duplicates dropped · {(manifest.rowsRejected as unknown[] | undefined)?.length ?? 0} rows
      rejected · hash <code>{detail.data.dataset.barsHash.slice(0, 8)}</code>
    </p>
  );
}
