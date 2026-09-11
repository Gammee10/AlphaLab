import { useEffect } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { navigate, useRoute } from "./router";
import { UiProvider, useUi } from "./store";
import { IcLayers, IcMoon, IcPlay, IcPulse, IcSearch, IcSpark, IcSun, IcSwap } from "./components/icons";
import { Toaster } from "./components/ui";
import { CommandPalette } from "./shell/CommandPalette";
import { AiPanel } from "./views/AiPanel";
import { Compare } from "./views/Compare";
import { Dashboard } from "./views/Dashboard";
import { Launcher } from "./views/Launcher";
import { RunView } from "./views/RunView";
import { Strategies } from "./views/Strategies";
import { StrategyDetail } from "./views/StrategyDetail";

interface NavEntry {
  path: string;
  label: string;
  icon: (props: { size?: number }) => React.ReactElement;
  match: (segments: string[]) => boolean;
}

const NAV: NavEntry[] = [
  { path: "/", label: "Home", icon: IcPulse, match: (s) => s.length === 0 },
  { path: "/strategies", label: "Strategies", icon: IcLayers, match: (s) => s[0] === "strategies" || s[0] === "strategy" },
  { path: "/launcher", label: "Backtest", icon: IcPlay, match: (s) => s[0] === "launcher" },
  { path: "/compare", label: "Compare", icon: IcSwap, match: (s) => s[0] === "compare" },
  { path: "/ai", label: "AI Copilot", icon: IcSpark, match: (s) => s[0] === "ai" },
];

const client = new QueryClient();

function StatusPills() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/api/health").then((r) => r.json()),
    refetchInterval: 15000,
  });
  const ai = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, refetchInterval: 60000 });
  const ok = health.data?.ok === true;
  return (
    <>
      <span className="badge" style={{ color: ok ? "var(--up)" : "var(--down)", borderColor: ok ? "var(--up-border)" : "var(--down-border)", background: ok ? "var(--up-soft)" : "var(--down-soft)" }}>
        API {ok ? "connected" : "down"}
      </span>
      <span className="badge">
        {ai.data ? (ai.data.keyConfigured ? `gemini · ${ai.data.provider}` : "ruled · offline") : "…"}
      </span>
    </>
  );
}

function Rail() {
  const { segments } = useRoute();
  const { railExpanded, toggleRail } = useUi();
  return (
    <nav className={`rail${railExpanded ? " expanded" : ""}`}>
      <button className="logo" onClick={toggleRail} title={railExpanded ? "Collapse sidebar" : "Expand sidebar"}>
        <span className="mark">
          <IcPulse size={17} />
        </span>
        <span className="logo-text">AlphaLab</span>
      </button>
      <div className="rail-label">Research terminal</div>
      {NAV.map((n) => (
        <button key={n.path} className={n.match(segments) ? "rail-item active" : "rail-item"} onClick={() => navigate(n.path)} title={n.label}>
          <n.icon size={16} />
          <span className="rail-text">{n.label}</span>
        </button>
      ))}
      <div className="rail-spacer" />
    </nav>
  );
}

function Topbar() {
  const { segments } = useRoute();
  const { theme, toggleTheme, setPaletteOpen } = useUi();

  const crumbs: { label: string; path?: string }[] = [];
  if (segments.length === 0) {
    crumbs.push({ label: "Dashboard" });
  } else {
    const map: Record<string, string> = {
      strategies: "Strategies",
      strategy: "Strategies",
      launcher: "Backtest",
      compare: "Compare",
      ai: "AI Copilot",
      run: "Runs",
    };
    const head = map[segments[0]] ?? segments[0];
    crumbs.push({ label: head, path: segments[0] === "strategy" ? "/strategies" : segments[0] === "run" ? "/" : `/${segments[0]}` });
    if (segments.length > 1) crumbs.push({ label: "Detail" });
  }

  return (
    <header className="topbar">
      <div className="crumb">
        {crumbs.map((c, i) => (
          <span key={i} className="row-wrap" style={{ gap: "0.5rem" }}>
            {i > 0 && <span className="sep">/</span>}
            {c.path ? (
              <a
                href={`#${c.path}`}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(c.path!);
                }}
              >
                <strong>{c.label}</strong>
              </a>
            ) : (
              <strong>{c.label}</strong>
            )}
          </span>
        ))}
      </div>
      <div className="grow" />
      <button className="palette-trigger" onClick={() => setPaletteOpen(true)}>
        <IcSearch size={14} />
        <span className="hint-kbd">Search strategies, runs, commands…</span>
        <kbd>⌘K</kbd>
      </button>
      <div className="grow" />
      <div className="topbar-actions">
        <StatusPills />
        <button className="btn glass sm" onClick={toggleTheme} title="Toggle theme">
          {theme === "dark" ? <IcSun size={15} /> : <IcMoon size={15} />}
        </button>
      </div>
    </header>
  );
}

function Router() {
  const { segments } = useRoute();
  const [head, ...rest] = segments;

  let view: React.ReactNode;
  switch (head) {
    case undefined:
      view = <Dashboard />;
      break;
    case "strategies":
      view = <Strategies />;
      break;
    case "strategy":
      view = <StrategyDetail id={rest[0] ?? ""} />;
      break;
    case "launcher":
      view = <Launcher presetVersionId={rest[0] ?? null} />;
      break;
    case "run":
      view = <RunView id={rest[0] ?? ""} />;
      break;
    case "compare":
      view = <Compare seedRunId={rest[0] ?? null} />;
      break;
    case "ai":
      view = <AiPanel presetVersionId={rest[0] ?? null} />;
      break;
    default:
      view = (
        <div className="glass">
          <h3>Page not found</h3>
          <p className="muted">
            Unknown route <code>{`/${segments.join("/")}`}</code> —{" "}
            <a
              href="#/"
              onClick={(e) => {
                e.preventDefault();
                navigate("/");
              }}
            >
              back to dashboard
            </a>
          </p>
        </div>
      );
  }

  useEffect(() => {
    const titles: Record<string, string> = {
      "": "Dashboard",
      strategies: "Strategies",
      strategy: "Strategy",
      launcher: "Backtest",
      run: "Run",
      compare: "Compare",
      ai: "AI Copilot",
    };
    document.title = `${titles[head ?? ""] ?? "AlphaLab"} — AlphaLab`;
  }, [head]);

  return (
    <div className="view-enter" key={`${head ?? ""}-${rest.join("-")}`}>
      {view}
    </div>
  );
}

function Shell() {
  return (
    <div className="shell">
      <Rail />
      <div className="main">
        <Topbar />
        <div className="content">
          <Router />
        </div>
      </div>
      <CommandPalette />
      <Toaster />
    </div>
  );
}

export function App() {
  return (
    <UiProvider>
      <QueryClientProvider client={client}>
        <Shell />
      </QueryClientProvider>
    </UiProvider>
  );
}
