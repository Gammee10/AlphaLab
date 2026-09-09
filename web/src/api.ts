// Typed API client. All numbers are server-authoritative; this module only
// transports and displays them (docs/frontend.md).

export interface Template {
  templateId: string;
  templateVersion: string;
  displayName: string;
  description: string;
  paramSchema: { properties?: Record<string, ParamField> };
}

export interface ParamField {
  type: string;
  minimum?: number;
  maximum?: number;
  default?: number | string;
  enum?: (string | number)[];
  title?: string;
}

export interface RunMetrics {
  tradeCount: number;
  netProfit: string;
  totalReturnPct: number | null;
  winRate: number | null;
  avgWin: string | null;
  avgLoss: string | null;
  profitFactor: number | null;
  noLosses: boolean;
  expectancy: string | null;
  maxDrawdown: string;
  maxDrawdownPct: number;
  sharpe: number | null;
  sharpeInsufficientData: boolean;
}

export interface Run {
  id: string;
  jobId: string;
  strategyVersionId: string;
  datasetId: string;
  specHash: string;
  resultHash: string;
  engineVersion: string;
  config: Record<string, unknown>;
  metrics: RunMetrics;
  equityCurve: [number, string][];
  assumptions: string[];
  warnings: Record<string, number | boolean>;
  createdAt: number;
  trades?: Trade[] | { total: number; url: string };
}

export interface Trade {
  id: string;
  direction: string;
  qty: string;
  entryPrice: string;
  exitPrice: string;
  netPnl: string;
  exitReason: string;
  ambiguous: boolean;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error((body as { message?: string }).message ?? `HTTP ${res.status}`) as Error & {
      code?: string;
      status?: number;
    };
    err.code = (body as { code?: string }).code;
    err.status = res.status;
    throw err;
  }
  return body as T;
}

export const api = {
  templates: () => req<{ templates: Template[] }>("/api/templates"),
  templatePreview: (id: string) => req<{ describe: string; spec: unknown }>(`/api/templates/${id}/preview`),
  createStrategy: (body: unknown) =>
    req<{ strategy: { id: string } }>("/api/strategies", { method: "POST", body: JSON.stringify(body) }),
  strategies: () => req<{ strategies: { id: string; name: string; currentVersionId: string }[] }>("/api/strategies"),
  strategy: (id: string) => req<{ strategy: { id: string; name: string }; versions: Version[] }>(`/api/strategies/${id}`),
  createVersion: (id: string, spec: unknown) =>
    req<{ version: { id: string } }>(`/api/strategies/${id}/versions`, {
      method: "POST",
      body: JSON.stringify({ spec }),
    }),
  datasets: () => req<{ datasets: Dataset[] }>("/api/datasets"),
  dataset: (id: string) => req<{ dataset: Dataset; manifest: Record<string, unknown>; sample: Bar[] }>(`/api/datasets/${id}`),
  importDataset: (body: unknown) =>
    req<{ dataset: { id: string; deduped?: boolean }; manifest: Record<string, unknown> }>("/api/datasets/import", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  backtest: (body: unknown) => req<{ run: Run } | { job: Job }>("/api/backtests", { method: "POST", body: JSON.stringify(body) }),
  run: (id: string) => req<{ run: Run }>(`/api/backtests/${id}`),
  runTrades: (id: string, page: number) => req<{ trades: Trade[]; total: number }>(`/api/backtests/${id}/trades?page=${page}&pageSize=50`),
  job: (id: string) => req<{ job: Job }>(`/api/jobs/${id}`),
  cancelJob: (id: string) => req<unknown>(`/api/jobs/${id}`, { method: "DELETE" }),
  createExperiment: (body: unknown) => req<{ experiment: { id: string } }>("/api/experiments", { method: "POST", body: JSON.stringify(body) }),
  experiment: (id: string) =>
    req<{ experiment: { id: string; name: string }; runs: { id: string; resultHash: string; metrics: RunMetrics }[]; diff: string[]; deltas: Record<string, Record<string, number | null>> }>(
      `/api/experiments/${id}`,
    ),
  sweep: (body: unknown) => req<{ experiment: { id: string }; runIds: string[] }>("/api/experiments/sweep", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  aiPropose: (body: unknown) => req<{ proposal: Proposal }>("/api/ai/propose", { method: "POST", body: JSON.stringify(body) }),
  aiConfirm: (proposalId: string) => req<{ version: { id: string } }>("/api/ai/confirm", {
    method: "POST",
    body: JSON.stringify({ proposalId }),
  }),
  aiExplain: (strategyVersionId: string) =>
    req<AiText>("/api/ai/explain", { method: "POST", body: JSON.stringify({ strategyVersionId }) }),
  aiSummarize: (runIds: string[]) => req<AiText>("/api/ai/summarize", { method: "POST", body: JSON.stringify({ runIds }) }),
  aiStatus: () => req<{ provider: string; keyConfigured: boolean }>("/api/ai/status"),
};

export interface Version {
  id: string;
  versionNumber: number;
  specHash: string;
  spec: Record<string, unknown>;
}

export interface Dataset {
  id: string;
  symbol: string;
  timeframe: string;
  barCount: number;
  barsHash: string;
}

export interface Bar {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Job {
  id: string;
  state: string;
  progress: { barsProcessed: number; barTotal: number; runId?: string; deduped?: boolean };
  error?: string | null;
}

export interface Proposal {
  id: string;
  status: string;
  patch: { ops: { op: string; target?: string; field?: string; filter?: string; value?: unknown }[]; rationale: string };
  validation: { ok: boolean; errors: { code: string; message: string }[] };
  provider: string;
  model?: string | null;
  tokens?: number | null;
  message?: string;
  fallbackReason?: string;
}

export interface AiText {
  text: string;
  citations: string[];
  provider: string;
  model: string;
  tokens: number;
  cached?: boolean;
  fallbackReason?: string;
}
