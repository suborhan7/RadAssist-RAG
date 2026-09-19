"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { BackArrowIcon } from "./rail-icons";

/**
 * The 60px screen header bar every app screen opens with: hairline bottom,
 * 30px horizontal padding, title at 16px/600, then screen-specific mono
 * metadata, a flex-1 spacer, then right-aligned status or actions.
 *
 * `meta` is the mono-grey run after the title (ids, accession, counts).
 * `actions` is the right-aligned region (status text, buttons, the language
 * toggle on the workspace).
 *
 * `back` is the leading return affordance. It was added after a tester
 * reported having no way to cancel out of a screen: the deep views (workspace,
 * compare, explainability) had only an implicit route back -- the patient's
 * name, styled as a heading, which nobody reads as "back". Putting it here
 * rather than on each page means one arrow, one position, one behaviour on
 * every screen, which is what makes it findable at all. `onBack` exists for
 * the workspace, whose return has to pass through its unsaved-changes guard.
 */
export function ScreenHeader({
  title,
  meta,
  actions,
  back,
  className,
}: {
  title: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  back?: { href: string; labelKey?: string; onClick?: (e: React.MouseEvent) => void };
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30",
        className,
      )}
    >
      {back && <BackLink {...back} />}
      <span className="text-screen-title text-text-primary">{title}</span>
      {meta != null && <span className="font-mono text-mono-meta text-text-tertiary">{meta}</span>}
      <span className="flex-1" />
      {actions}
    </header>
  );
}

/**
 * Exported so the screens that hand-roll their own header bar (workspace,
 * compare, explainability, upload -- each has a bespoke middle section) get the
 * identical control in the identical position. The point of the fix is that
 * back is always the first thing on the bar; that only holds if there is one
 * implementation of it.
 */
export function BackLink({
  href,
  labelKey,
  onClick,
}: {
  href: string;
  labelKey?: string;
  onClick?: (e: React.MouseEvent) => void;
}) {
  const { t } = useT();
  const label = t(labelKey ?? "nav.back");

  return (
    <Link
      href={href}
      onClick={onClick}
      aria-label={label}
      title={label}
      className="-ml-6 flex items-center gap-8 rounded-control px-6 py-4 text-sm text-text-tertiary transition-colors duration-hover hover:bg-bg-hover hover:text-cyan"
    >
      <BackArrowIcon className="flex-none" />
      <span className="hidden sm:inline">{label}</span>
    </Link>
  );
}
