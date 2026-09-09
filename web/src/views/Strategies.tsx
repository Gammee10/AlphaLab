import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ParamField, type Template } from "../api";

function ParamInput({ name, field, value, onChange }: { name: string; field: ParamField; value: unknown; onChange: (v: unknown) => void }) {
  if (field.enum) {
    return (
      <label>
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
    <label>
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
      <h2>Strategies</h2>
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
              <strong>{t.displayName}</strong>
              <small className="muted">
                {t.templateId} v{t.templateVersion}
              </small>
              <p>{t.description}</p>
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
          <h3>
            New from {picked.displayName} <span className="muted">v{picked.templateVersion}</span>
          </h3>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          {Object.entries(picked.paramSchema.properties ?? {}).map(([k, f]) => (
            <ParamInput key={k} name={k} field={f} value={params[k] ?? f.default} onChange={(v) => setParams({ ...params, [k]: v })} />
          ))}
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={create.isPending}>
            Create strategy
          </button>
        </form>
      )}
      <h3>All strategies</h3>
      <ul>
        {(strategies.data?.strategies ?? []).map((s) => (
          <li key={s.id}>
            <button className="link" onClick={() => onOpen(s.id)}>
              {s.name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
