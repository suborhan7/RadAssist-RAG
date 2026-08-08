import { cn } from "@/lib/cn";

/**
 * The 60px screen header bar every app screen opens with: hairline bottom,
 * 30px horizontal padding, title at 16px/600, then screen-specific mono
 * metadata, a flex-1 spacer, then right-aligned status or actions.
 *
 * `meta` is the mono-grey run after the title (ids, accession, counts).
 * `actions` is the right-aligned region (status text, buttons, the language
 * toggle on the workspace).
 */
export function ScreenHeader({
  title,
  meta,
  actions,
  className,
}: {
  title: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30",
        className,
      )}
    >
      <span className="text-screen-title text-text-primary">{title}</span>
      {meta != null && <span className="font-mono text-mono-meta text-text-tertiary">{meta}</span>}
      <span className="flex-1" />
      {actions}
    </header>
  );
}
