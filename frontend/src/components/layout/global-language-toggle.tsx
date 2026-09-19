"use client";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/**
 * The global EN / বাংলা switch. Fixed to the top-right so it is present on the
 * very first page (Landing / Sign in / Register) and every screen after,
 * independent of each page's own chrome. Segmented control exactly as the mock
 * specs it: the active half fills with the hairline colour; EN renders in mono,
 * বাংলা in the Bengali face. Flipping it rewrites the `rr_lang` cookie (read by
 * the server layout on the next paint) and swaps the whole app's language,
 * including the language new reports are generated in.
 *
 * Hidden on print — a signed report should not carry a UI control.
 *
 * Pinned bottom-right, not top-right: several screens (the dashboard, patient
 * profile and workspace headers, the landing Sign-in) put action buttons in the
 * top-right, and a fixed control there covered them. The bottom-right corner is
 * clear on every route, so the switch never hides a button.
 *
 * The fixed positioning now lives on GlobalControls, which pairs this with the
 * theme switch in one cluster -- two independently-fixed controls in the same
 * corner would sit on top of each other.
 */
export function GlobalLanguageToggle() {
  const { lang, setLang, t } = useT();

  return (
      <span
        className="pointer-events-auto flex overflow-hidden rounded-control border border-strong bg-bg-raised/90 backdrop-blur"
        role="group"
        aria-label={t("lang.label")}
      >
        <button
          type="button"
          onClick={() => setLang("en")}
          aria-pressed={lang === "en"}
          className={cn(
            "cursor-pointer px-12 py-7 font-mono text-mono-meta transition-colors duration-hover active:scale-[0.98]",
            lang === "en" ? "bg-border text-text-primary" : "text-text-secondary hover:text-text-primary",
          )}
        >
          EN
        </button>
        <button
          type="button"
          onClick={() => setLang("bn")}
          aria-pressed={lang === "bn"}
          className={cn(
            "cursor-pointer px-12 py-7 font-bn text-mono-meta transition-colors duration-hover active:scale-[0.98]",
            lang === "bn" ? "bg-border text-text-primary" : "text-text-secondary hover:text-text-primary",
          )}
        >
          বাংলা
        </button>
      </span>
  );
}
