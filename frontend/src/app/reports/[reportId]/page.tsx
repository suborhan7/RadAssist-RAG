"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  finalizeReport,
  getCurrentDoctor,
  getPatient,
  getReport,
  retrievalSessionImageUrl,
  updateReport,
} from "@/lib/api-client";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/chip";
import { SimilarityBar } from "@/components/ui/similarity-bar";
import { AgreementBadge } from "@/components/ui/agreement-badge";
import { OwnerChip } from "@/components/ui/owner-chip";
import { computeAgreement } from "@/lib/evidence-agreement";
import { toChipReportStatus } from "@/lib/report-status";
import { useDoctorName } from "@/lib/use-doctor-name";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { EditableReportSection } from "@/components/report/editable-report-section";
import { FinalizePreview } from "@/components/report/finalize-preview";
import { ReportDiffView } from "@/components/report/report-diff-view";
import { computeReportDiff } from "@/lib/report-diff";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];
type PatientResponse =
  paths["/patients/{patient_id}"]["get"]["responses"][200]["content"]["application/json"];
export type ReportContentKey = keyof ReportDetailResponse["content"];

// Phase 17 Step 7 / Phase 18 Decision 9: the single canonical list of the
// 5 user-editable report sections -- examination/disclaimer stay AI-set/
// read-only (exam-type metadata vs. free clinical narrative; fixed
// compliance statement) and are deliberately excluded. Exported so Phase
// 18's diff/section-counter/percentage logic imports this exact list
// rather than redeclaring it -- found duplicated (this Set plus a second,
// independent hardcoded object literal in handleRestoreAiDraft() below)
// within this same file before this consolidation, not actually
// centralized despite there being only one file involved.
export const EDITABLE_REPORT_FIELDS = [
  "clinical_history",
  "technique",
  "findings",
  "impression",
  "recommendation",
] as const satisfies readonly ReportContentKey[];

export type EditableReportField = (typeof EDITABLE_REPORT_FIELDS)[number];

const CONTENT_FIELDS: { key: ReportContentKey; label: string }[] = [
  { key: "examination", label: "Examination" },
  { key: "clinical_history", label: "Clinical History" },
  { key: "technique", label: "Technique" },
  { key: "findings", label: "Findings" },
  { key: "impression", label: "Impression" },
  { key: "recommendation", label: "Recommendation" },
  { key: "disclaimer", label: "Disclaimer" },
];

const EDITABLE_KEYS = new Set<ReportContentKey>(EDITABLE_REPORT_FIELDS);

/**
 * Radiologist Workspace (Phase 12 Step 5, restyled Phase 14 per
 * design_specification.md §8.12 -- frontend/CLAUDE.md cites this as §8.10,
 * a citation slip; §8.10 is actually "Retrieval", a different screen).
 * Explainability and Comparison are actions launched FROM here, not
 * separate, disconnected features. Retrieved evidence is a rail here, not
 * a separate page.
 *
 * Three registers, per §6.1/§8.12: the image sits in `--lightbox` (the
 * only dark surface in the product), the report is paper/sans document
 * typography, the evidence rail is paper but quieter/mono-heavy.
 *
 * NOT built, flagged explicitly rather than faked:
 * - Citation markers linking specific report sentences to specific
 *   retrieved cases (§8.12's "signature interaction"). The backend
 *   returns report content as plain prose with no sentence-level
 *   grounding markup at all -- building this would mean inventing a
 *   citation-extraction feature with no backend support, not styling an
 *   existing one. The report is rendered in the correct document
 *   register; the hover-linking interaction is not implemented.
 * - Window/level, zoom, pan, invert, prior-study thumbnails (§8.12's
 *   Lightbox toolbar) -- real PACS-viewer engineering, not a styling
 *   pass; not attempted here.
 * - "Alternatives in retrieved evidence"'s (§10.3) "not present" column
 *   requires the full label taxonomy, which no endpoint here exposes to
 *   the frontend -- only the "present in the retrieved set" side is
 *   real and shown; the "not present" side is omitted rather than
 *   invented from a hardcoded label list.
 * - Evidence Agreement's Strong/Mixed/Weak classification (§10.2) is
 *   computed client-side from retrieved_cases (see lib/evidence-agreement.ts)
 *   since ReportDetailResponse carries no voted_labels field -- a
 *   documented re-derivation, not a second backend source of truth.
 * - Per-section Regenerate (§8.12) and the word-level "Changes vs AI
 *   draft" diff (§10.5) -- explicitly deferred to Phase 18, per the
 *   frozen Phase 17 scope.
 *
 * Phase 15: OwnershipChip (via OwnerChip) in the context bar, and a
 * read-only banner (§8.15, adapted copy -- no "signed" language, since
 * finalize didn't exist yet at that phase, and no "your access has been
 * recorded" clause, since no access-log table exists, per
 * frontend/CLAUDE.md's explicit instruction).
 *
 * Phase 17 Step 7: real edit/finalize. Each of the 5 editable sections
 * (EditableReportSection) commits independently via PATCH /reports/{id}
 * as soon as the doctor presses Enter or blurs the field -- there is no
 * page-level "Save" button, matching the per-section-commit design.
 * `content` (rendered here) sources final_content -- what the report
 * currently says, doctor edits included; `ai_draft_content` (fetched but
 * not directly rendered outside Restore) is the immutable original.
 * "Edited" is a per-field, client-computed signal
 * (content[key] !== ai_draft_content[key]), not a stored flag -- no
 * backend field-level tracking exists, so this is the honest thing to
 * derive. Editing/finalizing is gated on isOwner AND status !== "final";
 * a non-owner or a finalized report renders every section exactly like
 * before (EditableReportSection degrades to plain read-only text when
 * canEdit is false). Finalize opens FinalizePreview (Preview screen)
 * rather than a bare confirm, reusing ReportDocumentView for the actual
 * document -- see that component's own docstring for why extracting it
 * was necessary (nothing reusable existed before this step). The
 * unsaved-changes guard is frontend-only: beforeunload covers tab
 * close/refresh/external navigation; the in-app Explain/Compare/patient
 * links are individually guarded with a confirm() since Next.js App
 * Router has no built-in route-change-intercept event to hook globally.
 */
export default function ReportWorkspacePage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;

  const [report, setReport] = useState<ReportDetailResponse | null>(null);
  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [railTab, setRailTab] = useState<"evidence" | "agreement" | "alternatives">("evidence");
  const [currentDoctorId, setCurrentDoctorId] = useState<string | null>(null);

  const [savingField, setSavingField] = useState<ReportContentKey | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [dirtyFields, setDirtyFields] = useState<Set<ReportContentKey>>(new Set());

  useEffect(() => {
    getReport(reportId)
      .then(async (reportResult) => {
        setReport(reportResult);
        if (reportResult.patient_id) {
          try {
            const patientResult = await getPatient(reportResult.patient_id);
            setPatient(patientResult);
          } catch {
            setPatient(null);
          }
        }
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load report.");
      });
    getCurrentDoctor()
      .then((doctor) => setCurrentDoctorId(doctor?.id ?? null))
      .catch(() => setCurrentDoctorId(null));
  }, [reportId]);

  const agreement = useMemo(() => {
    if (!report) return null;
    return computeAgreement(report.retrieved_cases);
  }, [report]);

  const diffSummary = useMemo(() => {
    if (!report) return null;
    return computeReportDiff(report.ai_draft_content, report.content);
  }, [report]);

  const reportOwnerId = report?.doctor_id ?? null;
  const isOwner = reportOwnerId !== null && currentDoctorId !== null && reportOwnerId === currentDoctorId;
  const otherOwnerName = useDoctorName(isOwner ? null : reportOwnerId);
  const finalizedByName = useDoctorName(report?.finalized_by ?? null);

  const canEdit = isOwner && report?.status !== "final";
  const hasUnsavedChanges = dirtyFields.size > 0;

  const handleDirtyChange = useCallback((key: ReportContentKey, dirty: boolean) => {
    setDirtyFields((prev) => {
      const next = new Set(prev);
      if (dirty) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  // beforeunload -- covers tab close/refresh/typed-URL navigation. This is
  // the one part of the guard the browser itself enforces; everything
  // else below is a best-effort in-app interception only.
  useEffect(() => {
    function handler(e: BeforeUnloadEvent) {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  function guardedNavigate(e: React.MouseEvent) {
    if (hasUnsavedChanges && !window.confirm("You have an unsaved edit in progress. Leave without saving?")) {
      e.preventDefault();
    }
  }

  async function handleCommit(key: ReportContentKey, nextValue: string) {
    if (!report) return;
    setSavingField(key);
    setActionError(null);
    try {
      const updated = await updateReport(reportId, { [key]: nextValue });
      setReport(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to save edit.");
    } finally {
      setSavingField(null);
    }
  }

  async function handleRestoreAiDraft() {
    if (!report) return;
    if (!window.confirm("Replace your edits with the original AI draft? This cannot be undone.")) return;
    setRestoring(true);
    setActionError(null);
    try {
      const restoreValues = EDITABLE_REPORT_FIELDS.reduce(
        (acc, field) => {
          acc[field] = report.ai_draft_content[field];
          return acc;
        },
        {} as Record<EditableReportField, string>,
      );
      const updated = await updateReport(reportId, restoreValues);
      setReport(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to restore AI draft.");
    } finally {
      setRestoring(false);
    }
  }

  async function handleFinalizeConfirm() {
    const updated = await finalizeReport(reportId);
    setReport(updated);
    setShowPreview(false);
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="rounded-card border border-critical-bd bg-critical-bg px-4 py-3 text-critical-ink">
          {error}
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="text-ink-3">Loading report...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      {/* Study context bar */}
      <div className="flex h-context-bar items-center justify-between border-b border-hairline bg-surface px-page">
        <div className="flex items-center gap-3">
          <h1 className="text-h3 text-ink">Radiologist Workspace</h1>
          {patient ? (
            <Link
              href={`/patients/${patient.id}`}
              onClick={guardedNavigate}
              className="text-sm text-ink-2 underline"
            >
              {patient.name} &middot; {patient.patient_code}
            </Link>
          ) : (
            <span className="text-sm text-ink-3">No patient linked to this report.</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Phase 18: visible to any doctor who can already read this
              report (Decision 7) -- owner or not, pre- or post-finalize.
              Both ai_draft_content/content are already universally
              readable, so no new permission logic is needed here. */}
          <button
            type="button"
            onClick={() => setShowDiff((prev) => !prev)}
            className="text-sm font-medium text-ink-2 underline decoration-hairline-strong underline-offset-2 hover:text-steel-ink"
          >
            {showDiff ? "Hide changes vs AI draft" : "Changes vs AI draft"}
          </button>
          <OwnerChip ownerId={reportOwnerId} currentDoctorId={currentDoctorId} />
          <StatusChip status={toChipReportStatus(report.status)} />
        </div>
      </div>

      {showDiff && diffSummary && (
        <div className="border-b border-hairline bg-surface px-page py-4">
          <ReportDiffView summary={diffSummary} />
        </div>
      )}

      {!isOwner && reportOwnerId !== null && (
        <div className="border-b border-hairline bg-sunken px-page py-3 text-sm text-ink-2">
          This report belongs to {otherOwnerName ?? "another doctor"}. You can read it and compare
          against it.
        </div>
      )}

      <div className="flex flex-1 flex-col gap-4 p-page lg:flex-row">
        {/* Lightbox -- the only black surface */}
        <div className="flex min-h-[420px] flex-1 items-center justify-center rounded-card bg-lightbox lg:min-w-[420px]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={retrievalSessionImageUrl(report.session_id)}
            alt={`Chest X-ray, ${report.report_date}`}
            className="max-h-[70vh] max-w-full object-contain"
          />
        </div>

        {/* Report as document */}
        <Card className="flex w-full flex-col gap-0 lg:w-report-col">
          <div className="flex items-center justify-between border-b border-hairline p-tight px-card">
            <div>
              <h2 className="text-eyebrow uppercase text-ink-3">
                {report.status === "final" ? "Finalized Report" : "AI Report"} &middot; {report.report_date}
              </h2>
              {report.status === "final" && report.finalized_at && (
                <p className="mt-0.5 text-sm text-ink-3">
                  Finalized by {finalizedByName ?? "this doctor"} on{" "}
                  {new Date(report.finalized_at).toLocaleDateString()}
                </p>
              )}
            </div>
            {canEdit && (
              <button
                type="button"
                onClick={handleRestoreAiDraft}
                disabled={restoring}
                className={cn(BUTTON_BASE, VARIANT.ghost, SIZE.sm)}
              >
                {restoring ? "Restoring…" : "Restore AI Draft"}
              </button>
            )}
          </div>
          <div className="flex flex-col divide-y divide-hairline p-card">
            {CONTENT_FIELDS.map(({ key, label }) => (
              <EditableReportSection
                key={key}
                label={label}
                value={report.content[key] ?? ""}
                isEdited={report.content[key] !== report.ai_draft_content[key]}
                canEdit={!!canEdit && EDITABLE_KEYS.has(key)}
                saving={savingField === key}
                onCommit={(next) => handleCommit(key, next)}
                onDirtyChange={(dirty) => handleDirtyChange(key, dirty)}
              />
            ))}
          </div>

          {actionError && (
            <div className="m-card mt-0 rounded-card border border-critical-bd bg-critical-bg p-tight text-sm text-critical-ink">
              {actionError}
            </div>
          )}

          {/* Validation */}
          <div
            className={cn(
              "m-card mt-0 rounded-card border p-tight",
              report.validation.is_clean
                ? "border-stable-bd bg-stable-bg"
                : "border-caution-bd bg-caution-bg",
            )}
          >
            <h3 className="text-eyebrow uppercase text-ink-3">Validation</h3>
            {report.validation.is_clean ? (
              <p className="mt-1 text-sm text-stable-ink">No validation warnings.</p>
            ) : (
              <ul className="mt-1 list-inside list-disc text-sm text-caution-ink">
                {report.validation.warnings.map((warning, i) => (
                  <li key={i}>{warning}</li>
                ))}
              </ul>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-3 p-card pt-0">
            <Link
              href={`/reports/${reportId}/explain`}
              onClick={guardedNavigate}
              className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md, "flex-1")}
            >
              Explain Report
            </Link>
            <Link
              href={`/reports/${reportId}/compare`}
              onClick={guardedNavigate}
              className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md, "flex-1")}
            >
              Compare Previous Report
            </Link>
            {canEdit && (
              <button
                type="button"
                onClick={() => setShowPreview(true)}
                className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md, "flex-1")}
              >
                Finalize
              </button>
            )}
            <button
              type="button"
              disabled
              title="Out of scope for this thesis (frozen Phase 12 spec)"
              className={cn(BUTTON_BASE, VARIANT.ghost, SIZE.md, "flex-1")}
            >
              Download PDF
            </button>
          </div>
        </Card>

        {/* Evidence rail -- paper, quieter, mono-heavy */}
        <Card className="flex w-full flex-col lg:w-evidence-rail">
          <div className="flex border-b border-hairline">
            {(["evidence", "agreement", "alternatives"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setRailTab(tab)}
                className={cn(
                  "flex-1 border-b-2 px-3 py-2 text-sm font-medium capitalize transition-colors duration-hover",
                  railTab === tab
                    ? "border-steel text-steel-ink"
                    : "border-transparent text-ink-3 hover:text-ink",
                )}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="p-card">
            {railTab === "evidence" && (
              <div className="flex flex-col gap-3">
                <h3 className="text-eyebrow uppercase text-ink-3">
                  Retrieved evidence ({report.retrieved_cases.length} cases)
                </h3>
                {report.retrieved_cases.map((c) => (
                  <div key={c.rank} className="rounded-card border border-hairline p-tight text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink">
                        #{c.rank} &middot; {c.primary_label}
                      </span>
                    </div>
                    <SimilarityBar value={c.similarity * 100} className="mt-2" />
                    <p className="mt-2 text-ink-2">{c.findings}</p>
                    <p className="text-ink-2">{c.impression}</p>
                  </div>
                ))}
              </div>
            )}

            {railTab === "agreement" && agreement && (
              <AgreementBadge level={agreement.level} factors={agreement.factors} />
            )}

            {railTab === "alternatives" && agreement && (
              <div className="flex flex-col gap-3">
                <h3 className="text-eyebrow uppercase text-ink-3">
                  Present in the retrieved set
                </h3>
                <dl className="flex flex-col">
                  {agreement.presentLabels.map(({ label, count, k }) => (
                    <div
                      key={label}
                      className="flex items-center justify-between border-b border-hairline py-2 last:border-0"
                    >
                      <dt className="text-sm text-ink-2">{label}</dt>
                      <dd className="font-mono text-data-sm text-ink">
                        {count} of {k}
                      </dd>
                    </div>
                  ))}
                </dl>
                <p className="rounded-card bg-sunken p-tight text-sm text-ink-2">
                  Absence from this list means no retrieved case carried the label. It is not an
                  exclusion. The full set of labels the system could have retrieved is not shown
                  here -- only labels present are reported, not a complete positive/negative
                  taxonomy.
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {showPreview && diffSummary && (
        <FinalizePreview
          report={report}
          reportDate={report.report_date}
          diffSummary={diffSummary}
          onConfirm={handleFinalizeConfirm}
          onCancel={() => setShowPreview(false)}
        />
      )}
    </div>
  );
}
