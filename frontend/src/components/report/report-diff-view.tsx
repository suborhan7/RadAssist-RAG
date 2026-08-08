import type { Change } from "diff";
import { REPORT_CONTENT_FIELDS } from "@/components/report/report-document-view";
import type { ReportDiffSummary } from "@/lib/report-diff";
import { cn } from "@/lib/cn";

const FIELD_LABELS = new Map(REPORT_CONTENT_FIELDS.map(({ key, label }) => [key, label]));

/**
 * Phase 18 Step 3 / Phase 19 extraction: the actual word-diff markup
 * (additions --stable, removals --critical strikethrough, per
 * phase18_diff_view_architecture.md Decision 3) -- pulled out of
 * ReportDiffView so Phase 19's single-section regeneration preview can
 * reuse the identical rendering without a second, divergent copy. Phase
 * 18's "N of 5 sections changed / X% of the AI draft" summary framing
 * below does NOT extend to that use case (a regeneration candidate isn't
 * being compared against "the AI draft," it's being compared against the
 * current section content), so only this inner piece is shared, not the
 * whole component.
 */
export function DiffMarkup({ diff }: { diff: Change[] }) {
  // Reading Room diff register (design mock): the doctor's words are cyan and
  // underlined; drafted words that were removed go muted with a strike. No fill
  // blocks -- the two accents carry the whole distinction.
  return (
    <p className="mt-8 whitespace-pre-wrap text-findings text-text-secondary">
      {diff.map((change, i) => {
        if (change.added) {
          return (
            <span key={i} className="border-b border-cyan text-cyan">
              {change.value}
            </span>
          );
        }
        if (change.removed) {
          return (
            <span key={i} className={cn("text-text-muted line-through")}>
              {change.value}
            </span>
          );
        }
        return <span key={i}>{change.value}</span>;
      })}
    </p>
  );
}

/**
 * Phase 18 Step 3: renders a ReportDiffSummary (Step 2's pure
 * computeReportDiff output) as additions/removals, per
 * phase18_diff_view_architecture.md Decision 3 (additions --stable,
 * removals --critical strikethrough) and Decision 5 (only sections that
 * actually changed render diff markup -- unchanged sections are omitted
 * entirely, not shown as empty "Unchanged" panels; zero changed sections
 * renders one empty-state message instead of five empty ones).
 *
 * Reuses REPORT_CONTENT_FIELDS's existing label map (ReportDocumentView,
 * Phase 17) rather than a third, independent field-label list -- this
 * component only needs labels for the 5 editable fields, a subset of
 * that same 7-field list.
 *
 * No new color tokens: --stable/--critical are the same semantic tokens
 * Phase 14 already wired up (New/Persistent/Resolved findings in the
 * Comparison workspace use the identical bg/ink pairing), reused here for
 * the same "addition vs. removal" semantic, not decoration.
 */
export function ReportDiffView({ summary }: { summary: ReportDiffSummary }) {
  const changedSections = summary.sections.filter((section) => section.changed);

  return (
    <div className="flex flex-col gap-16">
      <p className="text-sm text-text-secondary">
        <span className="font-medium text-text-primary">
          {summary.sectionsChanged} of {summary.sections.length} sections changed
        </span>{" "}
        &middot; {summary.editPercentage.toFixed(1)}% of the AI draft was edited
      </p>

      {changedSections.length === 0 ? (
        <p className="rounded-panel border border-hairline bg-bg-hover px-14 py-12 text-sm text-text-secondary">
          No edits made.
        </p>
      ) : (
        <div className="flex flex-col">
          {changedSections.map((section) => (
            <div key={section.field} className="border-b border-hairline py-16 first:pt-0 last:border-0 last:pb-0">
              <h3 className="font-mono text-eyebrow uppercase text-text-tertiary">
                {FIELD_LABELS.get(section.field) ?? section.field}
              </h3>
              <DiffMarkup diff={section.diff} />
            </div>
          ))}
        </div>
      )}

      {/* Decision 6: draft-vs-current only, not a full revision history --
          this project's report_audit_log records who edited when, but
          never snapshots content at each edit, so there is no
          intermediate state to reconstruct here. */}
      <p className="text-caption text-text-tertiary">
        Comparing the original AI draft against the current report. This shows what changed overall,
        not a step-by-step edit history.
      </p>
    </div>
  );
}
