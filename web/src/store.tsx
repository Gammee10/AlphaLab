// Global UI state: theme, rail expansion, toasts, command palette.
// Presentation-only state — no financial data lives here.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Theme = "dark" | "light";
export interface Toast {
  id: number;
  kind: "ok" | "error" | "info";
  text: string;
}

interface UiState {
  theme: Theme;
  toggleTheme: () => void;
  railExpanded: boolean;
  toggleRail: () => void;
  toasts: Toast[];
  toast: (text: string, kind?: Toast["kind"]) => void;
  dismissToast: (id: number) => void;
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
}

const Ctx = createContext<UiState | null>(null);

let toastSeq = 0;

export function UiProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("alphalab.theme");
    return saved === "light" ? "light" : "dark";
  });
  const [railExpanded, setRailExpanded] = useState(() => localStorage.getItem("alphalab.rail") !== "0");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("alphalab.theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("alphalab.rail", railExpanded ? "1" : "0");
  }, [railExpanded]);

  const dismissToast = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const toast = (text: string, kind: Toast["kind"] = "info") => {
    toastSeq += 1;
    const id = toastSeq;
    setToasts((prev) => [...prev.slice(-3), { id, kind, text }]);
    window.setTimeout(() => dismissToast(id), 4200);
  };

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  const toggleRail = () => setRailExpanded((v) => !v);

  return (
    <Ctx.Provider
      value={{ theme, toggleTheme, railExpanded, toggleRail, toasts, toast, dismissToast, paletteOpen, setPaletteOpen }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useUi(): UiState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useUi outside UiProvider");
  return v;
}

export function errText(e: Error & { code?: string }): string {
  return e.code ? `${e.code}: ${e.message}` : e.message;
}
