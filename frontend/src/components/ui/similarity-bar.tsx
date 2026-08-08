import { cn } from "@/lib/cn";

/** Retrieved evidence is always cyan (the retrieval accent). The % is machine
 *  output, so mono. `highlighted` lights the bar solid (a "lit" case); the rest
 *  sit at the dimmer translucent cyan. */
export function SimilarityBar({
  value, highlighted, className,
}: { value: number; highlighted?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-9", className)}>
      <div className="h-4 flex-1 overflow-hidden rounded-full bg-bg-raised">
        <div
          className={cn(
            "h-full origin-left rounded-full transition-transform duration-state",
            highlighted ? "bg-cyan" : "bg-cyan-line",
          )}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="w-44 shrink-0 text-right font-mono text-mono-meta text-text-secondary">
        {value.toFixed(1)}%
      </span>
    </div>
  );
}
