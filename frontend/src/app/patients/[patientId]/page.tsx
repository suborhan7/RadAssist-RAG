"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getPatient, getPatientHistory } from "@/lib/api-client";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/chip";
import { toChipReportStatus } from "@/lib/report-status";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type PatientResponse =
  paths["/patients/{patient_id}"]["get"]["responses"][200]["content"]["application/json"];
type PatientHistoryReportResponse =
  paths["/patients/{patient_id}/history"]["get"]["responses"][200]["content"]["application/json"][number];

/**
 * Patient Profile hub (Phase 12 Step 3, restyled Phase 14) -- overview +
 * chronological history timeline + "New Examination" action, per the
 * frozen spec's Consolidation Decision 1 ("Patient Profile is the real
 * hub, not a thin intermediate page") and design_specification.md §8.7's
 * "clinical hub" framing. Full ownership/access-log rail (§8.7) and the
 * §10.5 "14% of the AI draft was edited" edit-tracking header are not
 * built here -- both depend on data this system doesn't have yet
 * (doctor_id is tagged at creation per Phase 13a, but no UI reads it
 * anywhere yet; edit tracking needs a doctor-edit workflow that doesn't
 * exist, see Phase 13a's documented finalize/edit/regenerate gap).
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
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="rounded-card border border-critical-bd bg-critical-bg px-4 py-3 text-critical-ink">
          {error}
        </p>
      </div>
    );
  }

  if (!patient || !history) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="text-ink-3">Loading patient profile...</p>
      </div>
    );
  }

  const mostRecentReport = history.length > 0 ? history[history.length - 1] : null;
  const newestFirst = [...history].reverse();

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-2xl flex-col gap-8 px-page py-16">
        {/* Overview */}
        <Card className="flex flex-col gap-2 p-card">
          <h1 className="text-h1 text-ink">{patient.name}</h1>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-ink-2">
            <dt className="font-medium text-ink-3">Patient Code</dt>
            <dd className="font-mono">{patient.patient_code}</dd>
            <dt className="font-medium text-ink-3">Date of Birth</dt>
            <dd>{patient.date_of_birth}</dd>
            <dt className="font-medium text-ink-3">Gender</dt>
            <dd>{patient.gender}</dd>
          </dl>
        </Card>

        {/* New Examination action */}
        <Link
          href={`/patients/${patientId}/upload`}
          className={cn(BUTTON_BASE, VARIANT.primary, SIZE.lg, "w-full")}
        >
          New Examination
        </Link>

        {/* History timeline, newest first */}
        <section className="flex flex-col gap-3">
          <h2 className="text-h2 text-ink">History</h2>

          {newestFirst.length === 0 && (
            <p className="text-sm text-ink-3">No prior visits recorded for this patient yet.</p>
          )}

          {newestFirst.map((report) => {
            const isMostRecent = mostRecentReport !== null && report.id === mostRecentReport.id;
            return (
              <Card key={report.id} className="flex flex-col gap-2 p-card">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink">
                    {new Date(report.created_at).toLocaleString()}
                  </span>
                  <StatusChip status={toChipReportStatus(report.status)} />
                </div>
                <p className="line-clamp-2 text-sm text-ink-2">
                  {report.ai_content.impression || "(no impression recorded)"}
                </p>
                <div className="flex gap-3 pt-1">
                  <Link href={`/reports/${report.id}`} className="text-sm font-medium text-ink underline">
                    View Report
                  </Link>
                  {!isMostRecent && mostRecentReport && (
                    <Link
                      href={`/reports/${mostRecentReport.id}/compare?against=${report.id}`}
                      className="text-sm font-medium text-ink underline"
                    >
                      Compare with this report
                    </Link>
                  )}
                </div>
              </Card>
            );
          })}
        </section>
      </main>
    </div>
  );
}
