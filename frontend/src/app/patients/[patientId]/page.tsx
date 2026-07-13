"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getPatient, getPatientHistory } from "@/lib/api-client";
import type { paths } from "@/lib/generated/api";

type PatientResponse =
  paths["/patients/{patient_id}"]["get"]["responses"][200]["content"]["application/json"];
type PatientHistoryReportResponse =
  paths["/patients/{patient_id}/history"]["get"]["responses"][200]["content"]["application/json"][number];

/**
 * Patient Profile hub (Phase 12 Step 3) -- overview + chronological
 * history timeline + "New Examination" action, per the frozen spec's
 * Consolidation Decision 1 ("Patient Profile is the real hub, not a thin
 * intermediate page").
 *
 * Patient details fetch: GET /patients/{patient_id} (Phase 12, added this
 * step -- see backend/app/domain/interfaces.py's IPatientRepository
 * docstring for the full reasoning). Neither GET /patients/search (needs
 * a code or name+dob, not just an id) nor GET /patients/{id}/history
 * (report fields only, no patient details) could answer "get this
 * patient's own details from just their id," which this page needs to be
 * correct on a direct URL load, refresh, or bookmark -- not only when
 * arriving via in-app navigation that already has the data in hand.
 *
 * Timeline order: newest-first. GET /patients/{id}/history returns
 * ascending chronological order (oldest first, per Phase 11's
 * get_history() contract); reversed here for display since a doctor
 * returning to a patient almost always wants to see the most recent
 * visit first (the "most systems show newest first" convention), not
 * page down to it.
 *
 * "Compare with this report" (per frozen Consolidation Decision 8):
 * every entry EXCEPT the single most recent one gets this action, wired
 * to /reports/{mostRecentReportId}/compare?against={thisEntry.id} -- the
 * most recent report anchors the "current" side of the comparison (the
 * patient's latest state), and the clicked timeline entry supplies the
 * ?against= override (matching POST /comparisons' compare_against_report_id,
 * and the frozen folder structure's own comment: "compare/page.tsx
 * (accepts ?against=<report_id> from timeline)"). The most recent entry
 * itself has no button, since comparing it against itself is meaningless.
 */
export default function PatientProfilePage() {
  const params = useParams<{ patientId: string }>();
  const patientId = params.patientId;

  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [history, setHistory] = useState<PatientHistoryReportResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPatient(patientId), getPatientHistory(patientId)])
      .then(([patientResult, historyResult]) => {
        setPatient(patientResult);
        setHistory(historyResult);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.message
            : "Failed to load patient profile.",
        );
      });
  }, [patientId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
        <p className="rounded-md bg-red-50 px-4 py-3 text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      </div>
    );
  }

  if (!patient || !history) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
        <p className="text-zinc-500 dark:text-zinc-400">Loading patient profile...</p>
      </div>
    );
  }

  const mostRecentReport = history.length > 0 ? history[history.length - 1] : null;
  const newestFirst = [...history].reverse();

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col gap-8 px-6 py-16">
        {/* Overview */}
        <section className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">{patient.name}</h1>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-zinc-600 dark:text-zinc-400">
            <dt className="font-medium text-zinc-500 dark:text-zinc-500">Patient Code</dt>
            <dd className="font-mono">{patient.patient_code}</dd>
            <dt className="font-medium text-zinc-500 dark:text-zinc-500">Date of Birth</dt>
            <dd>{patient.date_of_birth}</dd>
            <dt className="font-medium text-zinc-500 dark:text-zinc-500">Gender</dt>
            <dd>{patient.gender}</dd>
          </dl>
        </section>

        {/* New Examination action */}
        <Link
          href={`/patients/${patientId}/upload`}
          className="flex h-14 w-full items-center justify-center rounded-lg bg-black px-5 text-base font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
        >
          New Examination
        </Link>

        {/* History timeline, newest first */}
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-black dark:text-zinc-50">History</h2>

          {newestFirst.length === 0 && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              No prior visits recorded for this patient yet.
            </p>
          )}

          {newestFirst.map((report) => {
            const isMostRecent = mostRecentReport !== null && report.id === mostRecentReport.id;
            return (
              <div
                key={report.id}
                className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    {new Date(report.created_at).toLocaleString()}
                  </span>
                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                    {report.status}
                  </span>
                </div>
                <p className="line-clamp-2 text-sm text-zinc-600 dark:text-zinc-400">
                  {report.ai_content.impression || "(no impression recorded)"}
                </p>
                <div className="flex gap-3 pt-1">
                  <Link
                    href={`/reports/${report.id}`}
                    className="text-sm font-medium text-black underline dark:text-zinc-50"
                  >
                    View Report
                  </Link>
                  {!isMostRecent && mostRecentReport && (
                    <Link
                      href={`/reports/${mostRecentReport.id}/compare?against=${report.id}`}
                      className="text-sm font-medium text-black underline dark:text-zinc-50"
                    >
                      Compare with this report
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      </main>
    </div>
  );
}
