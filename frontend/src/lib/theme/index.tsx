"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { DEFAULT_THEME, THEME_COOKIE, type Theme } from "./shared";

export { THEME_COOKIE, DEFAULT_THEME, type Theme } from "./shared";

/**
 * Light/dark switching, deliberately built on the exact mechanism the language
 * toggle already uses (lib/i18n/index.tsx): a JS-readable cookie that the
 * server layout reads to stamp the right attribute on <html> for the very
 * first paint, with the client provider owning changes from there.
 *
 * Copying that shape rather than inventing a second one matters here. Theme
 * has the same flash-of-wrong-value problem language has, and it is worse:
 * a reader who chose light would get a full-screen black flash on every
 * navigation. Reading the cookie server-side is what avoids it, and doing it
 * the same way twice means there is one pattern to get right.
 *
 * The attribute is only ever set to "light". Dark is the bare :root default,
 * so no attribute means dark -- see tokens.css.
 */
const ONE_YEAR = 60 * 60 * 24 * 365;

type Ctx = {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
};

const ThemeContext = createContext<Ctx | null>(null);

export function ThemeProvider({ initial, children }: { initial: Theme; children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initial);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    if (typeof document === "undefined") return;
    document.cookie = `${THEME_COOKIE}=${next}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
    // Keep the server-rendered attribute in sync for this session, so the
    // palette swaps immediately rather than at the next full navigation.
    if (next === DEFAULT_THEME) {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", next);
    }
  }, []);

  const toggle = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  const ctx = useMemo<Ctx>(() => ({ theme, setTheme, toggle }), [theme, setTheme, toggle]);

  return <ThemeContext.Provider value={ctx}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Ctx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
