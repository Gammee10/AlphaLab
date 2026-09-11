import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "../api";
import { navigate } from "../router";
import { errText, useUi } from "../store";
import { PriceChart } from "../charts";
import {
  Badge,
  Banner,
  ErrorInline,
  Loading,
  PageHead,
} from "../components/ui";
import { IcPlay, IcWarn } from "../components/icons";

const JOB_BADGE: Record<string, "ok" | "bad" | "acc" | "warn" | "neutral"> = {
  completed: "ok",
  failed: "bad",
  cancelled: "neutral",
  running: "acc",
  queued: "acc",
};

export function Launcher({ presetVersionId }: { presetVersionId: string | null }) {
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const client = useQueryClient();
  const { toast } = useUi();

  const [versionId, setVersionId] = useState(presetVersionId ?? "");
  const [datasetId, setDatasetId] = useState("");
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
      toast(`Dataset imported${data.dataset.deduped ? " (deduplicated)" : ""}`, "ok");
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
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
      if ("run" in data) {
        toast("Backtest complete", "ok");
        navigate(`/run/${data.run.id}`);
      } else {
        setJob(data.job);
        toast("Job queued — streaming progress", "info");
      }
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
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
          if (!stop) {
            toast("Backtest complete", "ok");
            navigate(`/run/${snap.progress.runId}`);
          }
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
        if (current.job.state === "completed" && current.job.progress?.runId && !stop) {
          toast("Backtest complete", "ok");
          navigate(`/run/${current.job.progress.runId}`);
        }
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

  const pct = job?.progress && job.progress.barTotal > 0 ? (job.progress.barsProcessed / job.progress.barTotal) * 100 : 0;

  return (
    <div>
      <PageHead
        eyebrow="New simulation"
        title="Backtest launcher"
        sub="Historical simulation with pessimistic fills. Assumptions are stored with the run — history never rewrites them."
      />

      <div className="glass step-card">
        <div className="step-head">
          <span className="step-badge">1</span>
          <div className="step-title">
            Strategy version <span className="step-hint">— id from the strategy page</span>
          </div>
        </div>
        <label className="field">
          <span className="field-label">Version id</span>
          <input
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
            placeholder="e.g. 3f9a… (from strategy detail page)"
            style={{ maxWidth: 420, fontFamily: "var(--font-mono)" }}
          />
        </label>
      </div>

      <div className="glass step-card">
        <div className="step-head">
          <span className="step-badge">2</span>
          <div className="step-title">
            Dataset <span className="step-hint">— pick existing or import CSV</span>
          </div>
        </div>
        <label className="field">
          <span className="field-label">Choose dataset</span>
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} style={{ maxWidth: 420 }}>
            <option value="">— pick a dataset —</option>
            {(datasets.data?.datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.symbol} {d.timeframe} · {d.barCount} bars
              </option>
            ))}
          </select>
        </label>

        {preview.isLoading && <Loading text="Loading preview…" />}
        {preview.data && (
          <div className="chart-panel glass" style={{ margin: "0.8rem 0 0" }}>
            <div className="chart-head">
              <div className="chart-name">Preview · downsampled candles</div>
            </div>
            <PriceChart bars={preview.data.bars} trades={[]} height={200} />
          </div>
        )}

        <details style={{ marginTop: "0.9rem" }}>
          <summary>…or import CSV (open_time,open,high,low,close,volume)</summary>
          <div className="field-row">
            <label className="field">
              <span className="field-label">Symbol</span>
              <input value={csvSymbol} onChange={(e) => setCsvSymbol(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Timeframe</span>
              <select value={csvTf} onChange={(e) => setCsvTf(e.target.value)}>
                {["M5", "M15", "H1", "H4", "D1"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">CSV file</span>
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
            <button className="btn glass" disabled={!csvText || doImport.isPending} onClick={() => doImport.mutate()}>
              {doImport.isPending ? "Importing…" : "Import"}
            </button>
          </div>
        </details>
      </div>

      <div className="glass step-card">
        <div className="step-head">
          <span className="step-badge">3</span>
          <div className="step-title">
            Assumptions <span className="step-hint">— stored with the run, never rewritten</span>
          </div>
        </div>
        <div className="field-row">
          <label className="field">
            <span className="field-label">Start date</span>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">End date</span>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Initial capital</span>
            <input value={capital} onChange={(e) => setCapital(e.target.value)} style={{ maxWidth: 140 }} />
          </label>
          <label className="field">
            <span className="field-label">Spread bps (blank = preset)</span>
            <input value={spread} onChange={(e) => setSpread(e.target.value)} style={{ maxWidth: 140 }} />
          </label>
          <label className="field">
            <span className="field-label">Slippage bps</span>
            <input value={slippage} onChange={(e) => setSlippage(e.target.value)} style={{ maxWidth: 140 }} />
          </label>
        </div>
      </div>

      {error && <ErrorInline text={error} />}

      <button className="btn primary lg" onClick={() => run.mutate()} disabled={run.isPending || !versionId || !datasetId}>
        <IcPlay size={15} />
        {run.isPending ? "Starting…" : "Run backtest"}
      </button>

      {job && (
        <div className="glass" style={{ marginTop: "1.2rem", maxWidth: 560 }}>
          <div className="row-wrap" style={{ marginBottom: "0.5rem" }}>
            <Badge kind={JOB_BADGE[job.state] ?? "neutral"}>{job.state}</Badge>
            <code>{job.id.slice(0, 8)}</code>
            {job.progress && job.progress.barTotal > 0 && (
              <span className="muted" style={{ fontSize: "0.83rem" }}>
                {job.progress.barsProcessed}/{job.progress.barTotal} bars · {pct.toFixed(0)}%
              </span>
            )}
          </div>
          <div className="progress-track">
            <div className={`progress-fill${job.progress && job.progress.barTotal > 0 ? "" : " indeterminate"}`} style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
          {job.error && (
            <p className="error-inline" style={{ marginTop: "0.5rem" }}>
              <IcWarn size={14} />
              {job.error}
            </p>
          )}
        </div>
      )}

      {!versionId && (
        <Banner kind="info">
          Tip: open a strategy and hit “Backtest” to prefill the version id automatically.
        </Banner>
      )}
    </div>
  );
}
