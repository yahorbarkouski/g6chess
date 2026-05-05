import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

const THEME_STORAGE_KEY = "g6explanation.theme";
const THEME_CYCLE: readonly Theme[] = ["system", "light", "dark"];
const COLOR_SCHEME_QUERY = "(prefers-color-scheme: dark)";

function readStoredTheme(): Theme {
  if (typeof window === "undefined") {
    return "system";
  }
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

function isThemeDark(theme: Theme): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  if (theme === "dark") {
    return true;
  }
  if (theme === "light") {
    return false;
  }
  return window.matchMedia(COLOR_SCHEME_QUERY).matches;
}

function applyDocumentTheme(theme: Theme): void {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.classList.toggle("dark", isThemeDark(theme));
}

export function useTheme(): { theme: Theme; cycle: () => void } {
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    applyDocumentTheme(theme);
    if (theme !== "system") {
      return;
    }
    const mediaQuery = window.matchMedia(COLOR_SCHEME_QUERY);
    const handleChange = () => applyDocumentTheme("system");
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme]);

  const cycle = useCallback(() => {
    setTheme((current) => {
      const nextIndex = (THEME_CYCLE.indexOf(current) + 1) % THEME_CYCLE.length;
      const next = THEME_CYCLE[nextIndex] ?? "system";
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {}
      return next;
    });
  }, []);

  return { theme, cycle };
}
