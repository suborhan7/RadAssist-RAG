"use client";

import { cn } from "@/lib/cn";

export type ReportLang = "en" | "bn";

/**
 * The workspace report-language toggle. A segmented EN / বাংলা control that
 * switches the report column between English and Bangla (font family + line
 * height); it does not affect chrome. Controlled: the workspace owns the
 * per-report `lang` (defaulted from the doctor's Settings "Report language"),
 * so live wiring to report rendering happens when the workspace route is
 * ported. The active segment is filled with the hairline colour, exactly as
 * the mock specs it.
 */
export function LanguageToggle({
  value,
  onChange,
  className,
}: {
  value: ReportLang;
  onChange: (lang: ReportLang) => void;
  className?: string;
}) {
  return (
    <span
      className={cn("flex overflow-hidden rounded-control border border-strong", className)}
      role="group"
      aria-label="Report language"
    >
      <button
        type="button"
        onClick={() => onChange("en")}
        aria-pressed={value === "en"}
        className={cn(
          "cursor-pointer px-11 py-6 font-mono text-mono-meta",
          value === "en" ? "bg-border text-text-primary" : "text-text-secondary",
        )}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => onChange("bn")}
        aria-pressed={value === "bn"}
        className={cn(
          "cursor-pointer px-11 py-6 font-bn text-mono-meta",
          value === "bn" ? "bg-border text-text-primary" : "text-text-secondary",
        )}
      >
        বাংলা
      </button>
    </span>
  );
}
