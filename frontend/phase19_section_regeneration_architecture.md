## Phase 19 — Section-Level Regeneration: Architecture (FROZEN)

**Status: frozen and implemented.** Originally drafted as "PROPOSED, NOT
YET FROZEN"; amended in place as real implementation findings landed
(Steps 1, 3, and 4 each surfaced something this draft didn't anticipate),
then frozen — see `docs/methodology/development_log.md`'s Phase 19 entry
for the full Implementation & Validation record and the COMPLETE banner.

### Why this phase, and what it actually is

Deferred explicitly since Phase 17 ("Section-level regeneration
(`POST /reports/{id}/regenerate-section`)... additive on top of
finalize/edit existing, not prerequisites for it"), and named in the
*original* design specification's component table before any of this
was built at all — `ReportSection`'s listed states were `view · edit ·
regenerating`, so a regenerating state was anticipated from the start,
just never implemented until now.

The core design question this phase has to answer isn't "how do we call
the LLM for one field" — it's **where regeneration sits relative to
Phase 17's edit/finalize machinery.** The answer proposed here: it
doesn't sit beside it, it sits *in front of* it. Regeneration produces a
candidate the doctor reviews and either discards or accepts; accepting
is not a new write path — it **is** Phase 17's existing
`PATCH /reports/{id}`, called with the accepted text as if the doctor
had typed it. This means no new status-transition logic, no new
ownership check, no new audit-log write path — all three are already
correct and tested from Phase 17, inherited for free rather than
re-implemented.

### Decisions frozen (pending this section's approval)

1. **Regeneration is two steps, not one atomic write: `POST
   /reports/{id}/regenerate-section` produces a candidate; nothing is
   persisted until the doctor explicitly accepts it through the
   existing `PATCH /reports/{id}`.** This mirrors Phase 17 Decision 7's
   "Restore AI Draft" precedent exactly (frontend populates a field,
   doctor explicitly saves via the existing endpoint, no dedicated
   commit route) and P5's standing principle ("the AI never gets the
   last word, structurally") — an auto-committing regenerate button
   could silently destroy a doctor's prior edits the instant it's
   clicked, which is a real risk this design removes by construction,
   not by convention.
2. **Only the 5 fields `EDITABLE_REPORT_FIELDS` already names** (the
   constant Phase 18 just consolidated) can be regenerated —
   `examination`/`disclaimer` stay AI-set-once, never regenerable, same
   reasoning as Phase 17 Decision 2. No new field-list invented; this
   phase is one more consumer of the existing constant. **Backend-side
   real finding (Step 4): no Python equivalent of `EDITABLE_REPORT_FIELDS`
   existed to reuse** — `ReportUpdateRequest` turned out to be 5
   separately-named Pydantic fields, not a list-shaped construct.
   Consolidated into `EditableReportField(str, Enum)` in
   `app/domain/entities.py`, matching `ReportStatus`'s existing idiom
   rather than introducing `Literal` as a second pattern for the same
   kind of thing. `RegenerateSectionRequest.field`, `PromptBuilder`'s
   `_SECTION_FIELD_LABELS` dict keys, and both service/interface
   signatures all reference this one type, with a test proving the
   dict's keys and the enum's members can't silently drift apart — the
   backend-side counterpart to the frontend consolidation this decision
   already required.
3. **`POST /reports/{id}/regenerate-section` requires ownership and
   blocks on `FINAL`, identically to `PATCH /reports/{id}`** — same
   `ForbiddenError` (403) / `ReportAlreadyFinalizedError` (409) types
   Phase 17 already defined, reused rather than duplicated. Regenerating
   a section is a form of editing; it gets edit's permission rules.
4. **Resolved via Step 1's real investigation — the finding was mixed,
   and scope is expanded narrowly in response.** Retrieved evidence,
   voted labels, and retrieval metadata are fully reconstructable from
   `RetrievedEvidence` rows and columns already on `ReportRecord`.
   `questionnaire_answers` and `clinical_notes`, however, were confirmed
   to arrive only as transient request-body fields, written nowhere,
   and permanently lost for any report generated before this
   persistence exists. `clinical_notes` is moot in current practice
   (hardcoded to `""` by the only real caller today), but
   `questionnaire_answers` has real, concrete teeth — genuinely
   non-empty whenever a doctor doesn't click Skip, which the evidence
   suggests is not rare. **Decision: persist both going forward** (see
   Entities, below) rather than accept a regeneration path that
   silently produces a systematically less-grounded candidate whenever
   questionnaire context existed for the original generation. The
   alternative — regenerate from retrieval-only context and trust the
   doctor's review to catch anything missing — was considered and
   rejected: it would make regeneration's typical output quality worse
   than original generation's by default, and "a human will review it"
   is not a justification this project accepts for skipping grounding
   fidelity anywhere else, so it shouldn't be accepted here either. This
   does not reopen or contradict Decision 4's original "hard gate"
   framing — it's exactly what that gate was for: the real finding
   changed the phase's shape, and that change is being made explicitly,
   not discovered halfway through implementation.
5. **No doctor-provided steering instruction (e.g. "make this more
   concise," "focus on the right lower lobe") in this phase.** Tempting,
   and named explicitly so it isn't quietly added mid-implementation —
   plain regeneration from the same original context only. A steering
   textbox is a real, separable feature for a later phase if wanted.
6. **The regeneration candidate is previewed via a diff against the
   current section content, reusing Phase 18's `computeReportDiff`/
   `ReportDiffView` machinery rather than building a second comparison
   UI.** A doctor should see exactly what accepting would change before
   accepting it — the same principle behind Phase 17's Preview-before-
   Finalize, applied here to a smaller, single-section decision. This is
   a genuine reuse opportunity Phase 18 created, not a new comparison
   component.
7. **Regeneration acceptance is intentionally modeled as a normal
   doctor edit — the audit log does not distinguish it from a hand-typed
   one, by design, not by oversight.** This is a direct, deliberate
   consequence of Decision 1: because accepting a regeneration goes
   through the exact same `PATCH /reports/{id}` as any other edit, the
   resulting `ReportAuditLog` row has `action = "EDITED"` regardless of
   which one happened, and that is the intended architecture, not a gap
   that was missed. Worth stating plainly anyway, because the practical
   consequence is real: if "how much of the final report is doctor-
   authored vs. AI-regenerated" ever becomes a genuine thesis evaluation
   question, this design cannot answer it as built — widening the audit
   log's `action` field (e.g. `EDITED` vs. `REGENERATED_AND_ACCEPTED`)
   would be a deliberate future change, not a bug fix. State this in the
   thesis as a documented boundary of the current audit trail.
8. **Regeneration is a real, potentially slow LLM call (Phase 17 showed
   ~5–7s for full generation; single-section should be faster but is
   unmeasured) and needs a real pending/loading state, not an instant
   response** — reuse whatever loading-state pattern the original
   generation flow already established rather than inventing a second
   one.
9. **Confirmed, not assumed — cross-tab/concurrent-edit behavior is
   plain last-write-wins, and this phase introduces no new risk beyond
   what already exists.** `ReportEditService.update_content()` was read
   directly: `_load_report_and_owner()` runs a fresh, per-request DB
   query at call time (server-side truth, never client-supplied — (a)
   confirmed), and `record.final_content = {**record.final_content,
   **updates}` has no ETag, version column, `SELECT ... FOR UPDATE`, or
   optimistic-locking compare — plain read-merge-write ((b) confirmed).
   There is a real, pre-existing lost-update race (two overlapping
   PATCHes to different fields, where the second's merge reads before
   the first commits, silently clobbering it) — this is not new, not
   introduced by this phase, and not fixed by this phase either.
   **Regeneration acceptance inherits `PATCH`'s existing last-write-wins
   behavior exactly, because it *is* a call to `PATCH`** — stated as
   confirmed fact now, not an assumed inheritance.
10. **Persistence detail for Decision 4's resolution:** `NULL` on
    backfill for both new columns, never an empty string/dict — `NULL`
    must mean "predates this column, unknown," staying distinct from a
    genuinely empty value meaning "doctor clicked Skip; confirmed no
    answers." Conflating the two would permanently lose the ability to
    tell a pre-existing report apart from a report where the doctor
    deliberately provided nothing. Regenerating a section on a report
    where `questionnaire_answers IS NULL` still works — it is not
    blocked — but the UI must show an explicit notice that the
    candidate may not reflect the original questionnaire context,
    rather than silently producing a lower-fidelity result with no
    indication anything is different from a normal regeneration.
    **The check is `questionnaire_answers IS NULL AND clinical_notes IS
    NULL` — and Step 4 found this equivalence was not actually
    guaranteed until it was made so.** `generate()` normalized
    `questionnaire_answers` (`or {}`) but had no matching normalization
    for `clinical_notes`, so the two fields could only be relied upon to
    stay NULL-together because of the API layer's Pydantic typing, not
    because of the service's own logic — a real gap if `generate()` were
    ever called directly, bypassing that boundary. Fixed by adding
    `clinical_notes = clinical_notes or ""` alongside the existing line,
    and proved (not just reasoned about) with a test that calls
    `generate()` with `clinical_notes=None` explicitly, bypassing the
    type hint. The asymmetric-state test in `report_edit_service.py`
    stays regardless — documenting `context_incomplete`'s behavior for
    that state even though it is now provably unreachable via
    `generate()`, since pre-fix data or a direct DB edit could still
    produce it.

### Entities (modified — new as of Decision 4's resolution)

```python
# ReportRecord — additive only, same table as the already-reconstructable
# retrieval_metadata columns (embedding_model/embedding_version/
# collection_name), colocated for consistency per Claude Code's own
# finding that this is the established pattern for per-generation
# metadata on this entity.
questionnaire_answers: dict | None   # NULL = predates this column, unknown
                                       # {} or populated = confirmed value at generation time
clinical_notes: str | None            # same NULL-vs-empty distinction (Decision 10)
```

No new table — this is two nullable columns on an existing entity, not
a new persistence layer. Backfill for every pre-existing row: `NULL` for
both, never an empty value (Decision 10).

### Endpoints (new)

```
POST /reports/{id}/regenerate-section
  body: { field: EditableReportField }   -- Step 4's real type, not a
     Literal; matches ReportStatus's existing enum idiom rather than
     introducing a second pattern for the same kind of thing
  -> 200 { field: EditableReportField, candidate: string,
           context_incomplete: bool }
     -- "candidate," not "content" -- this codebase already overloads
     -- "content" heavily (ReportContent, final_content,
     -- ai_draft_content); naming this response field distinctly makes
     -- "not yet persisted" part of the name itself, not just a comment.
     -- context_incomplete is Decision 10's real, implemented flag --
     -- true when questionnaire_answers and clinical_notes were both
     -- NULL on this report (pre-migration/unknown), driving the
     -- frontend's incomplete-context warning. This field was added
     -- during Step 4 as a direct, necessary consequence of Decision 4's
     -- scope expansion -- a confirmed deviation from this document's
     -- originally-drafted two-field response, not a silent one.
     -- Nothing about this call is written to final_content. Not logged.
     -- Nothing about this call is persisted anywhere.
  -> 403 if caller is not the owning doctor
  -> 409 if report.status == "FINAL"
  -> real LLM-failure handling, matching whatever pattern
     ReportGenerationService's original call already uses -- don't
     invent a second error-handling convention for what is, from
     Ollama's perspective, the same kind of call.

Accepting a candidate = calling the EXISTING PATCH /reports/{id} with
{ [field]: candidateText } -- no new endpoint, no new logic. This is
Decision 1's entire point.
```

### Step breakdown

1. ✅ **Done — Step 1's investigation is resolved (Decision 4).** Finding:
   retrieved evidence/labels/retrieval-metadata are reconstructable as-is;
   `questionnaire_answers`/`clinical_notes` are not, and scope is
   expanded to persist them going forward, per Decision 4's resolution.
2. Migration: two nullable columns on `ReportRecord`
   (`questionnaire_answers` JSON, `clinical_notes` text), `NULL` default,
   no backfill value beyond `NULL` for existing rows (Decision 10).
3. `ReportGenerationService.generate()`: write both fields to the new
   columns at generation time, from the same request-body values it
   already receives — no new input, just stop discarding what's already
   there.
4. `PromptBuilder`: confirm whether it already has (or can cleanly gain)
   a reusable section-generation primitive — a way to ask for just
   `findings`, say, given the same context that originally produced the
   full 7-field report — without duplicating the context-assembly logic
   `ReportGenerationService` already has. (Deliberately not "a
   single-field mode," to avoid implying the full-report path and this
   one are the only two shapes generation will ever take.) This
   primitive reads `questionnaire_answers`/`clinical_notes` from the
   report's own row (Step 2/3) alongside the already-reconstructable
   evidence/labels — full context for any report generated after this
   phase ships.
5. `ReportEditService` (Phase 17's service, extended, not a new service
   — this is another edit-adjacent operation, same home as `PATCH`/
   `finalize`): `regenerate_section(report_id, field, doctor_id)` —
   ownership + final-check per Decision 3, calls the (possibly extended)
   `PromptBuilder`/LLM path, returns the candidate **plus a flag
   indicating whether `questionnaire_answers` was `NULL` on this report**
   (Decision 10 — the frontend needs this to show the incomplete-context
   warning). No DB write.
6. `POST /reports/{id}/regenerate-section` route wired to Step 5.
7. Frontend: a "Regenerate" affordance per editable section (the
   `regenerating` state `ReportSection` was already speced for, per
   this document's opening note), a real pending state during the LLM
   call, and on response — a diff preview (Decision 6, reusing
   `ReportDiffView`) comparing the candidate against the section's
   current content, with explicit Accept/Discard actions, plus Decision
   10's incomplete-context notice when the flag from Step 5 is set.
   Accept calls the existing `PATCH` (Decision 1); Discard does nothing,
   no request fired at all.
8. Real end-to-end verification: regenerate a section through a real
   Ollama call on a report generated *after* this phase ships (fresh
   `questionnaire_answers` populated, if the doctor didn't skip),
   confirm the candidate is genuinely different generated text (not an
   echo of the input), preview it via the diff, discard it (confirm
   nothing persisted — a fresh `GET` shows unchanged content),
   regenerate again, accept it this time (confirm a real `PATCH` fired,
   `status` transitioned correctly per Phase 17's existing rules, a real
   audit log row exists with `action = "EDITED"` per Decision 7's
   intentional design), and confirm regeneration is blocked (409) on
   both a non-owned report and a finalized one. Also confirm: after
   accepting one regeneration, a *second* regenerate-and-preview on the
   same field diffs against the just-accepted text, not against the
   original AI draft or a stale copy — the accepted regeneration must
   become the real baseline for whatever comes next, not just by
   assumption. Confirm Decision 9's finding in practice: fire a
   regenerate call, then (before accepting) issue a real `PATCH` against
   the same report from a second client/session, then accept the
   original regeneration — observe and report what actually happens,
   rather than assuming the documented behavior holds. **And separately,
   on a report that predates this phase** (real `questionnaire_answers
   IS NULL` row, not simulated): confirm regeneration still works, and
   confirm the incomplete-context warning (Decision 10) actually renders
   — this is the one behavior this phase adds that has no equivalent to
   fall back on if it's untested.

### Risks

- **Step 1 did reveal this phase is bigger than the original draft
  assumed** — the finding was mixed, not clean, and scope was expanded
  in response (Decision 4) rather than silently building against
  retrieval-only context. Recorded here as the risk that materialized,
  not a hypothetical.
- **The audit-log limitation (Decision 7) is a real, named gap, not a
  deferred nice-to-have** — if the thesis ever wants to report "doctor
  wrote X%, AI-regenerated content makes up Y% of finalized reports,"
  this phase as scoped cannot answer that question. State this
  explicitly wherever REP or edit-tracking is discussed in the thesis,
  so the two metrics' actual scope isn't overstated.
- **Every report generated before this phase ships has a permanent,
  unfixable `questionnaire_answers` gap** — there is no way to
  reconstruct what was never persisted. This is a one-time historical
  boundary, not an ongoing limitation (every report generated after
  this phase has full context available), but it means the demo/thesis
  should regenerate on a *freshly generated* report to show the feature
  at its intended fidelity, not on an old one carried over from earlier
  testing — and the incomplete-context warning (Decision 10) is exactly
  what makes that distinction visible rather than silently confusing.
- **Regeneration latency is unmeasured** — Step 1's investigation should
  include a rough real-timing check once the path exists, since a
  section regenerate that takes as long as a full report generation
  would undercut the UX argument for building this at the section level
  at all.
- **Prompt drift between the full-report and section-generation
  prompts is a real, low-urgency risk worth documenting now rather than
  discovering later.** If the full-report prompt is edited in some
  future phase and the section-regeneration prompt isn't updated in
  step, a regenerated `findings` could stop matching how `findings` is
  produced during original generation — not a blocker for this phase,
  but worth a comment at both prompt sites pointing at each other so a
  future edit to one is a deliberate decision about the other, not an
  accidental divergence.

### Explicitly not in scope

- Doctor-steering instructions on regeneration (Decision 5).
- Distinguishing regenerated-and-accepted edits from hand-typed ones in
  the audit log (Decision 7) — future work if the metric becomes needed.
- "Accept into report" from the Comparison Workspace and the
  hallucination-heuristic warning remain separately deferred, unaffected
  by this phase.

---

**Once frozen, implementation follows this project's standing
discipline: step-by-step, real execution output at each gate, confirmed
before proceeding, `development_log.md` updated with the same
four-part structure as every prior phase.**