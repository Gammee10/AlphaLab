import { useEffect, useMemo, useRef, useState } from "react";
import { IcMoon, IcPulse, IcPlay, IcLayers, IcSpark, IcSun, IcSwap, IcSearch, IcPanel } from "../components/icons";
import { useUi } from "../store";
import { navigate } from "../router";

interface Cmd {
  id: string;
  label: string;
  hint?: string;
  icon: (props: { size?: number }) => React.ReactElement;
  run: () => void;
}

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen, toggleTheme, theme, railExpanded, toggleRail } = useUi();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Cmd[] = useMemo(
    () => [
      { id: "nav-dash", label: "Go to Dashboard", icon: IcPulse, hint: "nav", run: () => navigate("/") },
      { id: "nav-strats", label: "Go to Strategies", icon: IcLayers, hint: "nav", run: () => navigate("/strategies") },
      { id: "nav-launch", label: "New backtest run", icon: IcPlay, hint: "action", run: () => navigate("/launcher") },
      { id: "nav-compare", label: "Compare runs", icon: IcSwap, hint: "nav", run: () => navigate("/compare") },
      { id: "nav-ai", label: "Open AI copilot", icon: IcSpark, hint: "nav", run: () => navigate("/ai") },
      {
        id: "act-theme",
        label: theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
        icon: theme === "dark" ? IcSun : IcMoon,
        hint: "action",
        run: toggleTheme,
      },
      {
        id: "act-rail",
        label: railExpanded ? "Collapse sidebar" : "Expand sidebar",
        icon: IcPanel,
        hint: "action",
        run: toggleRail,
      },
    ],
    [theme, railExpanded, toggleTheme, toggleRail],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(needle));
  }, [q, commands]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(!paletteOpen);
      } else if (e.key === "Escape") {
        setPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paletteOpen, setPaletteOpen]);

  useEffect(() => {
    if (paletteOpen) {
      setQ("");
      setSel(0);
      window.setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [paletteOpen]);

  if (!paletteOpen) return null;

  const exec = (c: Cmd) => {
    setPaletteOpen(false);
    c.run();
  };

  return (
    <div className="palette-scrim" onMouseDown={(e) => e.target === e.currentTarget && setPaletteOpen(false)}>
      <div className="palette-box">
        <div className="palette-input">
          <IcSearch size={15} />
          <input
            ref={inputRef}
            value={q}
            placeholder="Type a command…"
            onChange={(e) => {
              setQ(e.target.value);
              setSel(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setSel((s) => Math.min(s + 1, filtered.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSel((s) => Math.max(s - 1, 0));
              } else if (e.key === "Enter" && filtered[sel]) {
                exec(filtered[sel]);
              }
            }}
          />
          <kbd>esc</kbd>
        </div>
        <div className="palette-list">
          {filtered.length === 0 && <div className="palette-empty">No matching commands</div>}
          {filtered.map((c, i) => (
            <button
              key={c.id}
              className={i === sel ? "palette-item active" : "palette-item"}
              onMouseEnter={() => setSel(i)}
              onClick={() => exec(c)}
            >
              <c.icon size={15} />
              {c.label}
              {c.hint && <span className="hint">{c.hint}</span>}
            </button>
          ))}
        </div>
        <div className="palette-foot">
          <span>
            <kbd>↑</kbd> <kbd>↓</kbd> navigate
          </span>
          <span>
            <kbd>↵</kbd> run
          </span>
          <span className="grow" />
          <span>⌘K / Ctrl+K</span>
        </div>
      </div>
    </div>
  );
}
