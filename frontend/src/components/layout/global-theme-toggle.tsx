"use client";

import { useTheme } from "@/lib/theme";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { MoonIcon, SunIcon } from "./rail-icons";

/**
 * The global Dark / Light switch, built as the same segmented control as the
 * language toggle beside it -- same border, same fill-the-active-half
 * treatment, same sizing. Two adjacent controls that behave identically are
 * one thing to learn; two that merely look similar are two.
 *
 * Icons rather than words: "Dark"/"Light" would need translating and would
 * widen the cluster, and a sun/moon pair is unambiguous at this size. The
 * accessible names are still real translated strings.
 *
 * Hidden on print, like the language toggle -- a signed report carries no UI.
 */
export function GlobalThemeToggle() {
  const { theme, setTheme } = useTheme();
  const { t } = useT();

  return (
    <span
      className="pointer-events-auto flex overflow-hidden rounded-control border border-strong bg-bg-raised/90 backdrop-blur"
      role="group"
      aria-label={t("theme.label")}
    >
      <button
        type="button"
        onClick={() => setTheme("dark")}
        aria-pressed={theme === "dark"}
        aria-label={t("theme.dark")}
        title={t("theme.dark")}
        className={cn(
          "cursor-pointer px-11 py-7 transition-colors duration-hover active:scale-[0.98]",
          theme === "dark" ? "bg-border text-text-primary" : "text-text-secondary hover:text-text-primary",
        )}
      >
        <MoonIcon />
      </button>
      <button
        type="button"
        onClick={() => setTheme("light")}
        aria-pressed={theme === "light"}
        aria-label={t("theme.light")}
        title={t("theme.light")}
        className={cn(
          "cursor-pointer px-11 py-7 transition-colors duration-hover active:scale-[0.98]",
          theme === "light" ? "bg-border text-text-primary" : "text-text-secondary hover:text-text-primary",
        )}
      >
        <SunIcon />
      </button>
    </span>
  );
}

