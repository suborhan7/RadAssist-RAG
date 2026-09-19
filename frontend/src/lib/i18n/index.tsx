"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { en } from "./dictionaries/en";
import { bn } from "./dictionaries/bn";
import { LANG_COOKIE, type Lang, type Dict } from "./shared";

export { LANG_COOKIE, type Lang } from "./shared";

/**
 * Custom, dependency-free internationalization for the Reading Room UI.
 *
 * Why not a library: the app carries no i18n dependency and only three real
 * deps (clsx/diff/tailwind-merge). A tiny context + two typed dictionaries fits
 * that ethos and gives full control over the Bengali typography axis (font +
 * no-case eyebrows), which a generic library would not know about.
 *
 * The active language is persisted to a JS-readable cookie `rr_lang` (NOT the
 * httpOnly auth cookie) so the *server* `layout.tsx` can read it and pick the
 * right <html lang> + body font class for the very first paint — no flash, no
 * hydration mismatch. The client provider owns toggling from there.
 *
 * Bengali strings are a full first-pass by the build, marked provisional and
 * awaiting review by a Bengali-speaking clinician — consistent with the
 * project's existing "provisional" convention for its Bengali report headers.
 */
const ONE_YEAR = 60 * 60 * 24 * 365;

const DICTS: Record<Lang, Dict> = { en, bn };

type TParams = Record<string, unknown>;
type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  toggle: () => void;
  t: (key: string, params?: TParams) => string;
};

const LanguageContext = createContext<Ctx | null>(null);

/** Read the persisted language on the client. Falls back to English. */
export function readLangCookie(): Lang {
  if (typeof document === "undefined") return "en";
  const m = document.cookie.match(/(?:^|;\s*)rr_lang=(en|bn)\b/);
  return (m?.[1] as Lang) ?? "en";
}

/**
 * Whether this browser has ever recorded a language choice. Distinct from
 * readLangCookie(), whose "en" fallback is indistinguishable from a deliberate
 * "en" -- a caller deciding whether it may seed the language from a stored
 * preference has to know "unset" from "chosen English", or it would override a
 * real choice. Used by DoctorProvider for exactly that.
 */
export function hasLangCookie(): boolean {
  if (typeof document === "undefined") return false;
  return /(?:^|;\s*)rr_lang=(en|bn)\b/.test(document.cookie);
}

export function LanguageProvider({
  initial,
  children,
}: {
  initial: Lang;
  children: ReactNode;
}) {
  const [lang, setLangState] = useState<Lang>(initial);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    if (typeof document !== "undefined") {
      document.cookie = `${LANG_COOKIE}=${next}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
      // Keep the server-rendered body class in sync for the current session so
      // the central Bengali typography rules (globals.css `body.lang-bn`) apply
      // immediately, before the next full navigation re-reads the cookie.
      document.body.classList.toggle("lang-bn", next === "bn");
      document.documentElement.setAttribute("lang", next);
    }
  }, []);

  const toggle = useCallback(() => {
    setLang(lang === "en" ? "bn" : "en");
  }, [lang, setLang]);

  const t = useCallback(
    (key: string, params?: TParams) => {
      const dict = DICTS[lang];
      const value = dict[key] ?? en[key];
      if (value == null) return key; // missing in both -> show the key, loudly
      return typeof value === "function" ? value(params ?? {}) : value;
    },
    [lang],
  );

  const ctx = useMemo<Ctx>(() => ({ lang, setLang, toggle, t }), [lang, setLang, toggle, t]);

  return <LanguageContext.Provider value={ctx}>{children}</LanguageContext.Provider>;
}

export function useT(): Ctx {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useT must be used within a LanguageProvider");
  return ctx;
}
