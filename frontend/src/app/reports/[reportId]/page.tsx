"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getPatient, getReport } from "@/lib/api-client";
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
 * Radiologist Workspace (Phase 12 Step 5) -- the report is a workspace,
 * not a viewer (frozen Consolidation Decision 3): Explainability and
 * Comparison are actions launched FROM here, not separate, disconnected
 * features. Retrieved evidence is an accordion here, not a separate page
 * (Consolidation Decision 2).
 *
 * Report detail fetch: GET /reports/{report_id} (Phase 12, added this
 * step -- see backend/app/services/report_detail_service.py's module
 * docstring for the full "no endpoint existed" reasoning). Patient
 * details are then fetched via the already-existing GET /patients/{patient_id}
 * (Step 3) using the patient_id GET /reports/{report_id} resolves --
 * composing two existing/new endpoints rather than duplicating patient-
 * fetch logic into the new report endpoint.
 *
 * patient_id may be null (a report's session predates patient linkage, or
 * was never given one) -- handled explicitly, not assumed present.
 */
export default function ReportWorkspacePage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;

  const [report, setReport] = useState<ReportDetailResponse | null>(null);
  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReport(reportId)
      .then(async (reportResult) => {
        setReport(reportResult);
        if (reportResult.patient_id) {
          try {
            const patientResult = await getPatient(reportResult.patient_id);
            setPatient(patientResult);
          } catch {
            // Patient fetch failing independently shouldn't block showing
            // the report itself -- the workspace degrades to "no patient
            // info shown," not a hard error for the whole page.
            setPatient(null);
          }
        }
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load report.");
      });
  }, [reportId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
        <p className="rounded-md bg-red-50 px-4 py-3 text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
        <p className="text-zinc-500 dark:text-zinc-400">Loading report...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col gap-6 px-6 py-16">
        <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">Radiologist Workspace</h1>

        {/* Patient Information */}
        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Patient Information
          </h2>
          {patient ? (
            <div className="flex flex-col gap-1">
              <Link
                href={`/patients/${patient.id}`}
                className="font-medium text-black underline dark:text-zinc-50"
              >
                {patient.name}
              </Link>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {patient.patient_code} &middot; DOB {patient.date_of_birth} &middot; {patient.gender}
              </p>
            </div>
          ) : (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No patient linked to this report.</p>
          )}
        </section>

        {/* AI Report content */}
        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            AI Report ({report.status}, {report.report_date})
          </h2>
          <dl className="flex flex-col gap-3">
            {CONTENT_FIELDS.map(({ key, label }) => (
              <div key={key}>
                <dt className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</dt>
                <dd className="text-sm text-zinc-600 dark:text-zinc-400">
                  {report.content[key] || "(none)"}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Validation Warnings */}
        <section
          className={`rounded-lg border p-4 ${
            report.validation.is_clean
              ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950"
              : "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950"
          }`}
        >
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Validation
          </h2>
          {report.validation.is_clean ? (
            <p className="text-sm text-green-700 dark:text-green-300">No validation warnings.</p>
          ) : (
            <ul className="list-inside list-disc text-sm text-amber-800 dark:text-amber-300">
              {report.validation.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          )}
        </section>

        {/* Retrieved Evidence accordion (not a separate page) */}
        <details className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Retrieved Evidence ({report.retrieved_cases.length} cases)
          </summary>
          <div className="mt-3 flex flex-col gap-3">
            {report.retrieved_cases.map((c) => (
              <div
                key={c.rank}
                className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-800"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">
                    #{c.rank} &middot; {c.primary_label}
                  </span>
                  <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
                    similarity {c.similarity.toFixed(2)}
                  </span>
                </div>
                <p className="mt-1 text-zinc-600 dark:text-zinc-400">{c.findings}</p>
                <p className="text-zinc-600 dark:text-zinc-400">{c.impression}</p>
              </div>
            ))}
          </div>
        </details>

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          <Link
            href={`/reports/${reportId}/explain`}
            className="flex h-12 flex-1 items-center justify-center rounded-lg bg-black px-5 text-sm font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Explain Report
          </Link>
          <Link
            href={`/reports/${reportId}/compare`}
            className="flex h-12 flex-1 items-center justify-center rounded-lg border border-zinc-300 px-5 text-sm font-medium text-black transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-900"
          >
            Compare Previous Report
          </Link>
          <button
            type="button"
            disabled
            title="Out of scope for this thesis (frozen Phase 12 spec)"
            className="flex h-12 flex-1 items-center justify-center rounded-lg border border-zinc-200 px-5 text-sm font-medium text-zinc-400 dark:border-zinc-800 dark:text-zinc-600"
          >
            Download PDF
          </button>
        </div>
      </main>
    </div>
  );
}
