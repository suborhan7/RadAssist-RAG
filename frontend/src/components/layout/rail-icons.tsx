/**
 * App icons (originally the rail set, now the whole family). The prototype used Unicode geometric glyphs (▤ ⌕ ◫ ＋ ▥ ? ⇄ ◍ →)
 * as placeholders and warned they risk rendering as tofu (a ⏻ power symbol did,
 * and was swapped for →). The repo ships no icon library, so these are small
 * hand-authored inline SVGs: 18px, 1px currentColor stroke, aria-hidden. The
 * visible text label beside each is what carries meaning (accessibility note).
 */
type IconProps = { className?: string };

const base = {
  width: 18,
  height: 18,
  viewBox: "0 0 18 18",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

/** Queue -- stacked worklist rows (▤). */
export function QueueIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <line x1="3" y1="5" x2="15" y2="5" />
      <line x1="3" y1="9" x2="15" y2="9" />
      <line x1="3" y1="13" x2="15" y2="13" />
    </svg>
  );
}

/** Find patient -- magnifier (⌕). */
export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="8" cy="8" r="4.5" />
      <line x1="11.5" y1="11.5" x2="15" y2="15" />
    </svg>
  );
}

/** Patients -- record card (◫). */
export function PatientsIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="3" y="3" width="12" height="12" rx="1.5" />
      <line x1="9" y1="3" x2="9" y2="15" />
    </svg>
  );
}

/** New examination -- plus (＋). */
export function NewExamIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <line x1="9" y1="3.5" x2="9" y2="14.5" />
      <line x1="3.5" y1="9" x2="14.5" y2="9" />
    </svg>
  );
}

/** Workspace -- side-by-side columns (▥). */
export function WorkspaceIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="3" y="3" width="12" height="12" rx="1.5" />
      <line x1="7" y1="3" x2="7" y2="15" />
    </svg>
  );
}

/** Explainability -- question (?). */
export function ExplainIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M6.5 6.5a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1.4.8-1.4 1.7v.4" />
      <circle cx="8.6" cy="13.5" r="0.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Compare -- opposed arrows (⇄). */
export function CompareIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M4 6.5h10M11.5 4l2.5 2.5-2.5 2.5" />
      <path d="M14 11.5H4M6.5 9 4 11.5 6.5 14" />
    </svg>
  );
}

/** Settings -- dot in ring (◍). */
export function SettingsIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="9" cy="9" r="6" />
      <circle cx="9" cy="9" r="2" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Sign out -- the → the prototype settled on (⏻ rendered as tofu). */
export function SignOutIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <line x1="3.5" y1="9" x2="14" y2="9" />
      <path d="M10.5 5.5 14 9l-3.5 3.5" />
    </svg>
  );
}

/**
 * Back -- chevron left. Not a rail item: it lives on the screen headers, but
 * it belongs to this family and is declared here so it inherits the same 18px
 * box, 1.4 stroke and round joins. An icon drawn to its own spec beside these
 * reads as borrowed from somewhere else.
 */
export function BackArrowIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M11 4 6 9l5 5" />
    </svg>
  );
}

/** Dark appearance -- crescent. */
export function MoonIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M14.8 10.6A6.6 6.6 0 0 1 7.4 3.2a6.6 6.6 0 1 0 7.4 7.4Z" />
    </svg>
  );
}

/** Light appearance -- sun with rays. */
export function SunIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="9" cy="9" r="3.4" />
      <path d="M9 1.6v1.7M9 14.7v1.7M16.4 9h-1.7M3.3 9H1.6M14.23 3.77l-1.2 1.2M4.97 13.03l-1.2 1.2M14.23 14.23l-1.2-1.2M4.97 4.97l-1.2-1.2" />
    </svg>
  );
}

/** Discard a draft -- waste bin. */
export function DiscardIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M3.5 5h11" />
      <path d="M7 5V3.5h4V5" />
      <path d="M5 5l.7 9.1a.9.9 0 0 0 .9.9h4.8a.9.9 0 0 0 .9-.9L13 5" />
    </svg>
  );
}

/** Copy to clipboard -- two offset sheets. */
export function CopyIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="6.5" y="6.5" width="8.5" height="8.5" rx="1.5" />
      <path d="M11.5 6.5V4.5A1.5 1.5 0 0 0 10 3H4.5A1.5 1.5 0 0 0 3 4.5V10a1.5 1.5 0 0 0 1.5 1.5h2" />
    </svg>
  );
}

/** Confirmation tick -- pairs with CopyIcon for the "copied" state. */
export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M3.5 9.5 7 13l7.5-8" />
    </svg>
  );
}
