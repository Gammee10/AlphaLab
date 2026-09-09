import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ParamField, type Template } from "../api";
import { Badge, EmptyState, Loading, PageHead } from "../components/ui";

function ParamInput({ name, field, value, onChange }: { name: string; field: ParamField; value: unknown; onChange: (v: unknown) => void }) {
  if (field.enum) {
    return (
      <label className="field">
        {field.title ?? name}
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
      {field.title ?? name}
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

export function Strategies({ onOpen }: { onOpen: (id: string) => void }) {
  const query = useQuery({ queryKey: ["templates"], queryFn: api.templates });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const [picked, setPicked] = useState<Template | null>(null);
  const [name, setName] = useState("My strategy");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const client = useQueryClient();

  const create = useMutation({
    mutationFn: () => api.createStrategy({ name, templateId: picked!.templateId, params }),
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ["strategies"] });
      onOpen(data.strategy.id);
    },
    onError: (e: Error & { code?: string }) => setError(`${e.code ?? "ERROR"}: ${e.message}`),
  });

  return (
    <div>
      <PageHead title="Strategies" sub="Start from a template, tune the parameters, then iterate on versions." />

      <h3 className="section-title">Templates</h3>
      {query.isLoading && <Loading text="Loading templates…" />}
      {query.data && (
        <div className="gallery">
          {query.data.templates.map((t) => (
            <button
              key={t.templateId}
              className={picked?.templateId === t.templateId ? "card picked" : "card"}
              onClick={() => {
                setPicked(t);
                const defaults: Record<string, unknown> = {};
                for (const [k, f] of Object.entries(t.paramSchema.properties ?? {})) defaults[k] = f.default;
                setParams(defaults);
                setError("");
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "baseline" }}>
                <strong>{t.displayName}</strong>
                <Badge kind="accent">v{t.templateVersion}</Badge>
              </div>
              <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
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
          <h3 className="section-title">New from {picked.displayName}</h3>
          <div className="card" style={{ maxWidth: 520 }}>
            <label className="field">
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            {Object.entries(picked.paramSchema.properties ?? {}).map(([k, f]) => (
              <ParamInput key={k} name={k} field={f} value={params[k] ?? f.default} onChange={(v) => setParams({ ...params, [k]: v })} />
            ))}
            {error && <p className="error-text">{error}</p>}
            <button type="submit" className="btn primary" style={{ marginTop: "0.7rem" }} disabled={create.isPending}>
              Create strategy
            </button>
          </div>
        </form>
      )}

      <h3 className="section-title">All strategies</h3>
      <div className="card table-card">
        {strategies.data && strategies.data.strategies.length === 0 ? (
          <EmptyState title="No strategies yet">Pick a template above to create your first strategy.</EmptyState>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Current version</th>
              </tr>
            </thead>
            <tbody>
              {(strategies.data?.strategies ?? []).map((s) => (
                <tr key={s.id}>
                  <td>
                    <button className="link" onClick={() => onOpen(s.id)}>
                      {s.name}
                    </button>
                  </td>
                  <td>
                    <code>{s.currentVersionId.slice(0, 8)}</code>
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
