import { REPORT_CONTENT_FIELDS } from "@/components/report/report-document-view";
import type { ReportDiffSummary } from "@/lib/report-diff";
import { cn } from "@/lib/cn";

const FIELD_LABELS = new Map(REPORT_CONTENT_FIELDS.map(({ key, label }) => [key, label]));

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
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-2">
        <span className="font-medium text-ink">
          {summary.sectionsChanged} of {summary.sections.length} sections changed
        </span>{" "}
        &middot; {summary.editPercentage.toFixed(1)}% of the AI draft was edited
      </p>

      {changedSections.length === 0 ? (
        <p className="rounded-card border border-hairline bg-sunken px-3 py-2 text-sm text-ink-2">
          No edits made.
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-hairline">
          {changedSections.map((section) => (
            <div key={section.field} className="py-3 first:pt-0 last:pb-0">
              <h3 className="text-h3 text-ink">{FIELD_LABELS.get(section.field) ?? section.field}</h3>
              <p className="mt-1 whitespace-pre-wrap text-report text-ink-2">
                {section.diff.map((change, i) => {
                  if (change.added) {
                    return (
                      <span key={i} className="rounded-in bg-stable-bg px-0.5 text-stable-ink">
                        {change.value}
                      </span>
                    );
                  }
                  if (change.removed) {
                    return (
                      <span
                        key={i}
                        className={cn("rounded-in bg-critical-bg px-0.5 text-critical-ink line-through")}
                      >
                        {change.value}
                      </span>
                    );
                  }
                  return <span key={i}>{change.value}</span>;
                })}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Decision 6: draft-vs-current only, not a full revision history --
          this project's report_audit_log records who edited when, but
          never snapshots content at each edit, so there is no
          intermediate state to reconstruct here. */}
      <p className="text-xs text-ink-3">
        Comparing the original AI draft against the current report. This shows what changed overall,
        not a step-by-step edit history.
      </p>
    </div>
  );
}
