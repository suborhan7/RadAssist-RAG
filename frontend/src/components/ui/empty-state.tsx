import type { ReactNode } from "react";

/**
 * §7. An empty state always contains the action that resolves it.
 * The dead end becomes the happy path.
 */
export function EmptyState({
  icon, title, body, actions,
}: { icon?: ReactNode; title: string; body: string; actions?: ReactNode }) {
  return (
    <div className="px-30 py-14 text-center">
      {icon && (
        <div className="mx-auto mb-14 grid h-44 w-44 place-items-center rounded-full bg-cyan-wash text-cyan">
          {icon}
        </div>
      )}
      <h2 className="text-panel text-text-primary">{title}</h2>
      <p className="mx-auto mt-8 max-w-[460px] text-sm leading-relaxed text-text-secondary">{body}</p>
      {actions && <div className="mt-18 flex justify-center gap-12">{actions}</div>}
    </div>
  );
}
