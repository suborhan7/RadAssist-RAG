import { cn } from "@/lib/cn";

/** Retrieved evidence is always steel (§P2). The % is machine output, so mono (§P3). */
export function SimilarityBar({
  value, highlighted, className,
}: { value: number; highlighted?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-sunken">
        <div
          className={cn("h-full rounded-full bg-steel origin-left transition-transform duration-state",
                        highlighted && "animate-[pulse-bar_300ms_ease-out]")}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="w-11 shrink-0 text-right font-mono text-data-sm text-ink-2">{value.toFixed(1)}%</span>
    </div>
  );
}
