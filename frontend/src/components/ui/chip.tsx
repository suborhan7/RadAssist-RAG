import { cn } from "@/lib/cn";

/* ---------------- StatusChip — the human-in-the-loop machine (§10.1) ------- */

export type ReportStatus = "draft" | "review" | "edited" | "final";

const STATUS: Record<ReportStatus, { label: string; cls: string }> = {
  draft:  { label: "AI Draft",      cls: "bg-caution-bg text-caution-ink border-caution-bd" },
  review: { label: "Under Review",  cls: "bg-steel-tint text-steel-ink border-steel-bd" },
  edited: { label: "Doctor Edited", cls: "bg-steel-tint text-steel-ink border-steel-bd" },
  final:  { label: "Final",         cls: "bg-stable-bg text-stable-ink border-stable-bd" },
};

export function StatusChip({ status }: { status: ReportStatus }) {
  const s = STATUS[status];
  return (
    <span className={cn("inline-flex h-6 items-center gap-1.5 rounded-full border px-3 text-label", s.cls)}>
      <Dot />
      {s.label}
    </span>
  );
}

/* ---------------- OwnershipChip — text first, texture second (§9) ---------- */

export function OwnershipChip({ doctor }: { doctor: string | null }) {
  // null == you. The chip is text, so the a11y property holds without the hatch.
  return doctor === null ? (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-steel-bd bg-steel-tint px-3 text-label text-steel-ink">
      <Check /> You
    </span>
  ) : (
    <span className="inline-flex h-6 items-center rounded-full border border-hairline-strong bg-sunken px-3 text-label text-ink-2">
      {doctor}
    </span>
  );
}

/* ---------------- ServiceChip --------------------------------------------- */

export function ServiceChip({
  name, value, state = "online",
}: { name: string; value: string; state?: "online" | "degraded" | "offline" }) {
  return (
    <div className="flex items-center gap-2 border-b border-hairline py-2 last:border-0">
      <Dot className={state === "online" ? "text-stable" : state === "degraded" ? "text-caution" : "text-critical"} />
      <span className="text-sm text-ink-2">{name}</span>
      <span className="ml-auto font-mono text-data-sm text-ink">{value}</span>
    </div>
  );
}

export function Tag({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "steel" }) {
  return (
    <span className={cn(
      "inline-flex h-5 items-center rounded-in border px-1.5 text-eyebrow uppercase",
      tone === "steel" ? "border-steel-bd bg-steel-tint text-steel-ink" : "border-hairline bg-sunken text-ink-3",
    )}>
      {children}
    </span>
  );
}

const Dot = ({ className }: { className?: string }) => (
  <span className={cn("inline-block h-1.5 w-1.5 rounded-full bg-current", className)} aria-hidden />
);
const Check = () => (
  <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" aria-hidden>
    <path d="M2.5 6.5 5 9l4.5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
