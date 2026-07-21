"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getCurrentDoctor, getPatient, getPatientHistory } from "@/lib/api-client";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
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
 * Patient Profile hub (Phase 12 Step 3, restyled Phase 14, given a real
 * context bar + Card-header structure by Priority 5 of the post-Phase-19
 * walkthrough fixes) -- overview + chronological history timeline + "New
 * Examination" action, per the frozen spec's Consolidation Decision 1
 * ("Patient Profile is the real hub, not a thin intermediate page") and
 * design_specification.md §8.7's "clinical hub" framing.
 *
 * Priority 5's real finding: a patient with few visits left this page
 * reading as unfinished -- a floating <h1> + a flat p-card div + a
 * separate full-width button, inside a min-h-screen/items-center shell
 * with nothing establishing it as an app page (contrast the Radiologist
 * Workspace's context bar, or this same shell's own top bar once
 * Priority 4 gave the Dashboard one). Fixed by giving this page the same
 * context-bar/CardHeader structure those pages already use -- not by
 * inventing content to fill the page, which this project's own
 * discipline rejects (§8.3's "does this change what the doctor does
 * next?" test applies here too).
 *
 * Timeline entries carry an OwnershipChip (Phase 15). The §10.5 "14% of
 * the AI draft was edited" edit-tracking header is still not built here
 * -- see this file's own history for why. Full access-log rail (§8.7)
 * also not built -- no access-log table exists.
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
        setError(
          err instanceof ApiError
            ? err.message
            : "Failed to load patient profile.",
        );
      });
    getCurrentDoctor()
      .then((doctor) => setCurrentDoctorId(doctor?.id ?? null))
      .catch(() => setCurrentDoctorId(null));
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
    <div className="flex min-h-screen flex-col bg-paper">
      {/* Context bar, matching the Radiologist Workspace's own pattern --
          this page previously had no app chrome at all above its content. */}
      <div className="flex h-context-bar items-center justify-between border-b border-hairline bg-surface px-page">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-sm text-ink-3 underline">
            Home
          </Link>
          <span className="text-ink-3">/</span>
          <h1 className="text-h3 text-ink">{patient.name}</h1>
        </div>
        <span className="font-mono text-sm text-ink-3">{patient.patient_code}</span>
      </div>

      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-page py-12">
        {/* Overview */}
        <Card>
          <CardHeader
            title={patient.name}
            sub={`${patient.patient_code} · ${history.length} ${history.length === 1 ? "visit" : "visits"} on record`}
            action={
              <Link
                href={`/patients/${patientId}/upload`}
                className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}
              >
                New Examination
              </Link>
            }
          />
          <CardBody>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-ink-2">
              <dt className="font-medium text-ink-3">Date of Birth</dt>
              <dd>{patient.date_of_birth}</dd>
              <dt className="font-medium text-ink-3">Gender</dt>
              <dd>{patient.gender}</dd>
            </dl>
          </CardBody>
        </Card>

        {/* History timeline, newest first */}
        <Card>
          <CardHeader title="History" sub="Newest first" />
          <CardBody className="flex flex-col gap-3">
            {newestFirst.length === 0 && (
              <p className="text-sm text-ink-3">No prior visits recorded for this patient yet.</p>
            )}

            {newestFirst.map((report) => {
              const isMostRecent = mostRecentReport !== null && report.id === mostRecentReport.id;
              return (
                <div
                  key={report.id}
                  className="flex flex-col gap-2 rounded-card border border-hairline p-tight"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-ink">
                      {new Date(report.created_at).toLocaleString()}
                    </span>
                    <div className="flex items-center gap-2">
                      <OwnerChip ownerId={report.doctor_id ?? null} currentDoctorId={currentDoctorId} />
                      <StatusChip status={toChipReportStatus(report.status)} />
                    </div>
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
                </div>
              );
            })}
          </CardBody>
        </Card>
      </main>
    </div>
  );
}
