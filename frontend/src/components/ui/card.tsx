import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Elevation 0 by default (§6.5): cards live in the document. They lift only
 * when they become dismissible — which a card never is.
 */
export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card border border-hairline bg-surface", className)} {...rest} />;
}

export function CardHeader({
  title, sub, action, className,
}: { title: ReactNode; sub?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-3 border-b border-hairline p-tight px-card", className)}>
      <div className="min-w-0">
        <div className="text-h3 text-ink">{title}</div>
        {sub && <div className="mt-0.5 text-sm text-ink-3">{sub}</div>}
      </div>
      {action && <div className="ml-auto shrink-0">{action}</div>}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-card", className)} {...rest} />;
}
