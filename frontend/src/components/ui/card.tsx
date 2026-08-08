import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * "Reading Room" raised panel. No elevation/shadow in this theme -- depth
 * reads from the near-black surface stack (bg-raised over bg-app) plus a
 * hairline, not a drop shadow. Used for dialogs and inset blocks; the
 * three reading-station columns build their own edge-to-edge chrome instead.
 */
export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-panel border border-hairline bg-bg-raised", className)} {...rest} />;
}

export function CardHeader({
  title, sub, action, className,
}: { title: ReactNode; sub?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-12 border-b border-hairline px-20 py-16", className)}>
      <div className="min-w-0">
        <div className="text-screen-title text-text-primary">{title}</div>
        {sub && <div className="mt-3 text-sm text-text-tertiary">{sub}</div>}
      </div>
      {action && <div className="ml-auto shrink-0">{action}</div>}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-20", className)} {...rest} />;
}
