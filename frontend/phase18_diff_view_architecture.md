## Phase 18 — Word-Level Diff View: Architecture (PROPOSED, NOT YET FROZEN)

**Status: draft, pending user review.** Do not implement until this
section is explicitly frozen, same discipline as every prior phase.

### Why this phase, and why it's genuinely small

Chosen over the other three deferred candidates (section-level
regeneration, "Accept into report," the hallucination-heuristic warning)
specifically because it needs **zero new backend work** — Phase 17
already put both `ai_draft_content` and `final_content` on
`ReportDetailResponse`, readable by any authenticated doctor under the
shared-read model already frozen since Phase 13a. This phase is a
rendering problem, not a data problem.

design_specification.md §10.6 specifies the target: a `[Changes vs AI
draft]` control that opens a word-level diff — additions in `--stable`,
removals in `--critical` strikethrough — with a summary header. Its
original wording ("3 of 7 sections changed") predates Phase 17's real
findings; corrected below to match what Phase 17 actually confirmed
(5 editable sections, not 7 — see Decision 2).

### Decisions frozen (pending this section's approval)

1. **No backend changes.** The diff is computed entirely client-side
   from data the frontend already has. No new endpoint, no new column,
   no new response field.
2. **The diff and its percentage cover the 5 editable fields only**
   (`clinical_history`, `technique`, `findings`, `impression`,
   `recommendation`) — not all 7. `examination` and `disclaimer` are
   structurally locked (Phase 17 Decision 2) and can never differ from
   the AI draft; including them in the denominator would understate the
   real edit percentage relative to what a doctor could actually change.
   Summary language is therefore **"N of 5 sections changed,"** not "of
   7" — correcting the design spec's original wording to match Phase
   17's real, frozen field count rather than copying it uncritically.
3. **Percentage formula, stated precisely because this is a candidate
   thesis evaluation metric and "looks about right" isn't defensible in
   a methodology chapter — named "Report Edit Percentage (REP)" for
   thesis use.** For each of the 5 editable fields, run a word-level
   diff between `ai_draft_content[field]` and `final_content[field]`
   using **`diffWordsWithSpace()`, and only this function, for both the
   rendered diff and the percentage calculation** — the same
   tokenization must produce both outputs, or the displayed diff and
   the reported number can silently diverge. Sum the added+removed word
   counts across all 5 fields, but **exclude any change whose value is
   pure whitespace** from that count (a line-break-only edit should not
   inflate REP) — this makes "word" mean an actual word token under
   `diffWordsWithSpace()`, not any changed span. Divide by the total
   word count of `ai_draft_content` across the same 5 fields:

   ```
   REP = (Σ added_words + removed_words across 5 fields)
         ─────────────────────────────────────────────── × 100
              (total words in ai_draft across 5 fields)
   ```

   **If the AI draft's 5 editable fields contain zero words in total,
   REP is defined as 0%** — an explicit rule, not undefined behavior,
   even though this edge case is unlikely to occur in practice (Phase
   17's finalize validation requires non-empty findings/impression, but
   the diff view is also viewable pre-finalize on a fresh generation,
   so the zero-word case isn't strictly impossible to reach). This is a
   real, reproducible, whole-document ratio — not a per-field average,
   which would weight a heavily-edited one-word field the same as a
   heavily-edited two-hundred-word field. If REP appears in the thesis
   evaluation chapter, state this exact equation and the
   `diffWordsWithSpace`-with-whitespace-exclusion definition of "word"
   verbatim, not paraphrased, so it's reproducible by an examiner
   reading the thesis alone.
4. **Diff library: use an established one, don't hand-roll a word-diff
   algorithm.** `diff` (jsdiff)'s `diffWordsWithSpace` (Decision 3 fixes
   the exact function — no longer "diffWords or diffWordsWithSpace,
   whichever") is the standard choice — MIT-licensed, small, widely
   used. Confirm whether it's already a dependency before adding it; if
   not, this is the one new package this phase introduces.
5. **Only sections that actually changed render diff markup — a single
   behavior, not two left open for implementation to decide.** Unchanged
   sections are omitted from the diff view entirely, not shown as
   "Unchanged" panels. If no sections changed, the diff view shows one
   empty-state message ("No edits made") instead of five empty panels.
6. **This is a two-point comparison (draft vs. current), not a full
   revision history.** Phase 17's `report_audit_log` records *who*
   edited *when*, but never snapshots *what the content was* at each
   edit — there is no intermediate state to reconstruct. The diff view
   always compares `ai_draft_content` against the current
   `final_content`, regardless of how many edits happened in between.
   State this explicitly in the UI copy and the thesis — this is not an
   edit-history feature, even though it sits next to one.
7. **Visible to any doctor who can already read the report** — owner or
   not, pre-finalize or post-finalize. Both fields it reads are already
   universally readable (Decision 1); a non-owner viewing a colleague's
   finalized report can see the same diff the owning doctor could. No
   new permission logic, since none is needed on top of what's already
   frozen.
8. **Entry point: a `[Changes vs AI draft]` control near the status
   chip / finalize bar** (per design_specification.md §10.6), and also
   surfaced from `FinalizePreview` (Phase 17) — a doctor previewing
   before finalizing can see exactly what they changed as part of that
   same review moment, not as a separately-discovered feature. Reuses
   `ReportDocumentView`'s layout conventions for section structure
   rather than inventing a new panel chrome.
9. **A single `EDITABLE_REPORT_FIELDS` constant, referenced everywhere
   the 5-field list is needed** — the editor, `FinalizePreview`, this
   phase's diff/section-counter/percentage logic, and tests — never
   redeclared. Step 1 already asks whether Phase 17 centralized this
   list; this decision settles what to do with the answer either way:
   if Phase 17 already has one canonical constant, reuse it, no new
   scope. **If Phase 17 duplicated the 5 field names across multiple
   components instead** (plausible — `EditableReportSection` and
   `FinalizePreview` were built as separate components in Phase 17's
   Step 7), consolidating them into one constant is worth doing now,
   but it means this phase touches Phase 17's existing files, not only
   new Phase 18 code — say so plainly when reporting Step 1's findings,
   rather than letting it pass as an invisible side effect of "add a
   diff view."

### Data (no schema, client-side only)

```typescript
// Computed on render, not stored anywhere
interface SectionDiff {
  field: EditableField;         // one of the 5
  changed: boolean;
  diff: Change[];               // diffWords() output, if changed
}

interface ReportDiffSummary {
  editPercentage: number;       // Decision 3's formula
  sectionsChanged: number;      // out of 5
  sections: SectionDiff[];
}
```

### Step breakdown

1. Confirm `diff` (jsdiff) isn't already a dependency before adding it;
   confirm whether Phase 17 already defined a single canonical 5-field
   constant somewhere in the frontend, per Decision 9 — report which
   case it is (already centralized vs. duplicated across components)
   before proceeding, since the second case means this step also touches
   Phase 17's existing files.
2. `computeReportDiff(aiDraft: ReportContent, final: ReportContent):
   ReportDiffSummary` — pure function, Decisions 2/3/5's rules,
   unit-tested directly (no browser needed for this part: feed it two
   `ReportContent` objects, assert REP and per-section `changed` flags
   against known inputs). Required cases: zero edits, every word
   changed, **a punctuation-only edit** (e.g. "No pleural effusion." →
   "No pleural effusion" — validates `diffWordsWithSpace`'s tokenization
   doesn't misbehave on the exact risk already named below), and **the
   zero-word-denominator edge case** (all 5 fields empty in the AI
   draft → REP defined as 0%, not `NaN` or a thrown error).
3. Diff rendering component: additions `--stable`, removals `--critical`
   strikethrough, per §10.6 and this project's existing token discipline
   (no new colors — reuse the same semantic tokens Phase 14 already
   wired up).
4. Wire the `[Changes vs AI draft]` entry point into the report view's
   status/finalize-bar area and into `FinalizePreview`.
5. Real end-to-end check: edit a real report through real Ollama
   generation → open the diff view → confirm the rendered percentage
   and section count match a hand-computed expectation for that specific
   edit, not just "a number appeared." Also check the zero-edit case
   (fresh `AI_DRAFT`, diff view shows 0%, 0 of 5 changed, not an error
   or an empty crash) and the non-owner read case (doctor B opens doctor
   A's report, diff view still renders).

### Risks

- **REP (Decision 3) is a judgment call this document makes, not
  something jsdiff or Phase 17 dictates** — now precisely defined
  (exact tokenizer, exclusion of pure-whitespace changes, zero-
  denominator rule), so the remaining risk is purely about faithful
  reporting: if REP appears in the thesis evaluation chapter, the exact
  equation and word-definition belong in the methodology write-up
  verbatim, not paraphrased, so it's reproducible by an examiner reading
  the thesis alone.
- **Whole-document percentage can hide field-level detail** — a report
  where `findings` was completely rewritten and the other 4 fields
  untouched will show a moderate overall REP, not "100% of one
  section." The per-section `changed` boolean (already shown, Decision
  5) is what carries that detail; REP is a summary, not the full
  picture, and should be described that way if cited.
- **jsdiff's word tokenization is naive (whitespace/punctuation-based)**
  — the punctuation-only test case (Step 2) now directly checks this
  rather than leaving it as an unverified concern, but worth a broader
  sanity check against a real report containing punctuation-heavy
  findings language before trusting the word counts blindly.

### Explicitly not in scope

- Section-level regeneration, "Accept into report," and the
  hallucination-heuristic warning remain separately deferred, unaffected
  by this phase.
- No backend persistence of diff results — always computed live.
- No per-edit-event diff reconstruction (Decision 6) — draft-vs-current
  only.

---

**Once frozen, implementation follows this project's standing
discipline: step-by-step, real execution output at each gate, confirmed
before proceeding, `development_log.md` updated with the same
four-part structure as every prior phase.**
