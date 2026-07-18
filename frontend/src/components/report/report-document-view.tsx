import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];
type ReportContentResponse = ReportDetailResponse["content"];

export const REPORT_CONTENT_FIELDS: { key: keyof ReportContentResponse; label: string }[] = [
  { key: "examination", label: "Examination" },
  { key: "clinical_history", label: "Clinical History" },
  { key: "technique", label: "Technique" },
  { key: "findings", label: "Findings" },
  { key: "impression", label: "Impression" },
  { key: "recommendation", label: "Recommendation" },
  { key: "disclaimer", label: "Disclaimer" },
];

/**
 * Phase 12's original report-as-document rendering, extracted here in
 * Phase 17 Step 7 -- previously this was inline JSX inside
 * app/reports/[reportId]/page.tsx with no separate component at all (the
 * "cross-doctor read-only view" was never actually a distinct renderer,
 * just the same markup every viewer saw). Extracting it lets the new
 * Preview screen (ahead of finalize) reuse the exact same hospital-style
 * document layout, one source of truth, rather than a second copy that
 * can drift.
 *
 * Purely read-only -- no edit affordances live here. The main Workspace
 * page's editable sections are a separate component
 * (EditableReportSection) that wraps this same field list with
 * edit/commit behavior; this component is for contexts that are always
 * read-only regardless of ownership (the Preview screen, principally).
 */
export function ReportDocumentView({ content }: { content: ReportContentResponse }) {
  return (
    <div className="flex flex-col divide-y divide-hairline">
      {REPORT_CONTENT_FIELDS.map(({ key, label }) => (
        <div key={key} className="py-3 first:pt-0 last:pb-0">
          <h3 className="text-h3 text-ink">{label}</h3>
          <p className="mt-1 whitespace-pre-wrap text-report text-ink-2">{content[key] || "(none)"}</p>
        </div>
      ))}
    </div>
  );
}
