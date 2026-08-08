repo: suborhan7/RadAssist-RAG
branch: main
path: frontend/src

## Last sync
date: 2026-07-31T11:12:00Z

### Updated in this project
- Read the real design system (tokens.css, tailwind.config.ts, fonts.ts) and rebuilt every route on it.
- New "RadAssist Redesign.dc.html" — all 15 screens/states, steel #0F5C87 palette, IBM Plex + Noto Sans Bengali.
- Added the citation/provenance interaction the repo's spec calls its signature but never built.
- Added two screens the repo lacks as designed surfaces: doctor registration with signature preview, patient registration with duplicate detection.

## Screen map
| Screen (in RadAssist Redesign.dc.html) | Built from |
|---|---|
| Landing `/` | frontend/src/app/page.tsx |
| Sign in `/login` | frontend/src/app/login/page.tsx, components/ui/chip.tsx |
| Register `/register` | frontend/src/app/register/page.tsx, app/settings/page.tsx |
| Queue `/dashboard` | frontend/src/app/dashboard/page.tsx, lib/report-status.ts |
| Find patient `/patients/search` | frontend/src/app/patients/search/page.tsx |
| Register patient `/patients/new` | frontend/src/app/patients/new/page.tsx |
| Patient `/patients/[patientId]` | frontend/src/app/patients/[patientId]/page.tsx, ui/owner-chip.tsx |
| New examination `/patients/[patientId]/upload` | .../upload/page.tsx, workflow/StepProgress.tsx, ui/phi-reveal-slider.tsx |
| Workspace `/reports/[reportId]` | .../[reportId]/page.tsx, ui/similarity-bar.tsx, ui/agreement-badge.tsx |
| Candidate / diff / sign states | components/report/editable-report-section.tsx, report-diff-view.tsx, finalize-preview.tsx, lib/report-diff.ts |
| Explainability `/reports/[reportId]/explain` | .../explain/page.tsx |
| Compare `/reports/[reportId]/compare` | .../compare/page.tsx |
| Settings `/settings` | frontend/src/app/settings/page.tsx |
| Tokens / type / radii (all screens) | frontend/src/styles/tokens.css, frontend/tailwind.config.ts, frontend/src/lib/fonts.ts |

## Notes
- Earlier files in this project ("RadAssist Design Plan", "RadAssist Workspace") predate the repo link and use a different palette; the redesign supersedes them.
- Film areas are `<image-slot>` drop targets — no dataset images are redistributed.
