# P0 — Design System

Implements `design_specification.md` §6 (design system), §7 (primitives), §13 (P0 gate).
**Nothing in P1–P8 should be built until `npm run check:design` passes in CI.**

## Why this phase exists at all

V1 shipped a *documented* design system that nothing consumed. Six tokens were
declared and never wired up; every banner invented its own border colour by hand
(§15.2). The mockups looked consistent because 23 screens were hand-tuned — not
because a system produced them. **Hand-tuning does not survive three developers.**

P0 makes §6 executable. `scripts/check-design-tokens.mjs` is the difference
between a specification and a suggestion.

## Install

```bash
cp -r src/styles/tokens.css        <repo>/frontend/src/styles/
cp -r src/lib/*                    <repo>/frontend/src/lib/
cp -r src/components/ui/*          <repo>/frontend/src/components/ui/
cp -r src/app/dev                  <repo>/frontend/src/app/
cp    tailwind.config.ts           <repo>/frontend/
cp    scripts/check-design-tokens.mjs <repo>/frontend/scripts/

npm i clsx tailwind-merge
```

`package.json`:
```json
{ "scripts": { "check:design": "node scripts/check-design-tokens.mjs" } }
```

Root layout:
```tsx
import "@/styles/tokens.css";
import { fontVars } from "@/lib/fonts";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVars}>
      <body className="bg-paper text-ink font-sans text-body antialiased">{children}</body>
    </html>
  );
}
```

`tsconfig.json` needs `"@/*": ["./src/*"]`.

## The gate

```
$ npm run check:design

✗ src/components/ui/report.tsx:42  [hex-literal]  #F5D9A8
  Colour must come from a token. See §6.2.
✗ src/components/ui/rail.tsx:18    [forbidden-word-confidence]  Confidence
  The measure is agreement among retrieved cases, not calibrated confidence. See §10.3.

2 violation(s). P0 gate FAILED.
```

Seven rules, each citing the clause it enforces:

| Rule | Catches | Clause |
|---|---|---|
| `hex-literal` | any hex outside `tokens.css` / `.svg` | §6.2 |
| `raw-padding` | `p-[13px]`, `padding:11px`, `padding: "13px"` | §6.4 |
| `dead-shadow-token` | `--shadow-popover` / `--shadow-modal` | §6.5 |
| `below-type-floor` | anything under 11px | §6.3, §9 |
| `forbidden-word-confidence` | the word in shipped strings | §10.3 |
| `outline-none` | suppressed focus | §9 |
| `tailwind-default-palette` | `bg-blue-500` and friends | §6.2 |

Comment lines are exempt from `forbidden-word-confidence` — a gate that forbids
documenting its own rationale is how rationale gets lost.

**Escape hatch:** `// design-token-allow` on the line. Use it approximately never;
each use should be defensible in a review.

**Known limitation:** computed values (`padding: n + "px"`) are invisible to a
static scanner. This is a lint, not a proof.

## Verified

```
scanned 11 files in src/
0 violations. P0 gate passed.
```

A probe file exercising all seven rules produced 8 violations across 4 lines and
exited 1; removing it returned exit 0. The gate bites.

## What is here

```
src/styles/tokens.css              58 tokens. The only file that may contain hex.
tailwind.config.ts                 Names the tokens. Restates no value.
                                   `colors` is REPLACED, not extended — otherwise
                                   Tailwind reintroduces ~250 non-semantic colours.
src/lib/fonts.ts                   Plex Sans + Plex Mono + Noto Sans Bengali
src/lib/cn.ts                      clsx + tailwind-merge
src/components/ui/
  button.tsx                       4 variants × 3 sizes × loading/disabled/block
  card.tsx                         Elevation 0 — cards never lift
  chip.tsx                         StatusChip · OwnershipChip · ServiceChip · Tag
  agreement-badge.tsx              §10.3. Never a bare percentage
  similarity-bar.tsx               Steel, always
  skeleton.tsx                     Static. No shimmer
  empty-state.tsx                  Always carries the action that resolves it
src/app/dev/kitchen-sink/page.tsx  Every primitive, every state
scripts/check-design-tokens.mjs    The gate
```

Exclude `/dev` from the production build.

## Not in P0 — deliberately

`EvidenceCard`, `CitationMarker`, `DiffView`, `Lightbox`, `ReportSection`,
`Drawer`, `Modal`, `Toast`, `ValidationList`. Each is coupled to a screen's data
shape; building them now would mean guessing at the API contract and rebuilding
them in P4/P6. The primitives above are the ones with no such coupling.

## Next: P1

B1 (auth), B2 (ownership in the **repository layer**), B6 (health), **B7 (masked
image persistence)**.

**P1's gate is a security gate, not a UI gate:** two seeded doctors must see only
their own reports. B2 belongs in the repository layer as a mandatory filter — a
service that forgets the filter is a cross-tenant leak, and nobody notices a
missing `WHERE` in review.

Before P1 ships, seed **four** doctors with cross-owned studies (§12.1). Without
it the ownership model, the read-only report, and the access log never render.
