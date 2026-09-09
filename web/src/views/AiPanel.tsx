import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, type Proposal } from "../api";
import { Badge, ErrorNotice, IconAlert, IconSpark, Loading } from "../components/ui";

interface Msg {
  role: "user" | "ai";
  text: string;
  meta?: string;
  proposal?: Proposal;
}

export function AiPanel({ versionId, runIds }: { versionId: string | null; runIds: string[] }) {
  const [intent, setIntent] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [error, setError] = useState("");

  const push = (m: Msg) => setMessages((prev) => [...prev, m]);

  const propose = useMutation({
    mutationFn: (text: string) => api.aiPropose({ strategyVersionId: versionId, runIds, intent: text }),
    onSuccess: (data) => {
      const p = data.proposal;
      push({
        role: "ai",
        text: p.message ?? p.patch.rationale ?? (p.validation.ok ? "Proposed changes (review below)." : "That proposal is invalid."),
        meta: `${p.provider}${p.model ? ` · ${p.model}` : ""}${p.tokens ? ` · ${p.tokens} tokens` : ""}${p.fallbackReason ? ` · fallback: ${p.fallbackReason}` : ""}`,
        proposal: p,
      });
      setError("");
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  const confirm = useMutation({
    mutationFn: (id: string) => api.aiConfirm(id),
    onSuccess: (data) => {
      push({ role: "ai", text: `Confirmed — new strategy version ${data.version.id.slice(0, 8)} created. History preserved.` });
      setMessages((prev) => prev.map((m) => (m.proposal ? { ...m, proposal: { ...m.proposal!, status: "confirmed" } } : m)));
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  const ask = async (kind: "explain" | "summarize") => {
    try {
      const out = kind === "explain" && versionId ? await api.aiExplain(versionId) : await api.aiSummarize(runIds);
      push({
        role: "ai",
        text: out.text,
        meta: `${out.provider} · ${out.model} · ${out.tokens} tokens${out.cached ? " · cached" : ""}`,
      });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const send = () => {
    const text = intent.trim();
    if (!text || !versionId || propose.isPending) return;
    push({ role: "user", text });
    setIntent("");
    propose.mutate(text);
  };

  return (
    <div>
      <div className="page">
        <h2 className="page-title">
          <span className="stat-ico" style={{ width: 34, height: 34 }}>
            <IconSpark size={17} />
          </span>
          AI copilot
        </h2>
        <p className="page-sub">
          Describe a change — proposals are validated and need your explicit confirm. Nothing applies itself.
        </p>
      </div>

      {!versionId && (
        <div className="banner info">
          <IconAlert size={16} />
          <span>Open a strategy first — proposals need a base version.</span>
        </div>
      )}

      <div className="card" style={{ maxWidth: 820, paddingBottom: "0.6rem" }}>
        <div className="chat" style={{ minHeight: 240 }}>
          {messages.length === 0 && !propose.isPending && (
            <div className="msg ai">
              Try: “widen the stop to 2 ATR” or “only trade London/New York”. I'll draft a validated proposal — you review and confirm.
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.text}
              {m.proposal && (
                <>
                  <ul className="ops">
                    {m.proposal.patch.ops.map((op, j) => (
                      <li key={j}>
                        <code>
                          {op.op} {op.target ?? op.field ?? op.filter ?? ""} {JSON.stringify(op.value ?? "")}
                        </code>
                      </li>
                    ))}
                  </ul>
                  {!m.proposal.validation.ok && (
                    <ul style={{ margin: "0.4rem 0 0", paddingLeft: "1.1rem" }}>
                      {m.proposal.validation.errors.map((e, j) => (
                        <li key={j} className="error-text" style={{ fontSize: "0.85rem" }}>
                          {e.code}: {e.message}
                        </li>
                      ))}
                    </ul>
                  )}
                  {m.proposal.status === "proposed" && m.proposal.validation.ok && (
                    <div style={{ marginTop: "0.6rem" }}>
                      <button className="btn primary sm" onClick={() => confirm.mutate(m.proposal!.id)}>
                        Confirm → new version
                      </button>
                    </div>
                  )}
                  {m.proposal.status === "confirmed" && (
                    <div style={{ marginTop: "0.6rem" }}>
                      <Badge kind="ok">applied as new version</Badge>
                    </div>
                  )}
                </>
              )}
              {m.meta && <div className="meta">{m.meta}</div>}
            </div>
          ))}
          {propose.isPending && (
            <div className="msg ai">
              <Loading text="Thinking…" />
            </div>
          )}
        </div>

        {error && <ErrorNotice message={error} />}

        <div className="chat-input">
          <input
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Describe a strategy change…"
          />
          <button className="btn primary" onClick={send} disabled={!versionId || propose.isPending}>
            Send
          </button>
        </div>
        <div className="chat-tools">
          <button className="btn ghost sm" onClick={() => ask("explain")} disabled={!versionId}>
            Explain strategy
          </button>
          <button className="btn ghost sm" onClick={() => ask("summarize")} disabled={runIds.length === 0}>
            Summarize runs
          </button>
        </div>
      </div>
    </div>
  );
}
