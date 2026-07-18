"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, createComparison, getCurrentDoctor, getReport, retrievalSessionImageUrl } from "@/lib/api-client";
import { StepProgress, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import { Card } from "@/components/ui/card";
import { OwnerChip } from "@/components/ui/owner-chip";
import { REPORT_CONTENT_FIELDS as CONTENT_FIELDS } from "@/components/report/report-document-view";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];
type ComparisonResponse =
  paths["/comparisons"]["post"]["responses"][200]["content"]["application/json"];

/**
 * Comparison Workspace (Phase 12 Step 7, restyled Phase 14 per
 * design_specification.md §8.14 -- frontend/CLAUDE.md cites this as
 * §8.12, a citation slip; §8.12 is actually "Radiologist Workspace", a
 * different screen).
 *
 * §8.14's provenance split is the content addition this phase makes:
 * "Computed by ComparisonService · Deterministic" under the diff,
 * "Narrative generated ... from the deterministic diff above" under the
 * narrative. ComparisonResponse carries no llm_model field (that's only
 * on GenerateReportResponse's generation_metadata, a different endpoint),
 * so the caption says "an LLM", not a specific hardcoded model name --
 * asserting a model this response never actually names would be a small
 * fabrication, not a styling choice.
 *
 * Linked-viewer pan/zoom synchronisation (§8.14's "single behaviour that
 * makes this feel like PACS") is real image-viewer engineering, not
 * attempted here -- flagged rather than silently dropped.
 */
export default function ComparePage() {
  const params = useParams<{ reportId: string }>();
  const searchParams = useSearchParams();
  const reportId = params.reportId;
  const against = searchParams.get("against");

  const [currentReport, setCurrentReport] = useState<ReportDetailResponse | null>(null);
  const [previousReport, setPreviousReport] = useState<ReportDetailResponse | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "comparing" | "done" | "error">("loading");
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [currentDoctorId, setCurrentDoctorId] = useState<string | null>(null);

  useEffect(() => {
    getCurrentDoctor()
      .then((doctor) => setCurrentDoctorId(doctor?.id ?? null))
      .catch(() => setCurrentDoctorId(null));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      let current: ReportDetailResponse;
      try {
        current = await getReport(reportId);
        if (cancelled) return;
        setCurrentReport(current);
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setErrorDetail(err instanceof ApiError ? err.message : "Failed to load current report.");
        }
        return;
      }

      if (!current.patient_id) {
        setStatus("error");
        setErrorDetail("This report has no patient linked -- cannot compare against patient history.");
        return;
      }

      setStatus("comparing");
      let comparisonResult: ComparisonResponse;
      try {
        comparisonResult = await createComparison({
          patient_id: current.patient_id,
          current_report_id: reportId,
          compare_against_report_id: against,
        });
        if (cancelled) return;
        setComparison(comparisonResult);
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setErrorDetail(err instanceof ApiError ? err.message : "Failed to generate comparison.");
        }
        return;
      }

      try {
        const previous = await getReport(comparisonResult.previous_report_id);
        if (cancelled) return;
        setPreviousReport(previous);
        setStatus("done");
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setErrorDetail(err instanceof ApiError ? err.message : "Failed to load previous report.");
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [reportId, against]);

  const stepDisplay: WorkflowStepDisplay = {
    id: "comparing",
    label: "Generating Comparison",
    status: status === "comparing" || status === "loading" ? "active" : status === "done" ? "done" : "error",
  };

  if (status === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center bg-paper">
        <main className="flex w-full max-w-md flex-col gap-4 px-page py-16">
          <StepProgress steps={[stepDisplay]} />
          <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {errorDetail}
          </p>
          <Link href={`/reports/${reportId}`} className="text-sm text-ink-3 underline">
            Back to Workspace
          </Link>
        </main>
      </div>
    );
  }

  if (status !== "done" || !comparison || !currentReport || !previousReport) {
    return (
      <div className="flex min-h-screen flex-col items-center bg-paper">
        <main className="flex w-full max-w-md flex-col gap-4 px-page py-16">
          <h1 className="text-h1 text-ink">Comparison</h1>
          <StepProgress steps={[stepDisplay]} />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-page py-16">
        <div className="flex items-center justify-between">
          <h1 className="text-h1 text-ink">Comparison</h1>
          <Link href={`/reports/${reportId}`} className="text-sm text-ink-3 underline">
            Back to Workspace
          </Link>
        </div>

        {/* Doctor Review Required -- visual enforcement of Phase 11's safety principle */}
        <div className="rounded-card border border-caution-bd bg-caution-bg px-4 py-3 text-sm font-semibold text-caution-ink">
          Doctor Review Required -- this AI-generated comparison is a draft, not a final verdict.
        </div>

        {/* Side-by-side X-rays, in the lightbox register */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <h2 className="text-eyebrow uppercase text-ink-3">
                Previous X-ray ({previousReport.report_date})
              </h2>
              <OwnerChip ownerId={previousReport.doctor_id ?? null} currentDoctorId={currentDoctorId} />
            </div>
            <div className="flex items-center justify-center rounded-card bg-lightbox p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={retrievalSessionImageUrl(previousReport.session_id)}
                alt="Previous chest X-ray"
                className="max-h-96 w-full object-contain"
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <h2 className="text-eyebrow uppercase text-ink-3">
                Current X-ray ({currentReport.report_date})
              </h2>
              <OwnerChip ownerId={currentReport.doctor_id ?? null} currentDoctorId={currentDoctorId} />
            </div>
            <div className="flex items-center justify-center rounded-card bg-lightbox p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={retrievalSessionImageUrl(currentReport.session_id)}
                alt="Current chest X-ray"
                className="max-h-96 w-full object-contain"
              />
            </div>
          </div>
        </div>

        {/* Side-by-side reports */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[
            { label: "Previous Report", content: previousReport.content },
            { label: "Current Report", content: currentReport.content },
          ].map(({ label, content }) => (
            <Card key={label} className="p-card">
              <h2 className="mb-2 text-eyebrow uppercase text-ink-3">{label}</h2>
              <dl className="flex flex-col gap-2">
                {CONTENT_FIELDS.map(({ key, label: fieldLabel }) => (
                  <div key={key}>
                    <dt className="text-xs font-medium text-ink-3">{fieldLabel}</dt>
                    <dd className="text-report text-ink-2">{content[key] || "(none)"}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          ))}
        </div>

        {/* Resolved / Persistent / New findings -- text labels, never colour alone */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            {
              label: "Resolved Findings",
              items: comparison.facts.resolved_findings,
              border: "border-stable-bd",
              bg: "bg-stable-bg",
              ink: "text-stable-ink",
            },
            {
              label: "Persistent Findings",
              items: comparison.facts.persistent_findings,
              border: "border-caution-bd",
              bg: "bg-caution-bg",
              ink: "text-caution-ink",
            },
            {
              label: "New Findings",
              items: comparison.facts.new_findings,
              border: "border-critical-bd",
              bg: "bg-critical-bg",
              ink: "text-critical-ink",
            },
          ].map(({ label, items, border, bg, ink }) => (
            <div key={label} className={`rounded-card border ${border} ${bg} p-card`}>
              <h3 className={`mb-2 text-eyebrow uppercase ${ink}`}>{label}</h3>
              {items.length === 0 ? (
                <p className="text-sm text-ink-3">(none)</p>
              ) : (
                <ul className="list-inside list-disc text-sm text-ink">
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        {/* Provenance split: the diff's authorship is public (§8.14) */}
        <p className="-mt-2 text-xs text-ink-3">
          Computed by ComparisonService &middot; Deterministic. Days between studies:{" "}
          {comparison.facts.days_between_studies}.
        </p>

        {/* AI comparison narrative */}
        <Card className="p-card">
          <h2 className="mb-2 text-eyebrow uppercase text-ink-3">AI Comparison Narrative</h2>
          <p className="whitespace-pre-wrap text-report text-ink-2">{comparison.narrative}</p>
          <p className="mt-3 rounded-card bg-sunken p-tight text-sm text-ink-2">
            Narrative generated by an LLM from the deterministic diff above. The diff itself is
            not decided by the model -- it is computed by ComparisonService and passed to the
            LLM only to be described in prose.
          </p>
        </Card>
      </main>
    </div>
  );
}
