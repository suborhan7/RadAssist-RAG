"use client";

import { GlobalLanguageToggle } from "./global-language-toggle";
import { GlobalThemeToggle } from "./global-theme-toggle";

/**
 * The bottom-right control cluster: theme, then language.
 *
 * Both are app-wide preferences that have to be reachable from the very first
 * screen (Landing / Sign in / Register carry no rail), so they are fixed rather
 * than living in any page's chrome. They share one fixed container because two
 * separately-fixed controls in the same corner would overlap.
 *
 * Theme sits left of language on purpose: the language control is the wider and
 * more frequently used of the two, so it keeps the corner position it already
 * had and nothing a reader learned about where to find it changes.
 */
export function GlobalControls() {
  return (
    <div className="pointer-events-none fixed bottom-16 right-16 z-50 flex items-center justify-end gap-8 print:hidden">
      <GlobalThemeToggle />
      <GlobalLanguageToggle />
    </div>
  );
}
