import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Proposal } from "../api";

export function AiPanel({ versionId, runIds }: { versionId: string | null; runIds: string[] }) {
  const status = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus });
  const [intent, setIntent] = useState("change stop to 1.5 ATR");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [error, setError] = useState("");
  const [explanation, setExplanation] = useState("");
  const [summary, setSummary] = useState("");

  const propose = useMutation({
    mutationFn: () => api.aiPropose({ strategyVersionId: versionId, runIds, intent }),
    onSuccess: (data) => {
      setProposal(data.proposal);
      setError("");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });
  const confirm = useMutation({
    mutationFn: () => api.aiConfirm(proposal!.id),
    onSuccess: () => {
      setProposal(null);
      setError("");
      alert("New strategy version created.");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  return (
    <div>
      <h2>AI assistant</h2>
      {status.data && !status.data.keyConfigured && (
        <p className="banner">AI offline — deterministic assistant active. Add a Gemini key server-side for NL.</p>
      )}
      <label>
        Intent
        <input value={intent} onChange={(e) => setIntent(e.target.value)} size={60} />
      </label>
      <button onClick={() => propose.mutate()} disabled={!versionId || propose.isPending}>
        Propose change
      </button>
      {error && <p className="error">{error}</p>}
      {proposal && (
        <div className="card">
          <p>
            <strong>{proposal.provider}</strong> {proposal.model ?? ""} ·{" "}
            {proposal.validation.ok ? "valid" : "INVALID"}
            {proposal.fallbackReason ? ` · fallback: ${proposal.fallbackReason}` : ""}
          </p>
          <ul>
            {proposal.patch.ops.map((op, i) => (
              <li key={i}>
                <code>
                  {op.op} {op.target ?? op.field ?? op.filter ?? ""} {JSON.stringify(op.value ?? "")}
                </code>
              </li>
            ))}
          </ul>
          {!proposal.validation.ok && (
            <ul>
              {proposal.validation.errors.map((e, i) => (
                <li key={i} className="error">
                  {e.code}: {e.message}
                </li>
              ))}
            </ul>
          )}
          {proposal.message && <p className="muted">{proposal.message}</p>}
          <button onClick={() => confirm.mutate()} disabled={!proposal.validation.ok}>
            Confirm → new version
          </button>
        </div>
      )}
      <div>
        <button
          onClick={async () => {
            if (!versionId) return;
            const out = await api.aiExplain(versionId);
            setExplanation(`${out.text}\n\n— ${out.provider} ${out.model}, ${out.tokens} tokens`);
          }}
          disabled={!versionId}
        >
          Explain strategy
        </button>
        <button
          onClick={async () => {
            if (runIds.length === 0) return;
            const out = await api.aiSummarize(runIds);
            setSummary(`${out.text}\n\n— ${out.provider} ${out.model}, ${out.tokens} tokens`);
          }}
          disabled={runIds.length === 0}
        >
          Summarize runs
        </button>
      </div>
      {explanation && <pre>{explanation}</pre>}
      {summary && <pre>{summary}</pre>}
    </div>
  );
}
