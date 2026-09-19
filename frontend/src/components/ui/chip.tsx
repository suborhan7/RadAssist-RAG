"use client";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/* ============================================================================
   "Reading Room" pills. Two accents only: cyan = interaction / confirmed /
   "yours", amber = attention / unsupported. Anything that is neither uses
   text-secondary inside a border-strong outline (no third hue). Pill shape is
   fixed: rounded-full, 1px border, 3/11 padding, 12.5px, no wrap.
   ============================================================================ */

type PillTone = "cyan" | "amber" | "muted";

const PILL: Record<PillTone, string> = {
  cyan: "border-cyan-line bg-cyan-wash text-cyan",
  amber: "border-amber-line bg-amber-wash text-amber",
  muted: "border-strong text-text-secondary",
};

const pillBase = "inline-flex items-center gap-6 rounded-full border px-11 py-3 text-chip whitespace-nowrap";

/* ---------------- StatusChip — the human-in-the-loop machine --------------- */

export type ReportStatus = "draft" | "review" | "edited" | "final";

// AI draft = the model's, unreviewed => amber (attention). Under review /
// doctor-edited = a person is in the loop => cyan. Final/signed = settled,
// needs no emphasis => muted.
const STATUS: Record<ReportStatus, { labelKey: string; tone: PillTone }> = {
  draft:  { labelKey: "chip.statusDraft",  tone: "amber" },
  review: { labelKey: "chip.statusReview", tone: "cyan" },
  edited: { labelKey: "chip.statusEdited", tone: "cyan" },
  final:  { labelKey: "chip.statusFinal",  tone: "muted" },
};

export function StatusChip({ status }: { status: ReportStatus }) {
  const { t } = useT();
  const s = STATUS[status];
  return <span className={cn(pillBase, PILL[s.tone])}>{t(s.labelKey)}</span>;
}

/* ---------------- OwnershipChip — text first, texture second --------------- */

export function OwnershipChip({ doctor }: { doctor: string | null }) {
  const { t } = useT();
  // null == you. cyan is the "yours" accent. Another doctor is neither an
  // interaction nor a risk, so it reads muted. The chip is text, so the a11y
  // property holds without any texture.
  return doctor === null ? (
    <span className={cn(pillBase, PILL.cyan)}>
      <Check /> {t("chip.you")}
    </span>
  ) : (
    <span className={cn(pillBase, PILL.muted)}>{doctor}</span>
  );
}

/* ---------------- ServiceChip --------------------------------------------- */

export function ServiceChip({
  name, value, state = "online",
}: { name: string; value: string; state?: "online" | "degraded" | "offline" }) {
  // Dots: cyan for ok, amber for anything not ok. Colour is never the only
  // signal -- the value sits right beside it.
  return (
    <div className="flex items-center gap-12 border-b border-hairline py-12 last:border-0">
      <Dot className={state === "online" ? "text-cyan" : "text-amber"} />
      <span className="text-sm text-text-secondary">{name}</span>
      <span className="ml-auto font-mono text-mono-meta-lg text-text-primary">{value}</span>
    </div>
  );
}

export function Tag({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "steel" }) {
  // `tone="steel"` is kept for API compatibility; in this theme it renders cyan.
  return (
    <span className={cn(
      "inline-flex items-center rounded-chip border px-6 py-3 font-mono text-eyebrow uppercase",
      tone === "steel" ? "border-cyan-line bg-cyan-wash text-cyan" : "border-strong text-text-tertiary",
    )}>
      {children}
    </span>
  );
}

const Dot = ({ className }: { className?: string }) => (
  <span className={cn("inline-block h-6 w-6 rounded-full bg-current", className)} aria-hidden />
);
const Check = () => (
  <svg className="h-12 w-12" viewBox="0 0 12 12" fill="none" aria-hidden>
    <path d="M2.5 6.5 5 9l4.5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
