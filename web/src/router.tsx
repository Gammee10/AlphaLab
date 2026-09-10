// Minimal hash-based router. No deps; keeps FastAPI static serving intact.

import { useEffect, useState, type ReactNode, type MouseEvent } from "react";

function currentPath(): string {
  const h = window.location.hash.replace(/^#/, "");
  return h === "" ? "/" : h;
}

export function navigate(path: string): void {
  if (currentPath() === path) return;
  window.location.hash = path;
}

export interface Route {
  path: string;
  segments: string[];
}

export function useRoute(): Route {
  const [path, setPath] = useState(currentPath);
  useEffect(() => {
    const onChange = () => setPath(currentPath());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return { path, segments: path.split("/").filter(Boolean) };
}

export function Link({
  to,
  children,
  className,
  onClick,
}: {
  to: string;
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    onClick?.();
    navigate(to);
  };
  return (
    <a href={`#${to}`} className={className} onClick={handle}>
      {children}
    </a>
  );
}
