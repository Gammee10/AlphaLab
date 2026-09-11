import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ParamField, type Template } from "../api";
import { navigate } from "../router";
import { errText, useUi } from "../store";
import {
  Badge,
  EmptyState,
  ErrorInline,
  Loading,
  PageHead,
  SectionLabel,
} from "../components/ui";
import { IcPlay, IcPlus, IcSearch } from "../components/icons";

function ParamInput({ field, value, onChange }: { field: ParamField; value: unknown; onChange: (v: unknown) => void }) {
  if (field.enum) {
    return (
      <label className="field">
        <span className="field-label">{field.title ?? "value"}</span>
        <select value={String(value ?? field.default ?? "")} onChange={(e) => onChange(e.target.value)}>
          {field.enum.map((o) => (
            <option key={String(o)} value={String(o)}>
              {String(o)}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className="field">
      <span className="field-label">{field.title ?? "value"}</span>
      <input
        type="number"
        step="any"
        min={field.minimum}
        max={field.maximum}
        value={Number(value ?? field.default ?? 0)}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

export function Strategies() {
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.templates });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const client = useQueryClient();
  const { toast } = useUi();

  const [picked, setPicked] = useState<Template | null>(null);
  const [name, setName] = useState("My strategy");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const list = useMemo(() => {
    const all = strategies.data?.strategies ?? [];
    const needle = search.trim().toLowerCase();
    return needle ? all.filter((s) => s.name.toLowerCase().includes(needle)) : all;
  }, [strategies.data, search]);

  const pick = (t: Template) => {
    setPicked(t);
    const defaults: Record<string, unknown> = {};
    for (const [k, f] of Object.entries(t.paramSchema.properties ?? {})) defaults[k] = f.default;
    setParams(defaults);
    setName(`${t.displayName} · my variant`);
    setError("");
  };

  const create = useMutation({
    mutationFn: () => api.createStrategy({ name, templateId: picked!.templateId, params }),
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ["strategies"] });
      toast("Strategy created", "ok");
      navigate(`/strategy/${data.strategy.id}`);
    },
    onError: (e: Error & { code?: string }) => {
      setError(errText(e));
      toast(errText(e), "error");
    },
  });

  return (
    <div>
      <PageHead
        eyebrow="Strategy library"
        title="Strategies"
        sub="Start from a validated template, tune parameters, and iterate as immutable versions."
      />

      <SectionLabel right={templates.data ? `${templates.data.templates.length} available` : undefined}>
        Templates
      </SectionLabel>
      {templates.isLoading ? (
        <Loading text="Loading templates…" />
      ) : templates.isError ? (
        <ErrorInline text="Failed to load templates." />
      ) : (
        <div className="gallery">
          {(templates.data?.templates ?? []).map((t) => (
            <button
              key={t.templateId}
              className={`glass pickable${picked?.templateId === t.templateId ? " picked" : ""}`}
              onClick={() => pick(t)}
            >
              <div className="row-wrap" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
                <div className="glass-title">{t.displayName}</div>
                <Badge kind="acc">v{t.templateVersion}</Badge>
              </div>
              <p className="muted" style={{ fontSize: "0.85rem", margin: "0.5rem 0 0" }}>
                {t.description}
              </p>
            </button>
          ))}
        </div>
      )}

      {picked && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError("");
            create.mutate();
          }}
        >
          <SectionLabel>New from {picked.displayName}</SectionLabel>
          <div className="glass" style={{ maxWidth: 540 }}>
            <label className="field">
              <span className="field-label">Strategy name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <div className="field-row">
              {Object.entries(picked.paramSchema.properties ?? {}).map(([k, f]) => (
                <ParamInput key={k} field={f} value={params[k] ?? f.default} onChange={(v) => setParams({ ...params, [k]: v })} />
              ))}
            </div>
            {error && <ErrorInline text={error} />}
            <div style={{ marginTop: "0.9rem" }}>
              <button type="submit" className="btn primary" disabled={create.isPending}>
                <IcPlus size={14} />
                {create.isPending ? "Creating…" : "Create strategy"}
              </button>
            </div>
          </div>
        </form>
      )}

      <SectionLabel right={strategies.data ? `${list.length}/${strategies.data.strategies.length}` : undefined}>
        All strategies
      </SectionLabel>
      <div className="glass" style={{ padding: 0, overflow: "hidden" }}>
        <div className="filter-bar">
          <IcSearch size={14} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search strategies…" style={{ maxWidth: 280 }} />
        </div>
        {strategies.isLoading ? (
          <div style={{ padding: "1rem" }}>
            <Loading text="Loading strategies…" />
          </div>
        ) : strategies.data && strategies.data.strategies.length === 0 ? (
          <EmptyState title="No strategies yet">Pick a template above to create your first strategy.</EmptyState>
        ) : list.length === 0 ? (
          <EmptyState title="No matches">No strategy name matches that search.</EmptyState>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Current version</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id}>
                  <td>
                    <button
                      className="link"
                      onClick={() => navigate(`/strategy/${s.id}`)}
                      style={{ background: "none", border: "none", cursor: "pointer", font: "inherit", fontWeight: 600 }}
                    >
                      {s.name}
                    </button>
                  </td>
                  <td>
                    <code>{s.currentVersionId.slice(0, 8)}</code>
                  </td>
                  <td>
                    <div className="row-wrap" style={{ justifyContent: "flex-end" }}>
                      <button className="btn glass sm" onClick={() => navigate(`/strategy/${s.id}`)}>
                        Open
                      </button>
                      <button className="btn glass sm" onClick={() => navigate(`/launcher/${s.currentVersionId}`)}>
                        <IcPlay size={12} />
                        Backtest
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
