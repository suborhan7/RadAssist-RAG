"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { ReportDocumentView } from "@/components/report/report-document-view";
import { ReportDiffView } from "@/components/report/report-diff-view";
import { useT } from "@/lib/i18n";
import type { ReportDiffSummary } from "@/lib/report-diff";
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
 *
 * Phase 18 Decision 8: also surfaces the "Changes vs AI draft" diff here
 * -- a doctor previewing before finalizing can see exactly what they
 * changed as part of this same review moment, not as a separately-
 * discovered feature elsewhere.
 */
export function FinalizePreview({
  report,
  reportDate,
  diffSummary,
  onConfirm,
  onCancel,
}: {
  report: ReportDetailResponse;
  reportDate: string;
  diffSummary: ReportDiffSummary;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useT();
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  async function handleConfirm() {
    setFinalizing(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("report.errFinalize"));
    } finally {
      setFinalizing(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg-page/70 p-44">
      <Card className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-hairline px-24 py-20">
          <div>
            <h2 className="text-panel text-text-primary">{t("report.previewTitle")}</h2>
            <p className="mt-3 text-sm text-text-secondary">
              {t("report.previewDesc")}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowDiff((prev) => !prev)}
            className="shrink-0 text-sm font-medium text-text-secondary transition-colors duration-hover hover:text-cyan"
          >
            {showDiff ? t("report.hideChangesAi") : t("report.changesAi")}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-24">
          {showDiff ? (
            <ReportDiffView summary={diffSummary} />
          ) : (
            <>
              <h3 className="font-mono text-eyebrow uppercase text-text-tertiary">{t("workspace.reportFallback")} &middot; {reportDate}</h3>
              <div className="mt-14">
                <ReportDocumentView content={report.content} />
              </div>
            </>
          )}
        </div>

        {error && (
          <div className="mx-24 mb-14 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-14 border-t border-hairline p-24">
          <button
            type="button"
            onClick={onCancel}
            disabled={finalizing}
            className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md)}
          >
            {t("report.backToEdit")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={finalizing}
            className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}
          >
            {finalizing ? t("report.finalizing") : t("report.confirmFinalize")}
          </button>
        </div>
      </Card>
    </div>
  );
}
