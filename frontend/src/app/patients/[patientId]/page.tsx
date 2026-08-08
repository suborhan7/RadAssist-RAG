"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getCurrentDoctor, getPatient, getPatientHistory } from "@/lib/api-client";
import { StatusChip } from "@/components/ui/chip";
import { OwnerChip } from "@/components/ui/owner-chip";
import { toChipReportStatus } from "@/lib/report-status";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type PatientResponse =
  paths["/patients/{patient_id}"]["get"]["responses"][200]["content"]["application/json"];
type PatientHistoryReportResponse =
  paths["/patients/{patient_id}/history"]["get"]["responses"][200]["content"]["application/json"][number];

/**
 * Patient Profile hub (Phase 12 Step 3, ported to the Reading Room theme in
 * the redesign step 4) -- overview + chronological history timeline + "New
 * examination" action, per the frozen spec's Consolidation Decision 1
 * ("Patient Profile is the real hub, not a thin intermediate page").
 *
 * "Prior studies · same patient" is the load-bearing distinction the mock
 * copy makes: these are this patient over time, never the archive cases
 * (other patients' films) that only appear inside the workspace. Timeline
 * entries carry an OwnershipChip (Phase 15). Not built (no backing): per-row
 * film thumbnails/accession/projection, the §10.5 edit-percentage header, and
 * the access-log rail (no access-log table exists).
 */
export default function PatientProfilePage() {
  const params = useParams<{ patientId: string }>();
  const patientId = params.patientId;

  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [history, setHistory] = useState<PatientHistoryReportResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentDoctorId, setCurrentDoctorId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPatient(patientId), getPatientHistory(patientId)])
      .then(([patientResult, historyResult]) => {
        setPatient(patientResult);
        setHistory(historyResult);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load patient profile.");
      });
    getCurrentDoctor()
      .then((doctor) => setCurrentDoctorId(doctor?.id ?? null))
      .catch(() => setCurrentDoctorId(null));
  }, [patientId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-app p-30">
        <p className="rounded-field border border-amber-line bg-amber-wash px-16 py-12 text-sm text-amber">
          {error}
        </p>
      </div>
    );
  }

  if (!patient || !history) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-app">
        <p className="text-text-tertiary">Loading patient profile…</p>
      </div>
    );
  }

  // history is oldest -> newest (mostRecent is the last entry).
  const mostRecentReport = history.length > 0 ? history[history.length - 1] : null;
  const priorReport = history.length > 1 ? history[history.length - 2] : null;
  const newestFirst = [...history].reverse();
  const age = ageFromDob(patient.date_of_birth);
  const since = history.length > 0 ? monthYear(history[0].created_at) : null;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <Link
          href="/patients/search"
          className="text-sm text-text-tertiary transition-colors duration-hover hover:text-cyan"
        >
          Find patient
        </Link>
        <span className="text-text-muted">/</span>
        <h1 className="truncate text-screen-title text-text-primary">{patient.name}</h1>
        <span className="whitespace-nowrap font-mono text-mono-meta-lg text-text-tertiary">
          {patient.patient_code}
        </span>
        <span className="flex-1" />
        {mostRecentReport && priorReport && (
          <Link
            href={`/reports/${mostRecentReport.id}/compare?against=${priorReport.id}`}
            className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md)}
          >
            Compare latest two
          </Link>
        )}
        <Link
          href={`/patients/${patientId}/upload`}
          className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}
        >
          New examination
        </Link>
      </header>

      <div className="flex-1 overflow-auto px-30 py-34">
        <div className="mx-auto max-w-[1100px]">
          {/* Overview */}
          <div className="mb-34 flex flex-col gap-16 sm:flex-row sm:items-end sm:gap-44">
            <div className="min-w-0">
              <h2 className="text-page-title text-text-primary">{patient.name}</h2>
              <p className="mt-6 text-sm text-text-secondary">
                {age !== null ? `${age} years, ` : ""}
                {patient.gender} · born {patient.date_of_birth}
              </p>
            </div>
            <span className="hidden flex-1 sm:block" />
            <div className="flex-none">
              <div className="font-mono text-eyebrow uppercase text-text-tertiary">On record</div>
              <div className="mt-4 text-base text-text-primary">
                {history.length} {history.length === 1 ? "study" : "studies"}
                {since ? ` since ${since}` : ""}
              </div>
            </div>
          </div>

          {/* Prior studies timeline, newest first */}
          <div className="mb-8 font-mono text-eyebrow uppercase text-cyan">
            Prior studies · same patient
          </div>
          <div className="border-t border-hairline">
            {newestFirst.length === 0 && (
              <p className="py-20 text-sm text-text-tertiary">
                No prior visits recorded for this patient yet.
              </p>
            )}

            {newestFirst.map((report) => {
              const isMostRecent = mostRecentReport !== null && report.id === mostRecentReport.id;
              return (
                <div key={report.id} className="border-b border-hairline py-20">
                  <div className="mb-8 flex flex-wrap items-center gap-12">
                    <span className="font-mono text-sm font-medium text-text-primary">
                      {new Date(report.created_at).toLocaleString()}
                    </span>
                    <OwnerChip ownerId={report.doctor_id ?? null} currentDoctorId={currentDoctorId} />
                    <StatusChip status={toChipReportStatus(report.status)} />
                  </div>
                  <p className="line-clamp-2 max-w-[74ch] text-findings text-text-secondary">
                    {report.ai_content.impression || "(no impression recorded)"}
                  </p>
                  <div className="mt-12 flex flex-wrap items-center gap-18">
                    <Link
                      href={`/reports/${report.id}`}
                      className="text-sm text-cyan transition-colors duration-hover hover:text-text-primary"
                    >
                      Open report
                    </Link>
                    {!isMostRecent && mostRecentReport && (
                      <Link
                        href={`/reports/${mostRecentReport.id}/compare?against=${report.id}`}
                        className="text-sm text-cyan transition-colors duration-hover hover:text-text-primary"
                      >
                        Compare with this
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <p className="mt-24 max-w-[74ch] text-sm-tight leading-relaxed text-text-secondary">
            Prior studies are this patient over time. Archive cases, other patients&rsquo; films
            retrieved by similarity, never appear here; they exist only inside the workspace.
          </p>
        </div>
      </div>
    </div>
  );
}

function ageFromDob(dob: string): number | null {
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age -= 1;
  return age >= 0 && age < 200 ? age : null;
}

function monthYear(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { month: "short", year: "numeric" });
}
