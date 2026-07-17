import { cn } from "@/lib/cn";

/**
 * §10.9. Static blocks. NO SHIMMER.
 *
 * Shimmer is an AI-startup tell and it implies speed the LLM does not have.
 * The shape of the content arrives before the content; that is the whole job.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("rounded-in bg-sunken", className)} aria-hidden />;
}

export function SkeletonReport() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Generating report">
      {[3, 5, 2].map((lines, s) => (
        <div key={s}>
          <Skeleton className="mb-3 h-3 w-24" />
          <div className="space-y-2">
            {Array.from({ length: lines }).map((_, i) => (
              <Skeleton key={i} className={cn("h-3.5", i === lines - 1 ? "w-2/3" : "w-full")} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
