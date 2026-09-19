"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getCurrentDoctor } from "@/lib/api-client";
import { CHROMELESS_ROUTES } from "@/lib/chromeless-routes";
import { resolveTopK } from "@/lib/doctor-defaults";
import { hasLangCookie, useT, type Lang } from "@/lib/i18n";
import type { paths } from "@/lib/generated/api";

type CurrentDoctor =
  paths["/auth/me"]["get"]["responses"][200]["content"]["application/json"];

/**
 * The authenticated doctor and their saved preferences, fetched once per
 * navigation and shared by every screen that needs them.
 *
 * Why this exists: Settings has always *written* default_top_k,
 * default_language, default_questionnaire_skip, default_rail_state and
 * default_export_format to the doctors table, and nothing anywhere ever read
 * them back. The screen saved successfully, showed a success state, and
 * changed nothing about the system -- the reported "k=3 still shows k=5" was
 * one visible symptom of a form that was entirely inert. Preferences are only
 * real once something consumes them, so consumption goes through here rather
 * than each screen re-fetching /auth/me and re-deriving its own fallbacks.
 *
 * The fetch is keyed on pathname, preserving AppRail's original behaviour --
 * that is what makes the rail appear after a client-side navigation from
 * /login. `refresh()` covers the in-place case (saving Settings) where the
 * path does not change.
 */
type Ctx = {
  doctor: CurrentDoctor | null;
  loading: boolean;
  /**
   * The doctor's k, already resolved against the default and the valid range.
   * Read this -- never write a literal at a call site (see doctor-defaults.ts).
   */
  topK: number;
  /** default_questionnaire_skip, resolved against false. */
  questionnaireSkip: boolean;
  /** Re-read /auth/me without a navigation (Settings calls this after saving). */
  refresh: () => void;
};

const DoctorContext = createContext<Ctx | null>(null);

export function DoctorProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { setLang } = useT();
  const [doctor, setDoctor] = useState<CurrentDoctor | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshNonce, setRefreshNonce] = useState(0);

  const refresh = useCallback(() => setRefreshNonce((n) => n + 1), []);

  // Landing / Sign in / Register have no authenticated doctor by definition;
  // asking anyway just trades a guaranteed 401 for a network round trip on the
  // first page most visitors see. Derived, not stored: writing state for this
  // in the effect body would cascade a render for something already knowable
  // from the pathname alone.
  const chromeless = CHROMELESS_ROUTES.has(pathname);

  useEffect(() => {
    if (chromeless) return;

    let cancelled = false;
    getCurrentDoctor()
      .then((result) => {
        if (!cancelled) setDoctor(result ?? null);
      })
      .catch(() => {
        if (!cancelled) setDoctor(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [chromeless, pathname, refreshNonce]);

  // default_language seeds the interface language ONLY when this browser has
  // no rr_lang cookie yet. An explicit toggle is a direct act by the person at
  // the screen and outranks a stored default -- without this guard, switching
  // to বাংলা would be silently reverted on the next navigation, which reads as
  // a broken toggle rather than an honoured preference.
  useEffect(() => {
    const preferred = doctor?.default_language;
    if (preferred !== "en" && preferred !== "bn") return;
    if (hasLangCookie()) return;
    setLang(preferred as Lang);
  }, [doctor, setLang]);

  const current = chromeless ? null : doctor;

  const ctx = useMemo<Ctx>(
    () => ({
      doctor: current,
      loading: chromeless ? false : loading,
      topK: resolveTopK(current?.default_top_k),
      questionnaireSkip: current?.default_questionnaire_skip ?? false,
      refresh,
    }),
    [current, chromeless, loading, refresh],
  );

  return <DoctorContext.Provider value={ctx}>{children}</DoctorContext.Provider>;
}

export function useDoctor(): Ctx {
  const ctx = useContext(DoctorContext);
  if (!ctx) throw new Error("useDoctor must be used within a DoctorProvider");
  return ctx;
}
