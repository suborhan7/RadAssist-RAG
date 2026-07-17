"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useEffect } from "react";
import { ApiError, getCurrentDoctor, getPatient, getReport, retrievalSessionImageUrl } from "@/lib/api-client";
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
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];
type PatientResponse =
  paths["/patients/{patient_id}"]["get"]["responses"][200]["content"]["application/json"];

const CONTENT_FIELDS: { key: keyof ReportDetailResponse["content"]; label: string }[] = [
  { key: "examination", label: "Examination" },
  { key: "clinical_history", label: "Clinical History" },
  { key: "technique", label: "Technique" },
  { key: "findings", label: "Findings" },
  { key: "impression", label: "Impression" },
  { key: "recommendation", label: "Recommendation" },
  { key: "disclaimer", label: "Disclaimer" },
];

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
 *
 * Phase 15: OwnershipChip (via OwnerChip) in the context bar, and a
 * read-only banner (§8.15, adapted copy -- no "signed" language, since
 * finalize doesn't exist, and no "your access has been recorded" clause,
 * since no access-log table exists, per frontend/CLAUDE.md's explicit
 * instruction). Read is universal (Phase 13a): the banner is purely
 * informational and does not gate Explain/Compare, which any
 * authenticated doctor may use on any report regardless of ownership --
 * there is no edit/finalize control anywhere in this UI to disable in
 * the first place.
 */
export default function ReportWorkspacePage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;

  const [report, setReport] = useState<ReportDetailResponse | null>(null);
  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [railTab, setRailTab] = useState<"evidence" | "agreement" | "alternatives">("evidence");
  const [currentDoctorId, setCurrentDoctorId] = useState<string | null>(null);

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

  const reportOwnerId = report?.doctor_id ?? null;
  const isOwner = reportOwnerId !== null && currentDoctorId !== null && reportOwnerId === currentDoctorId;
  const otherOwnerName = useDoctorName(isOwner ? null : reportOwnerId);

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
            <Link href={`/patients/${patient.id}`} className="text-sm text-ink-2 underline">
              {patient.name} &middot; {patient.patient_code}
            </Link>
          ) : (
            <span className="text-sm text-ink-3">No patient linked to this report.</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <OwnerChip ownerId={reportOwnerId} currentDoctorId={currentDoctorId} />
          <StatusChip status={toChipReportStatus(report.status)} />
        </div>
      </div>

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
            <h2 className="text-eyebrow uppercase text-ink-3">
              AI Report &middot; {report.report_date}
            </h2>
          </div>
          <div className="flex flex-col divide-y divide-hairline p-card">
            {CONTENT_FIELDS.map(({ key, label }) => (
              <div key={key} className="py-3 first:pt-0 last:pb-0">
                <h3 className="text-h3 text-ink">{label}</h3>
                <p className="mt-1 text-report text-ink-2">{report.content[key] || "(none)"}</p>
              </div>
            ))}
          </div>

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
              className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md, "flex-1")}
            >
              Explain Report
            </Link>
            <Link
              href={`/reports/${reportId}/compare`}
              className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md, "flex-1")}
            >
              Compare Previous Report
            </Link>
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
    </div>
  );
}
