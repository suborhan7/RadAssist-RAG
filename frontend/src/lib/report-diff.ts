import { diffWordsWithSpace, type Change } from "diff";
import { EDITABLE_REPORT_FIELDS, type EditableReportField } from "@/app/reports/[reportId]/page";

export interface SectionDiff {
  field: EditableReportField;
  changed: boolean;
  diff: Change[];
}

export interface ReportDiffSummary {
  editPercentage: number;
  sectionsChanged: number;
  sections: SectionDiff[];
}

/**
 * Counts "words" within a single diffWordsWithSpace() chunk by splitting
 * its already-produced value on whitespace runs. A Change's `value` can
 * merge several of the tokenizer's own word/whitespace tokens together
 * (e.g. one added chunk "text now" covers a word + a space + a word),
 * so this decomposes it back into real word tokens using the exact same
 * word/whitespace boundary the tokenizer already drew -- not a second,
 * independent tokenizer applied to the raw pre-diff text. A pure-
 * whitespace chunk (" ", "\n") naturally yields 0 here, which is exactly
 * Decision 3's "exclude pure whitespace changes" rule -- it falls out of
 * this definition rather than needing a separate special case.
 */
function countWords(value: string): number {
  return value.split(/\s+/).filter((token) => token.length > 0).length;
}

/**
 * Phase 18 Step 2: the Report Edit Percentage (REP) formula, per
 * phase18_diff_view_architecture.md Decision 3 -- stated precisely
 * because REP is a candidate thesis evaluation metric. `diffWordsWithSpace()`
 * is the ONLY tokenization used for both the rendered diff (each
 * SectionDiff.diff) and this percentage: both are read off the exact
 * same Change[] array per field, so the displayed markup and the
 * reported number can never silently diverge.
 *
 * `changed` (feeding `sectionsChanged`, "N of 5 sections changed") is
 * plain string inequality -- deliberately NOT the same test as REP's
 * word-count. A whitespace-only edit (e.g. a doctor adding a line break)
 * is a real, honest change worth surfacing in the diff view; it just
 * contributes 0 to REP's word count, per Decision 3's specific "a line-
 * break-only edit should not inflate REP" rule. Keeping these two checks
 * separate (rather than reusing one for both) is deliberate, not an
 * oversight -- a report can have `sectionsChanged > 0` with `editPercentage`
 * still 0% if every change was whitespace-only.
 *
 * The denominator ("total words in ai_draft across the 5 fields") is
 * `countWords()` applied directly to each field's raw ai_draft text, not
 * routed through a self-diff -- diffing any non-empty string against
 * itself always yields one whole unchanged chunk equal to that same
 * string (verified directly against this project's installed `diff`
 * version), so the two approaches are mathematically identical; the
 * direct call avoids a pointless indirection.
 *
 * Decision 2: only the 5 editable fields are ever considered --
 * `examination`/`disclaimer` are structurally AI-set-only (Phase 17) and
 * excluded from both the diff and the denominator, so the reported
 * percentage isn't understated relative to what a doctor could actually
 * change.
 */
export function computeReportDiff(
  aiDraft: Record<EditableReportField, string>,
  final: Record<EditableReportField, string>,
): ReportDiffSummary {
  let addedOrRemovedWords = 0;
  let totalDraftWords = 0;
  let sectionsChanged = 0;

  const sections: SectionDiff[] = EDITABLE_REPORT_FIELDS.map((field) => {
    const draftText = aiDraft[field] ?? "";
    const finalText = final[field] ?? "";
    const changed = draftText !== finalText;
    if (changed) sectionsChanged += 1;

    const diff = diffWordsWithSpace(draftText, finalText);
    for (const change of diff) {
      if (change.added || change.removed) {
        addedOrRemovedWords += countWords(change.value);
      }
    }
    totalDraftWords += countWords(draftText);

    return { field, changed, diff };
  });

  // Decision 3: an explicit rule, not undefined (NaN) behavior.
  const editPercentage = totalDraftWords === 0 ? 0 : (addedOrRemovedWords / totalDraftWords) * 100;

  return { editPercentage, sectionsChanged, sections };
}
