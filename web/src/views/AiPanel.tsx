import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Proposal } from "../api";
import { errText, useUi } from "../store";
import { Badge, ErrorInline, Loading, SectionLabel } from "../components/ui";
import { IcSend, IcSpark } from "../components/icons";

interface Msg {
  role: "user" | "ai";
  text: string;
  meta?: string;
  proposal?: Proposal;
}

export function AiPanel({ presetVersionId }: { presetVersionId: string | null }) {
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const { toast } = useUi();

  const [versionId, setVersionId] = useState(presetVersionId ?? "");
  const [intent, setIntent] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [error, setError] = useState("");

  const push = (m: Msg) => setMessages((prev) => [...prev, m]);

  const propose = useMutation({
    mutationFn: (text: string) => api.aiPropose({ strategyVersionId: versionId, runIds: [], intent: text }),
    onSuccess: (data) => {
      const p = data.proposal;
      push({
        role: "ai",
        text:
          p.message ??
          p.patch.rationale ??
          (p.validation.ok ? "Proposed changes (review below)." : "That proposal is invalid."),
        meta: `${p.provider}${p.model ? ` · ${p.model}` : ""}${p.tokens ? ` · ${p.tokens} tokens` : ""}${
          p.fallbackReason ? ` · fallback: ${p.fallbackReason}` : ""
        }`,
        proposal: p,
      });
      setError("");
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
  });

  const confirm = useMutation({
    mutationFn: (id: string) => api.aiConfirm(id),
    onSuccess: (data) => {
      push({
        role: "ai",
        text: `Confirmed — new strategy version ${data.version.id.slice(0, 8)} created. History preserved.`,
      });
      setMessages((prev) =>
        prev.map((m) => (m.proposal ? { ...m, proposal: { ...m.proposal!, status: "confirmed" } } : m)),
      );
      toast("Proposal applied as new version", "ok");
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
  });

  const ask = async (kind: "explain" | "summarize") => {
    try {
      const out = kind === "explain" && versionId ? await api.aiExplain(versionId) : await api.aiSummarize([]);
      push({
        role: "ai",
        text: out.text,
        meta: `${out.provider} · ${out.model} · ${out.tokens} tokens${out.cached ? " · cached" : ""}`,
      });
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast(msg, "error");
    }
  };

  const send = () => {
    const text = intent.trim();
    if (!text || !versionId || propose.isPending) return;
    push({ role: "user", text });
    setIntent("");
    propose.mutate(text);
  };

  const currentStrategy = strategies.data?.strategies.find((s) => s.currentVersionId === versionId);

  return (
    <div>
      <div className="page-head">
        <div className="grow">
          <h2 className="page-title">
            <span className="stat-icon" style={{ width: 34, height: 34 }}>
              <IcSpark size={16} />
            </span>
            AI copilot
          </h2>
          <p className="page-sub">Describe a change — proposals are validated and need your explicit confirm. Nothing applies itself.</p>
        </div>
      </div>

      {!versionId && (
        <ErrorInline text="Pick a strategy below — proposals need a base version to edit." />
      )}

      <div className="glass" style={{ maxWidth: 840 }}>
        <SectionLabel>Base strategy version</SectionLabel>
        <div className="row-wrap" style={{ marginBottom: "0.4rem" }}>
          <select value={versionId} onChange={(e) => setVersionId(e.target.value)} style={{ maxWidth: 380 }}>
            <option value="">— select strategy version —</option>
            {(strategies.data?.strategies ?? []).map((s) => (
              <option key={s.id} value={s.currentVersionId}>
                {s.name} · {s.currentVersionId.slice(0, 8)}
              </option>
            ))}
          </select>
          {currentStrategy && <Badge kind="neutral">{currentStrategy.name}</Badge>}
        </div>

        <hr />

        <div className="chat-bar">
          <input
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Describe a strategy change… e.g. “widen the stop to 2 ATR”"
            disabled={!versionId}
          />
          <button className="btn primary" onClick={send} disabled={!versionId || propose.isPending}>
            <IcSend size={14} />
            Send
          </button>
        </div>
        <div className="row-wrap" style={{ marginTop: "0.55rem" }}>
          <button className="btn glass sm" onClick={() => ask("explain")} disabled={!versionId}>
            Explain strategy
          </button>
          <button className="btn glass sm" onClick={() => ask("summarize")}>
            Summarize context
          </button>
          {propose.isPending && (
            <span className="row-wrap muted" style={{ fontSize: "0.83rem" }}>
              <SpinnerInline />
              thinking…
            </span>
          )}
        </div>

        {error && <ErrorInline text={error} />}

        <hr />
        <div className="chat">
          {messages.length === 0 && !propose.isPending && (
            <div className="bubble ai">
              Try: “widen the stop to 2 ATR” or “only trade London/New York”. I'll draft a validated proposal — you review
              the ops and confirm.
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.text}
              {m.proposal && (
                <>
                  <ul style={{ margin: "0.5rem 0 0.2rem", paddingLeft: "1.1rem" }}>
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
                        <li key={j} className="error-inline" style={{ fontSize: "0.84rem" }}>
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
              {m.meta && <div className="bubble-meta">{m.meta}</div>}
            </div>
          ))}
          {propose.isPending && (
            <div className="bubble ai">
              <Loading text="Drafting proposal…" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SpinnerInline() {
  return <span style={{ width: 12, height: 12, border: "2px solid var(--border-strong)", borderTopColor: "var(--accent)", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} />;
}
