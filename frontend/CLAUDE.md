# CLAUDE.md — RadAssist-RAG Frontend Build Instructions (v2)

**Read this entire file before writing any code.** This supersedes the earlier version of this file. The earlier version wrongly assumed `frontend/` didn't exist yet and told you to scaffold a fresh Next.js app — **that was wrong.** `frontend/` already exists: it's Phase 12's real, working, frozen implementation, wired to a real backend across 12 completed phases. You are **extending and visually refactoring it**, not building it from scratch.

## Where this file goes

Put this file at `frontend/CLAUDE.md`. The repo root has its own `CLAUDE.md` for `ml/`. Claude Code reads whichever is nearest to where you're working — do not merge or overwrite the root one. `frontend/` never imports from `ml/` or `shared/` directly, only through the backend's API.

## Required reading, in this order

1. **`docs/methodology/development_log.md`** — the authoritative record of what already exists. Read at minimum: Phase 11 (Patient entity, `PAT-000001` codes), Phase 12 (the real frontend architecture — folder structure, routes, the frozen workflow), and the new **Phase 13 section** (below) — authentication and ownership, frozen and ready to implement.
2. **`phase13_auth_architecture.md`** — frozen backend architecture for auth + doctor ownership. **Append this to `development_log.md` as the actual Phase 13 section once backend work begins**, matching this project's own logging discipline (architecture -> implementation -> validation -> "How to Write This in Your Thesis").
3. **`design_specification.md`** — the visual/interaction design system. Read §16 (Corrections) — the earlier draft of this document assumed an *invented* architecture (patient ID format `RA-{YYYY}-{NNNNNN}`, generic auth) that conflicted with what Phase 11/12 actually built. **Use this document for visual design only** (tokens, typography, spacing, component styling, copy like "Evidence agreement" and "Alternatives in retrieved evidence"). Where it describes data (patient ID format, entity names, ownership mechanics), **`phase13_auth_architecture.md` and `development_log.md` are correct and this document is not** — do not implement `RA-{YYYY}-{NNNNNN}`, keep `PAT-000001`.
4. **`radassist-v2-final.html`** — visual reference for exact layout/spacing/color. Still valid for appearance. Not valid as a data model reference.
5. **`p0-design-system/`** — already-implemented tokens, Tailwind config, and primitives. Drop these into the **existing** `frontend/src/`, do not scaffold a new project around them.

## Hard rules

- **Do not scaffold a new Next.js app.** `frontend/` exists. Work inside it.
- **Do not implement `RA-{YYYY}-{NNNNNN}` patient IDs.** The real format is `PAT-000001`, already built, already migrated. Reusing the invented format is pure churn with no benefit.
- **Do not touch `ml/`, `shared/`, or any Phase 4-11 backend file's *business logic*** without this file or `phase13_auth_architecture.md` explicitly saying so. Phase 13 adds `doctor_id` as an *additive* parameter to existing services — it does not change what they compute.
- **Never use the word "confidence" in UI copy** — the measure is "Evidence agreement" (§10.3 of the design spec). Enforced by the gate script.
- **Run `npm run check:design` before showing me any screen.** Fix violations; don't work around the gate.
- **Reuse `p0-design-system` primitives** before building new components.
- If a design-spec screen assumes something Phase 13 doesn't provide (e.g. an admin role — explicitly out of scope per `phase13_auth_architecture.md`'s "Explicitly not in this phase"), **skip it and tell me**, don't invent the missing piece.

## Build order

### Phase 13a — Backend: auth + ownership (do this first, it's a prerequisite)

Follow `phase13_auth_architecture.md` exactly — entities, interfaces, database migrations, folder structure, step breakdown, all specified there. This is backend work in `backend/`, not `frontend/`, but it blocks every ownership-dependent frontend screen below, so it comes first.

**Gate:** the integration test in that document's Step 8 passes — two doctors, shared patient, ownership enforced on write, read universal. Run it for real, show me the output.

### Phase 13b — Frontend: login + register

- `frontend/src/app/login/page.tsx`, `frontend/src/app/register/page.tsx` — new routes, per `phase13_auth_architecture.md`'s folder structure section.
- Visual treatment per design_specification.md §8.1 (Login screen) — the 46/54 split, lightbox side, service status strip. Adapt copy/fields to match Phase 13's real `Doctor` entity (email, password, full_name) — not the design spec's invented fields (BMDC number etc. — that's Settings·Profile, later, and only if you decide to build it).
- `lib/api-client.ts` — attach the JWT (httpOnly cookie, per Phase 13a) to every request.
- **Gate:** register a doctor through the real UI, log in, confirm the token round-trips to a protected endpoint.

### Phase 14 — Visual system pass (no auth dependency, can run in parallel with 13a/13b if you want)

Apply design_specification.md §6 (design system) to the **existing** Phase 12 pages — Dashboard, Patient Profile, Upload flow, Radiologist Workspace, Explainability, Comparison. This is styling and interaction, not new routes:

- Design tokens, typography, spacing, elevation (from `p0-design-system/`).
- "Evidence agreement" wording replacing any "confidence" language in the existing report/retrieval UI.
- "Alternatives in retrieved evidence" panel styling on the existing retrieval-evidence accordion (§10.5).
- **Comparison provenance split** (§8.12) — this maps directly onto Phase 11's real `ComparisonFacts` (deterministic) vs `narrative` (LLM) fields. Attribute them separately and visibly: "Computed by DeterministicComparator — deterministic, not generated" vs "Narrative generated by [model] from the diff above."
- PHI reveal slider on the upload flow (§8.7) — check what Phase 1's `phi_masking.py` actually persists before promising "original never stored" in the UI copy; confirm against `development_log.md`'s PHI Masking section, don't assume the design spec's claim is accurate for this backend.
- Lightbox aesthetic, citation markers, evidence rail on the Radiologist Workspace (§8.10).
- Explainability drawer styling (§8.11) — not a chat UI, per that section.

**Gate:** `npm run check:design` passes. Screens visually match `radassist-v2-final.html`.

### Phase 15 — Ownership UI (requires 13a + 13b complete)

- Ownership chips ("You" / doctor name) on sessions, reports, comparisons, explanations — per design_specification.md §7 (`OwnershipChip` component, already built in `p0-design-system`).
- Read-only banner + disabled edit controls when viewing a report you don't own (§8.13 — adapt copy, there's no access-log table in Phase 13's scope, so drop any "your access has been recorded" language unless you build that too).
- Dashboard: reflect real ownership — "your sessions" vs the shared registry, not the invented "38 of 142" style stat, use real counts from the API.

**Gate:** log in as two real registered doctors, confirm ownership renders correctly and read-only enforcement is visible, not just backend-enforced.

### Not in scope unless you tell me otherwise

Settings·Profile (BMDC field etc.), the standalone "Studies" registry page, access-log table/UI, admin role. These were in the earlier design spec but aren't part of Phase 13's frozen scope. Building them means writing a new mini-architecture first, same discipline as Phase 13 — don't improvise them mid-implementation.

## How to ask me for clarification

If `development_log.md`, `phase13_auth_architecture.md`, or `design_specification.md` disagree with each other on something not covered above, stop and ask — cite the specific sections in conflict. Don't guess and continue.

## Every response to me should include

1. Which phase and section(s) you implemented.
2. Result of `npm run check:design` (frontend work) or the relevant test suite (backend work).
3. Any visual differences vs `radassist-v2-final.html`, or any data-model assumption you had to resolve against `development_log.md`.