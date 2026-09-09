import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { shortHash } from "../format";

export function StrategyDetail({ id, onBacktest }: { id: string; onBacktest: (versionId: string) => void }) {
  const detail = useQuery({ queryKey: ["strategy", id], queryFn: () => api.strategy(id) });
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const client = useQueryClient();

  const save = useMutation({
    mutationFn: () => api.createVersion(id, JSON.parse(draft)),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["strategy", id] });
      setDraft("");
      setError("");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  if (detail.isLoading) return <p>Loading…</p>;
  if (detail.isError) return <p className="error">Failed to load strategy.</p>;
  const { strategy, versions } = detail.data!;
  const current = versions[versions.length - 1];

  return (
    <div>
      <h2>{strategy.name}</h2>
      <ol className="versions">
        {versions.map((v) => (
          <li key={v.id} className={v.id === current.id ? "current" : ""}>
            v{v.versionNumber} · <code>{shortHash(v.specHash)}</code>
            <button className="link" onClick={() => onBacktest(v.id)}>
              backtest this version
            </button>
            <pre>{JSON.stringify(v.spec, null, 1).slice(0, 1200)}</pre>
          </li>
        ))}
      </ol>
      <h3>New version (edit JSON — validated server-side, history immutable)</h3>
      <textarea
        rows={10}
        cols={80}
        placeholder="Paste the full edited spec…"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      {error && <p className="error">{error}</p>}
      <div>
        <button
          onClick={() => {
            setError("");
            save.mutate();
          }}
          disabled={!draft || save.isPending}
        >
          Save as new version
        </button>
      </div>
    </div>
  );
}
