"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, createComparison, getReport, retrievalSessionImageUrl } from "@/lib/api-client";
import { StepProgress, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];
type ComparisonResponse =
  paths["/comparisons"]["post"]["responses"][200]["content"]["application/json"];

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
 * Comparison page (Phase 12 Step 7) -- the phase's centerpiece, the UI
 * most directly demonstrating Phase 11's actual novelty. Full side-by-side
 * layout per the frozen spec's Consolidation Decision 5: previous X-ray +
 * current X-ray, previous report + current report, resolved/persistent/
 * new findings clearly sectioned, AI narrative, and an explicit "Doctor
 * Review Required" line -- the visual enforcement of Phase 11's own
 * safety principle (a comparison narrative is a draft requiring review,
 * never a final verdict), not optional polish.
 *
 * [reportId] (route) is the CURRENT report -- the anchor. ?against=
 * (query, optional) is the explicit previous-report override, present
 * when arriving from the Patient Profile timeline's "Compare with this
 * report" action; absent when arriving from this same report's own
 * Workspace "Compare Previous Report" button, which relies on the
 * backend's default-to-most-recent-prior resolution.
 *
 * Images: GET /reports/{report_id} (Step 5) gives each side's session_id;
 * GET /retrieval-sessions/{session_id}/image (Step 7 prerequisite fix)
 * serves each side's real, masked X-ray directly as an <img src=...>.
 *
 * Two real, distinct 404 failure modes are shown as the backend
 * describes them, not collapsed into one generic error (see
 * api-client.ts's createComparison docstring): NoPriorReportError
 * ("No prior report available: ...") and ReportNotFoundError ("Report
 * not found: ...").
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
    // No `detail` here on error -- the dedicated error message box below
    // already shows the full text; repeating it in the step row too was
    // pure redundancy.
  };

  if (status === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
        <main className="flex w-full max-w-md flex-col gap-4 px-6 py-16">
          <StepProgress steps={[stepDisplay]} />
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {errorDetail}
          </p>
          <Link href={`/reports/${reportId}`} className="text-sm text-zinc-500 underline dark:text-zinc-400">
            Back to Workspace
          </Link>
        </main>
      </div>
    );
  }

  if (status !== "done" || !comparison || !currentReport || !previousReport) {
    return (
      <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
        <main className="flex w-full max-w-md flex-col gap-4 px-6 py-16">
          <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">Comparison</h1>
          <StepProgress steps={[stepDisplay]} />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-5xl flex-col gap-6 px-6 py-16">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">Comparison</h1>
          <Link href={`/reports/${reportId}`} className="text-sm text-zinc-500 underline dark:text-zinc-400">
            Back to Workspace
          </Link>
        </div>

        {/* Doctor Review Required -- visual enforcement of Phase 11's safety principle */}
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          Doctor Review Required -- this AI-generated comparison is a draft, not a final verdict.
        </div>

        {/* Side-by-side X-rays */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Previous X-ray ({previousReport.report_date})
            </h2>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={retrievalSessionImageUrl(previousReport.session_id)}
              alt="Previous chest X-ray"
              className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800"
            />
          </div>
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Current X-ray ({currentReport.report_date})
            </h2>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={retrievalSessionImageUrl(currentReport.session_id)}
              alt="Current chest X-ray"
              className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800"
            />
          </div>
        </div>

        {/* Side-by-side reports */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[
            { label: "Previous Report", content: previousReport.content },
            { label: "Current Report", content: currentReport.content },
          ].map(({ label, content }) => (
            <div
              key={label}
              className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {label}
              </h2>
              <dl className="flex flex-col gap-2">
                {CONTENT_FIELDS.map(({ key, label: fieldLabel }) => (
                  <div key={key}>
                    <dt className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{fieldLabel}</dt>
                    <dd className="text-sm text-zinc-700 dark:text-zinc-300">{content[key] || "(none)"}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>

        {/* Resolved / Persistent / New findings */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            { label: "Resolved Findings", items: comparison.facts.resolved_findings, color: "green" },
            { label: "Persistent Findings", items: comparison.facts.persistent_findings, color: "amber" },
            { label: "New Findings", items: comparison.facts.new_findings, color: "red" },
          ].map(({ label, items, color }) => (
            <div
              key={label}
              className={`rounded-lg border p-4 ${
                color === "green"
                  ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950"
                  : color === "amber"
                    ? "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950"
                    : "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950"
              }`}
            >
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                {label}
              </h3>
              {items.length === 0 ? (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">(none)</p>
              ) : (
                <ul className="list-inside list-disc text-sm text-zinc-700 dark:text-zinc-300">
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        <p className="-mt-2 text-xs text-zinc-500 dark:text-zinc-400">
          Days between studies: {comparison.facts.days_between_studies}
        </p>

        {/* AI comparison narrative */}
        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            AI Comparison Narrative
          </h2>
          <p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
            {comparison.narrative}
          </p>
        </section>
      </main>
    </div>
  );
}
