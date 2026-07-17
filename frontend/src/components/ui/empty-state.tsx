import type { ReactNode } from "react";

/**
 * §7. An empty state always contains the action that resolves it.
 * The dead end becomes the happy path.
 */
export function EmptyState({
  icon, title, body, actions,
}: { icon?: ReactNode; title: string; body: string; actions?: ReactNode }) {
  return (
    <div className="px-page py-14 text-center">
      {icon && (
        <div className="mx-auto mb-4 grid h-11 w-11 place-items-center rounded-full bg-steel-tint text-steel">
          {icon}
        </div>
      )}
      <h2 className="text-h2 text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-[460px] text-body leading-[22px] text-ink-2">{body}</p>
      {actions && <div className="mt-5 flex justify-center gap-2">{actions}</div>}
    </div>
  );
}
