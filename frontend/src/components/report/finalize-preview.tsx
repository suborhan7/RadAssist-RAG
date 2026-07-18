"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { ReportDocumentView } from "@/components/report/report-document-view";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Phase 17 Step 7: the Preview screen, replacing a bare confirmation
 * dialog per the frozen (amended) architecture -- finalizing signs an
 * immutable report, so the doctor sees the exact document, in the exact
 * hospital-style rendering it will be read in afterward, before
 * committing. Reuses ReportDocumentView rather than a third rendering of
 * the same 7 fields.
 */
export function FinalizePreview({
  report,
  reportDate,
  onConfirm,
  onCancel,
}: {
  report: ReportDetailResponse;
  reportDate: string;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}) {
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setFinalizing(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finalize report.");
    } finally {
      setFinalizing(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-page">
      <Card className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-hairline p-tight px-card">
          <div>
            <h2 className="text-h3 text-ink">Preview before finalizing</h2>
            <p className="text-sm text-ink-3">
              Once finalized, this report cannot be edited further.
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-card">
          <h3 className="text-eyebrow uppercase text-ink-3">Report &middot; {reportDate}</h3>
          <div className="mt-2">
            <ReportDocumentView content={report.content} />
          </div>
        </div>

        {error && (
          <div className="mx-card mb-3 rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 border-t border-hairline p-card">
          <button
            type="button"
            onClick={onCancel}
            disabled={finalizing}
            className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md)}
          >
            Back to Edit
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={finalizing}
            className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}
          >
            {finalizing ? "Finalizing…" : "Confirm Finalize"}
          </button>
        </div>
      </Card>
    </div>
  );
}
