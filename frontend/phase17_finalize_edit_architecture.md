## Phase 17 — Report Finalize & Edit: Architecture (PROPOSED, NOT YET FROZEN)

**Status: draft, pending user review.** Do not implement until this
section is explicitly frozen, same discipline as Phase 13.

### Why this phase exists

Phase 13a's Step 6 called for an ownership check on `ReportGenerationService`'s
finalize/edit/regenerate actions. None existed anywhere in the codebase, so
the check was deferred and the gate test's 403 assertion was dropped — a
scope adaptation, confirmed with the user and documented, not silently
patched around. That gap has been named explicitly at the end of every
phase since (13a, 15, 16) as still open. This phase closes it: it builds
the actual write path Phase 13a's ownership model was designed for, and
wires the ownership check onto it for real.

It is also the last piece blocking design_specification.md's core claim —
"nothing is final until a human signs it" — from being a real, enforced
property rather than one that happens to hold because nothing can be
finalized at all yet.

### Decisions frozen (pending this section's approval)

1. **Amended after Step 1's real evidence: reuse the existing
   `ReportStatus` enum, not a new 2-value type.** The original draft of
   this decision proposed inventing `AI_DRAFT | FINAL` from scratch to
   avoid the design spec's unverifiable "Under Review" dwell-timer. Step
   1's confirmation showed `ReportStatus` already exists in this
   codebase with all four values (`AI_DRAFT`, `UNDER_REVIEW`,
   `DOCTOR_EDITED`, `FINAL`) — inventing a competing type would repeat
   the exact mistake Decision 2 already warned against for
   `ReportContent`. The corrected decision: **reuse the real enum, but
   only ever transition into three of its four values.**
   `AI_DRAFT → DOCTOR_EDITED → FINAL`, both transitions real, verifiable
   events (`DOCTOR_EDITED` set on the first successful `PATCH
   /reports/{id}`; `FINAL` set on `PATCH /reports/{id}/finalize`) — no
   less honest than a computed diff, since it's driven by an actual
   database write, not inferred after the fact. `UNDER_REVIEW` remains
   defined on the enum (removing it would be a breaking type change for
   no benefit) but **no code path in this phase ever transitions into
   it** — stated explicitly in `ReportGenerationService`'s docstring so
   it isn't mistaken for reachable dead code later. This also means
   `is_edited` as a separately computed property is unnecessary —
   `status == DOCTOR_EDITED` already carries that fact as a real,
   persisted workflow state, one source of truth instead of two.
   **Before writing the migration, confirm whether `reports.status`
   already exists as a real database column or whether `ReportStatus` is
   currently only a Python-level type with no persisted field** — these
   are different migrations (start using an existing column vs. add a
   new one), and also grep for any existing code that filters/queries by
   `ReportStatus` value, since wiring real transitions could affect
   behavior that currently silently assumes every row is `AI_DRAFT`.
2. **`final_content` is structured, not a plain string, with five named
   sections.** Reports already have real internal structure, and the
   editing UI must expose it as five independently editable sections —
   **Clinical History, Technique, Findings, Impression, Recommendations**
   — not one collapsed textarea. Collapsing it would also make every
   later feature that needs a specific field (section-level regeneration,
   bilingual translation, PDF export, the §10.8 findings/impression
   validation itself) work against unstructured text instead of the real
   shape. **Before writing the migration or the endpoint, confirm the
   exact structure `ReportGenerationService` already returns** (its real
   field names — this document's five-section list is the target shape,
   not proof that all five already exist server-side; if `technique` in
   particular isn't currently a distinct field, say so before inventing
   one) and reuse that type for both `ai_draft_content` and
   `final_content` rather than inventing a parallel shape. If a
   `ReportContent`-style model already exists, `PATCH /reports/{id}`
   accepts and returns it directly.
3. **The AI draft is preserved immutably**, which is also what makes
   "Restore AI Draft" possible without a new endpoint (Decision 7). On
   generation, the structured output is stored once as `ai_draft_content`
   and never overwritten. `final_content` starts as a deep copy and is
   the only field `PATCH /reports/{id}` ever touches. This is what makes
   edit-distance evaluation possible later without inventing a second
   snapshot table — and with structured content, that evaluation can
   eventually be per-field, not just whole-document.
4. **Ownership check lands where Phase 13a specified it, on the actual
   endpoints it now has to attach to:** `PATCH /reports/{id}` (edit) and
   `PATCH /reports/{id}/finalize`. Both derive ownership via
   `report.session_id → retrieval_sessions.doctor_id`, same derivation
   Phase 15 already uses for read-side ownership chips — no new lookup
   path invented.
5. **Finalize requires non-empty `findings` and `impression`** as real
   fields on the structured content — no parsing or heuristic needed now
   that Decision 2 guarantees a structured shape. Recommendation/clinical-
   history/technique stay non-blocking, since nothing currently computes
   "warning severity" as a first-class concept and inventing one for
   fields that don't block anyway isn't worth the scope.
6. **Finalize goes through a Preview screen, not a bare confirmation
   dialog.** Workflow: `Edit → Preview → Confirm Finalize`. Clicking
   "Finalize" does not immediately open a modal — it opens a full
   read-only rendering of the current `final_content` in the same
   hospital-style document format a finished report is displayed in
   elsewhere in this system (**confirm whether that read-only rendering
   already exists — e.g. the view Phase 15's read-only banner uses for
   another doctor's finalized report — and reuse it rather than building
   a parallel renderer**). The Preview screen itself carries the
   disclosure copy Decision 6 originally specified for a dialog
   ("finalizing makes this report permanently read-only") and its own
   explicit "Confirm & Finalize" action — this **replaces** the separate
   modal-on-top-of-a-preview pattern, one deliberate gate instead of two
   stacked ones. Still a **frontend interaction gate, not a new backend
   state** — same reasoning as before: it cannot be mistaken for a third
   `ReportStatus` value and does not reintroduce the unverifiable-
   dwell-timer problem Decision 1 rejected. A doctor who skims the
   Preview and finalizes anyway is recorded identically to one who read
   every word; this is a workflow nudge, not a provable attention check,
   and the thesis should describe it as such.
7. **"Restore AI Draft" is a frontend-only action, not a new endpoint.**
   Because `ai_draft_content` is already returned on `ReportDetailResponse`
   (Decision 3) and never mutates, "restore" means repopulating the
   five edit fields from `ai_draft_content` and leaving the doctor to
   explicitly save via the existing `PATCH /reports/{id}` — the same
   write path as any other edit, not a special-cased revert. This is
   available any time before finalize (never after — a finalized report
   is immutable per Decision 9, so there is nothing to restore into).
   Shows a lightweight confirm ("Discard your edits and restore the AI
   draft?") — real, since it's destructive to unsaved work, but distinct
   from and less heavy than the Preview/Finalize flow in Decision 6,
   since restoring is reversible (the doctor can just edit again) and
   finalizing is not.
8. **Section-level edit visibility is in scope; a detailed diff view is
   not — a boundary worth stating precisely.** This is independent of
   `status` (Decision 1, whole-report workflow state): each of the five
   editable sections additionally shows a lightweight "Edited" indicator
   when its *current* value differs from `ai_draft_content`'s value for
   that same section — a live per-field comparison, recomputed on read,
   not stored. `status == DOCTOR_EDITED` answers "has this report ever
   been touched"; the per-section indicator answers "does this specific
   section currently differ from the draft" — the two can disagree (e.g.
   after a partial Restore, or if a doctor edits a section back to its
   original wording, `status` stays `DOCTOR_EDITED` but that section's
   indicator clears). A doctor can toggle any single section between its
   AI-draft value and current value to compare, without a permanent
   side-by-side layout. Word-level diffing, percentage-edited scoring,
   and any highlighted-change rendering remain Phase 18 scope
   (design_specification.md §10.6) — this phase proves *which* sections
   currently differ, not *how much* or *what* changed within one.
9. **Finalized reports are immutable in this phase, with report
   versioning/corrections named explicitly as Future Work, not silently
   absent.** Real clinical systems support corrected reports after
   finalization; building that now would require a real versioning model
   (superseding relationships, a "corrected" status, an audit trail of
   which version is authoritative) that has never been discussed or
   scoped. Locking a finalized report permanently is the honest Phase 17
   behavior — the alternative, silently treating "immutable forever" as
   if it were the intended long-term design, would misrepresent a scope
   boundary as a considered clinical-workflow decision. See "Future
   Work," below.
10. **No section-level regeneration, no "Accept into report" from
    Comparison, no word-level diff UI in this phase.** All three are
    real design-spec features but are additive on top of finalize/edit
    existing, not prerequisites for it. Explicitly deferred to Phase 18 —
    see below.
11. **Audit trail — a genuine, named exception to "no backend
    architecture changes," scoped as narrowly as the requirement allows.**
    "Do not change backend architecture" (this phase's own scope
    instruction) and "record every edit, never overwrite history
    silently" cannot both be satisfied by adding columns alone — an
    append-only history is a new table, not a field. Read narrowly: the
    "don't change" instruction protects the five things it names
    explicitly (ownership model, permissions, `ReportStatus`, AI-draft
    preservation, finalize rules) — none of which this touches — not a
    blanket ban on any new table. Two different shapes for two different
    kinds of event, not one audit mechanism forced onto both:
    - **Finalize happens at most once per report** (the 409-when-already-
      final guard makes a second finalize impossible) — so `finalized_by`
      (new) and `finalized_at` (already decided) are safe as plain
      columns directly on `reports`. There is no "silent overwrite" risk
      here because there is no second write to overwrite with.
    - **Edits can happen arbitrarily many times** — a single
      `edited_by`/`edited_at` pair on `reports` would silently overwrite
      prior edit history on every save, exactly what this requirement
      rules out. These get a new, append-only `report_audit_log` table
      instead: one row per successful `PATCH /reports/{id}`, `INSERT`
      only, no `UPDATE`, no `DELETE`, ever.
12. **Unsaved-changes warning is frontend-only, no backend involvement.**
    Standard `beforeunload`/route-change guard, fires when any of the
    five editable fields differ from what was last successfully saved
    (not from `ai_draft_content` — from the last save, so a doctor who
    saves and then navigates away isn't warned about their own saved
    work). No new state, no new endpoint.

### Entities (modified)

```python
# Report — rename, not a new column: ai_content already IS the immutable
# AI draft (nothing updates it post-insert). Renaming it to
# ai_draft_content names it correctly rather than duplicating it.
ai_draft_content: ReportContent   # renamed from ai_content, unchanged semantics
final_content: ReportContent      # NEW column, mutable via PATCH, starts as a deep copy of ai_draft_content
status: ReportStatus              # reuses the real, existing enum -- see Decision 1
finalized_at: str | None          # NEW column
finalized_by: str | None          # NEW column -- doctor_id, denormalized (Decision 11);
                                   # will always equal session.doctor_id under the current
                                   # ownership model, kept explicit so the report's own audit
                                   # trail is self-contained without a join
```

```python
# NEW table -- append-only, Decision 11. INSERT only. No UPDATE, no DELETE.
class ReportAuditLog:
    id: str
    report_id: str
    doctor_id: str
    action: Literal["EDITED"]     # only edits are logged here; FINALIZED
                                   # lives on `reports.finalized_by/at` directly
                                   # per Decision 11's "happens once" reasoning
    at: str
```

```python
# CONFIRMED via real runtime introspection + a real persisted report
# (Step 1 evidence) -- this is the actual shape, not a guess.
class ReportContent:
    examination: str
    clinical_history: str
    technique: str
    findings: str
    impression: str
    recommendation: str
    disclaimer: str
```

**Editable scope is 5 of these 7 fields**: `clinical_history`, `technique`,
`findings`, `impression`, `recommendation` — matching the five sections
named explicitly in the doctor-workflow requirement. `examination` and
`disclaimer` stay AI-set and are never accepted by the edit endpoint:
`examination` is exam-type metadata (e.g. "Chest X-ray"), not free-text
clinical narrative that should vary radiologist-to-radiologist for the
same study; `disclaimer` is presumed to be a fixed compliance/AI-disclosure
statement, and allowing a doctor to edit or remove it would defeat its
purpose. The `PATCH /reports/{id}` request schema (`ReportUpdateRequest`,
below) is therefore a **separate, narrower 5-field schema**, not the full
7-field `ReportContent` with two fields silently ignored — silently
discarding fields a client sent risks a caller believing a value took
effect when it didn't. Both `examination` and `disclaimer` remain part of
the stored `ReportContent` and render read-only in the document view.

`ReportStatus == DOCTOR_EDITED` is the single source of truth for "has
this report been touched since generation" — no separate `is_edited`
column or computed property (Decision 1). No entity shape change to
`Doctor`, `Patient`, `Comparison`, or `Explanation`.

### Endpoints (new)

```
PATCH /reports/{id}
  body: ReportUpdateRequest {
    clinical_history, technique, findings, impression, recommendation
    -- all optional/partial if the real schema supports partial update,
    confirm per Step 1's findings; examination and disclaimer are not
    accepted fields on this request at all
  }
  Reused for both ordinary section edits and for committing a
  "Restore AI Draft" action (Decision 7) -- the frontend populates the
  body from ai_draft_content's five editable fields and calls the same
  endpoint, no separate restore route exists.
  -> 200 updated ReportDetailResponse
  -> sets status=DOCTOR_EDITED if currently AI_DRAFT (first edit); stays
     DOCTOR_EDITED on subsequent edits, including one that reverts
     content back to matching ai_draft_content -- this is a workflow
     record ("this report was touched"), not a live content diff
  -> INSERTs one ReportAuditLog row (action=EDITED, doctor_id, at=now())
     in the same transaction as the content update -- both succeed or
     both fail, never a content change with no matching log row
  -> 403 if caller is not the owning doctor (session.doctor_id)
  -> 409 if report.status == "FINAL"  -- a finalized report is immutable

PATCH /reports/{id}/finalize
  -> valid from AI_DRAFT (doctor accepts the draft as-is, no edits made)
     or DOCTOR_EDITED -- both transition to FINAL
  -> 200 { status: "FINAL", finalized_at, finalized_by }
  -> sets finalized_by=current_doctor.id, finalized_at=now() directly on
     the report row (Decision 11 -- no log-table entry, finalize cannot
     recur so there's nothing to append-log)
  -> 403 if caller is not the owning doctor
  -> 422 if findings or impression is empty on final_content
  -> 409 if already FINAL
```

`ReportDetailResponse` gains `ai_draft_content`, `status`, `finalized_at`
— additive only, same pattern as Phase 15's `doctor_id` addition. No new
endpoint for restore, per Decision 7. No separate `is_edited` field —
the client reads `status` directly.

### Frontend visual treatment

Not a new design decision — a pointer to reuse what Phase 14 already
built rather than invent generic form UI. design_specification.md §8.10
(Radiologist Workspace, built in Phase 14) already specifies "Report as
document, not cards. Continuous paper, hairline section rules... Editing
affordances appear on hover" and the lightbox/lightbox-adjacent visual
language this project has used consistently since Phase 14's tokenized
pass. The five-section editor in this phase should read as that same
continuous clinical document — section headers as hairline-divided
headings, each section's content editable in place on hover/focus, not
as a form with five labeled `<textarea>` boxes stacked in visible input
chrome. The status chip (`AI Draft`/`Final`), the per-section "Edited"
indicator (Decision 8), and the Restore/Finalize actions belong in the
same context bar or finalize-bar treatment §8.10 already defines — no
new chrome pattern needed, this is that screen's edit mode, not a
different screen.

Two specific requirements from this round, both consistent with what's
already built rather than new visual language: the per-section "Edited"
indicator (Decision 8) stays **subtle** — a small dot or label-color
shift, not a badge, banner, or colored border around the whole section;
this project's design tokens already reserve strong color/border
treatment for real semantic states (§P2 of the broader design system),
and an edit indicator is informational, not a warning. And the editor
must be **keyboard-operable**: Tab moves between sections in document
order, Enter/Escape commit or cancel an in-progress section edit — the
same keyboard-first posture design_specification.md §9 already commits
to for the rest of the Workspace, not a new pattern invented for this
screen alone.

### Ownership check (the actual Step 6 Phase 13a deferred)

```
Doctor B calls PATCH /reports/{id}/finalize
  -> get_current_doctor resolves B
  -> ReportGenerationService.finalize(report_id, doctor_id=B)
       -> load report -> join to session.doctor_id
       -> if session.doctor_id != B: raise ForbiddenError (403)
       -> if not report.final_content.findings or not .impression: raise ValidationError (422)
       -> if report.status == "FINAL": raise ConflictError (409)
       -> else: set status=FINAL, finalized_at=now(), finalized_by=B
```

### Step breakdown

1. ✅ **Done** — `ReportGenerationService`'s real output shape confirmed
   via runtime introspection and a real persisted report: 7 fields
   (`examination`, `clinical_history`, `technique`, `findings`,
   `impression`, `recommendation`, `disclaimer`), 5 of them editable
   (Decision 2 amendment). `ReportStatus` confirmed to already exist as
   a 4-value enum (Decision 1 amendment).
1b. **Before the migration:** confirm whether `reports.status` already
   exists as a real DB column or is currently only a Python-level type
   with no persisted field — determines whether this is "start using an
   existing column" or "add a new one." Grep for any existing code that
   filters or queries by `ReportStatus` value before wiring real
   transitions, since behavior that currently assumes every row is
   `AI_DRAFT` could be affected once `DOCTOR_EDITED`/`FINAL` become real.
2. Migration: rename `ai_content` → `ai_draft_content` (`op.alter_column`,
   not a new column); add `final_content` (same structured type, JSON
   column if needed), `finalized_at` (nullable), `finalized_by` (nullable
   FK to `doctors.id`); add `status` only if 1b determines it doesn't
   already exist as a persisted column, otherwise no schema change
   needed for it. New table `report_audit_log` (`id`, `report_id` FK,
   `doctor_id` FK, `action`, `at`) — plain `create_table`, no batch mode
   needed, same reasoning as Phase 15's brand-new tables. Backfill:
   `final_content = ai_draft_content` for every existing row, `status =
   AI_DRAFT` if newly added, no backfill needed for `report_audit_log`
   (it starts empty — there is no real history for reports that predate
   this phase, and inventing synthetic log rows for them would be worse
   than having no history at all).
3. `ReportGenerationService`: set `ai_draft_content` at generation time
   (currently wherever the generated content is first persisted).
4. `PATCH /reports/{id}` + ownership check + the 409-when-final guard +
   the `ReportAuditLog` insert, same transaction as the content update.
5. `PATCH /reports/{id}/finalize` + ownership check + the two-field
   validation (`findings`, `impression` non-empty on the structured
   content) + 409-when-already-final guard + `finalized_by`/`finalized_at`
   set directly on the row.
6. `ReportDetailResponse` gains the new fields (`ai_draft_content`,
   `status`, `finalized_at`, `finalized_by`); verify Phase 15's
   `doctor_id` field still renders correctly alongside them (no
   regression to that response shape). New `GET /reports/{id}/audit-log`
   (or embedded on the detail response, whichever this codebase's
   existing convention favors — check how Phase 15 exposed a related-but-
   separate list, e.g. patient history, before choosing) returning the
   `report_audit_log` rows for that report, doctor names resolved via
   the existing `GET /doctors/{doctor_id}` pattern from Phase 15, not a
   new name-resolution path.
7. Frontend: report view gains five independently editable sections
   (Clinical History, Technique, Findings, Impression, Recommendations —
   owner only; non-owner still sees the Phase 15 read-only banner, now
   actually gating something real for the first time), rendered per
   "Frontend visual treatment" above, not as a generic form. Each section
   shows a lightweight "Edited" indicator (Decision 8) when its current
   value differs from the AI draft's value for that section. A "Restore
   AI Draft" action (Decision 7) repopulates all five fields from
   `ai_draft_content` after a lightweight confirm, leaving the doctor to
   explicitly save. A "Finalize" action opens the **Preview screen**
   (Decision 6) — the real hospital-style read-only rendering of
   `final_content`, the "becomes permanently read-only" disclosure, and
   the actual "Confirm & Finalize" action — disabled entirely if
   findings or impression is empty, if not owner, or if already final.
   An `AI Draft`/`Final` status chip is driven by the real field
   throughout. A `beforeunload`/route-change guard (Decision 12) warns
   on any unsaved edit to any of the five fields.
8. Integration test, extending Phase 13a's existing two-doctor fixture:
   doctor A generates a report (status=AI_DRAFT) → doctor B attempts
   `PATCH .../finalize` → real 403 → doctor A edits `final_content` via
   `PATCH /reports/{id}` → real `status` transitions to `DOCTOR_EDITED`,
   a real `ReportAuditLog` row exists with the right `doctor_id`/`action`
   → doctor A edits a second time → a second, distinct log row exists
   (proving the first wasn't overwritten) → doctor A finalizes → real
   200, status=FINAL, `finalized_by`/`finalized_at` both set correctly →
   doctor A attempts a second edit → real 409 → doctor B still reads it
   fine (200, universal read intact). Also: doctor A finalizes a *fresh,
   unedited* AI_DRAFT report directly (no PATCH first) → real 200,
   status=FINAL — confirms finalize doesn't require DOCTOR_EDITED as a
   precondition. The Preview screen and the unsaved-changes guard are
   frontend interactions, not asserted here — cover them in the frontend
   walkthrough (Step 7) instead.
9. **This is also the moment to add back the write-rejection case Phase
   13a's gate test explicitly deferred** — same test file, same fixture,
   closing the note left in that phase's docstring.

### Risks

- **Whether `reports.status` already exists as a persisted column is
  still unconfirmed** (Step 1b) — determines the migration's actual
  shape. Do not assume either way before checking.
- **Existing code may already read/filter by `ReportStatus`** in ways
  that silently assumed every row is `AI_DRAFT` — grepping for this
  before wiring real transitions (Step 1b) is what prevents a Phase
  15/16-style surprise here instead of after.
- **This unblocks the correction-beat demo but does not build it** — the
  hallucination-heuristic validation warning referenced in earlier design
  discussion is a separate, not-yet-scoped capability. Worth naming so it
  isn't assumed to arrive for free with this phase.
- **Locking `examination`/`disclaimer` as non-editable is a judgment
  call, not something the real data proved.** The evidence confirmed
  these fields exist and are populated; it didn't confirm they *should*
  stay AI-only. If this reasoning turns out wrong once real doctors are
  looking at real reports, loosening it later is a small, additive
  schema-permission change, not a redesign.
- **The `report_audit_log` insert must share a transaction with its
  triggering `PATCH`** — if the framework/ORM's existing pattern for
  multi-write operations elsewhere in this codebase differs from a
  simple same-transaction insert, follow that existing pattern rather
  than inventing a new one. A content update that succeeds while its
  log row silently fails to write is worse than not having a log at all
  — it would look complete and not be.
- **"Keep backend architecture exactly the same" and "audit trail,
  don't overwrite history" are in real tension**, resolved here by
  reading the former as protecting the five explicitly-named items
  (Decision 11) rather than forbidding any new table. If that reading
  is wrong, the fix is small — drop `report_audit_log`, keep
  `finalized_by`/`finalized_at` (which need no new table) — not a
  redesign of anything else in this document.
- **The Preview screen is a UX step, not an enforced attention check**
  — same honesty as the two-state machine (Decision 1) and the original
  confirmation dialog it replaced. A doctor can open Preview and finalize
  within a second without reading; nothing here proves review happened,
  only that the step existed. Do not describe it in the thesis as proof
  the doctor read the report.
- **The read-only hospital-style rendering this reuses may not exist
  yet in the exact form assumed** — Decision 6 says to check for and
  reuse whatever component already renders a finalized/read-only report
  elsewhere (e.g. Phase 15's cross-doctor read-only view). If nothing
  like that exists yet, building a proper document-format renderer for
  the first time is more work than reusing one, and should be flagged
  as a larger Step 7 than this document assumes.

### Explicitly deferred to Phase 18

- Section-level regeneration (`POST /reports/{id}/regenerate-section`)
- "Accept into report" from the Comparison Workspace
- Doctor-edit-tracking diff UI (design_specification.md §10.6's
  "14% of the AI draft was edited" — computable per-field from
  `ai_draft_content` vs `final_content` once this phase lands, and
  actually easier now that both are structured rather than opaque text,
  but the diff-rendering UI itself is new scope)
- The hallucination-heuristic validation warning (needs its own
  architecture — what triggers it, where it reads from)

### Future Work (thesis roadmap, not a near-term phase)

- **Report versioning / corrected reports.** Phase 17 makes `FINAL`
  permanent — no endpoint anywhere ever un-finalizes or supersedes a
  report. Real hospital systems support corrected reports after
  finalization (a new version referencing the one it corrects, with the
  original preserved for audit rather than overwritten). This needs its
  own architecture — a versioning relationship, a "corrected" status
  distinct from a fresh `AI_DRAFT`, and a rule for which version a reader
  sees by default — and should be named in the thesis explicitly as a
  known limitation of the current design, not discovered as a gap by an
  examiner asking "what happens when a doctor makes a mistake after
  signing?"

---

**Once frozen, implementation follows this project's standing
discipline: step-by-step, real execution output at each gate, confirmed
before proceeding, `development_log.md` updated with the same
four-part structure as every prior phase.**