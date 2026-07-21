"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  getCurrentDoctor,
  getDashboardStats,
  getHealth,
  listReports,
} from "@/lib/api-client";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/chip";
import { toChipReportStatus } from "@/lib/report-status";
import { computeReportDiff, editableRecordFrom } from "@/lib/report-diff";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type DashboardStatsResponse =
  paths["/dashboard/stats"]["get"]["responses"][200]["content"]["application/json"];
type ReportListItemResponse =
  paths["/reports"]["get"]["responses"][200]["content"]["application/json"][number];

const RECENT_ACTIVITY_LIMIT = 8;

function daysAgo(dateOnly: string): number {
  const then = new Date(`${dateOnly}T00:00:00`).getTime();
  const now = new Date().getTime();
  return Math.max(0, Math.round((now - then) / 86_400_000));
}

/**
 * Dashboard (Phase 12 Step 2, real ownership counts added Phase 15,
 * rebuilt per design_specification.md §8.3 in Priority 4 of the
 * post-Phase-19 walkthrough fixes). Moved from `/` to `/dashboard` under
 * §16.1's reopening -- `/` is now the public Landing page (design spec
 * §8.1, previously specced but never built), so the authenticated home
 * needed its own path, matching how a real hospital platform separates
 * a public marketing entry point from the signed-in workspace.
 *
 * Zero charts, per §8.3's own stated test ("does this change what the
 * doctor does next?"). Agreement and a per-row generation-duration
 * column are deliberately NOT in the recent-activity table -- named
 * omissions, not oversights, see development_log.md's Priority 4 entry
 * for the real cost reasoning (agreement needs a live vector-store query
 * per report; generation duration was never instrumented anywhere).
 *
 * "Settings" no longer lives in Quick Actions -- moved into AppNavbar's
 * doctor menu (§16.1: a doctor's own profile/settings has no business
 * sitting next to clinical actions like "Register New Patient").
 */
export default function DashboardPage() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">(
    "checking",
  );
  const [doctorName, setDoctorName] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [recentReports, setRecentReports] = useState<ReportListItemResponse[] | null>(null);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then((response) => setBackendStatus(response.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));

    getCurrentDoctor()
      .then((doctor) => setDoctorName(doctor?.full_name ?? null))
      .catch(() => setDoctorName(null));

    getDashboardStats()
      .then(setStats)
      .catch((err) => {
        setStatsError(err instanceof ApiError ? err.message : "Failed to load dashboard stats.");
      });

    listReports(RECENT_ACTIVITY_LIMIT)
      .then(setRecentReports)
      .catch((err) => {
        setRecentError(err instanceof ApiError ? err.message : "Failed to load recent activity.");
      });
  }, []);

  const hasAwaitingReview = !!stats && stats.awaiting_review > 0;
  const oldestAge = stats?.oldest_awaiting_review_report_date
    ? daysAgo(stats.oldest_awaiting_review_report_date)
    : null;

  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-page py-16">
        {/* Greeting demoted to small/secondary text -- the work leads, per §8.3 */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-ink-2">
            {doctorName ? `Welcome back, ${doctorName}.` : "RadAssist-RAG"}
          </p>
        </div>

        {/* Work-queue H1 */}
        <div>
          {!stats ? (
            <h1 className="text-display text-ink-3">Loading...</h1>
          ) : hasAwaitingReview ? (
            <>
              <h1 className="text-display text-ink">
                {stats.awaiting_review} {stats.awaiting_review === 1 ? "report" : "reports"} awaiting
                your review
              </h1>
              {stats.oldest_awaiting_review_report_id && (
                <div className="mt-2 flex items-center gap-3">
                  <Link
                    href={`/reports/${stats.oldest_awaiting_review_report_id}`}
                    className="text-sm font-medium text-steel-ink underline decoration-steel-bd underline-offset-2 hover:text-steel"
                  >
                    Open oldest
                  </Link>
                  {oldestAge !== null && (
                    <span className="text-sm text-ink-3">
                      {oldestAge} {oldestAge === 1 ? "day" : "days"} old
                    </span>
                  )}
                </div>
              )}
            </>
          ) : (
            <h1 className="text-display text-ink">Your queue is clear.</h1>
          )}
        </div>

        {statsError && (
          <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {statsError}
          </p>
        )}

        {/* Four tiles */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Card>
            <CardBody className="text-center">
              <p className="text-eyebrow uppercase text-ink-3">Examinations today</p>
              <p className="mt-1 text-h1 text-ink">{stats?.examinations_today ?? "—"}</p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-eyebrow uppercase text-ink-3">Patients you&rsquo;ve reported</p>
              <p className="mt-1 text-h1 text-ink">
                {stats?.my_patients ?? "—"}{" "}
                <span className="text-sm font-normal text-ink-3">of {stats?.total_patients ?? "—"}</span>
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-eyebrow uppercase text-ink-3">Reports generated</p>
              <p className="mt-1 text-h1 text-ink">
                {stats?.my_reports ?? "—"}{" "}
                <span className="text-sm font-normal text-ink-3">of {stats?.total_reports ?? "—"}</span>
              </p>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="text-center">
              <p className="text-eyebrow uppercase text-ink-3">Awaiting review</p>
              <p className="mt-1 text-h1 text-ink">{stats?.awaiting_review ?? "—"}</p>
            </CardBody>
          </Card>
        </div>

        {/* Recent activity table -- patient, time, status, edited%. Deliberately
            NOT agreement/generated-time, see this file's own docstring. */}
        <Card>
          <CardHeader title="Your recent activity" />
          <CardBody className="p-0">
            {recentError ? (
              <p className="p-card text-sm text-critical-ink">{recentError}</p>
            ) : recentReports === null ? (
              <p className="p-card text-sm text-ink-3">Loading...</p>
            ) : recentReports.length === 0 ? (
              <p className="p-card text-sm text-ink-2">No reports yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-hairline text-eyebrow uppercase text-ink-3">
                      <th className="p-card py-2 font-medium">Patient</th>
                      <th className="p-card py-2 font-medium">Time</th>
                      <th className="p-card py-2 font-medium">Status</th>
                      <th className="p-card py-2 font-medium">Edited</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentReports.map((item) => {
                      const editPercentage = computeReportDiff(
                        editableRecordFrom(item.ai_draft_content),
                        editableRecordFrom(item.content),
                      ).editPercentage;
                      return (
                        <tr key={item.report_id} className="border-b border-hairline last:border-0">
                          <td className="p-card py-2">
                            <Link
                              href={`/reports/${item.report_id}`}
                              className="font-medium text-ink underline decoration-hairline-strong underline-offset-2 hover:text-steel-ink"
                            >
                              {item.patient_name ?? "No patient linked"}
                            </Link>
                            {item.patient_code && (
                              <span className="ml-1 text-ink-3">&middot; {item.patient_code}</span>
                            )}
                          </td>
                          <td className="p-card py-2 text-ink-2">
                            {new Date(item.created_at).toLocaleString()}
                          </td>
                          <td className="p-card py-2">
                            <StatusChip status={toChipReportStatus(item.status)} />
                          </td>
                          <td className="p-card py-2 font-mono text-data-sm text-ink-2">
                            {editPercentage.toFixed(1)}%
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Quick actions -- clinical actions only; Settings lives in AppNavbar's doctor menu */}
          <Card>
            <CardHeader title="Quick actions" />
            <CardBody className="flex flex-col gap-3">
              <Link
                href="/patients/search"
                className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md, "w-full")}
              >
                Find Patient
              </Link>
              <Link
                href="/patients/new"
                className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md, "w-full")}
              >
                Register New Patient
              </Link>
            </CardBody>
          </Card>

          {/* Registry card -- the ownership model taught through arithmetic,
              per §8.3, richer presentation than the compact tile above. */}
          <Card>
            <CardHeader title="Registry" />
            <CardBody className="flex flex-col gap-2">
              <p className="text-ink-2">
                You&rsquo;ve reported on{" "}
                <span className="font-medium text-ink">{stats?.my_patients ?? "—"}</span> of the{" "}
                hospital&rsquo;s <span className="font-medium text-ink">{stats?.total_patients ?? "—"}</span>{" "}
                registered patients.
              </p>
              <p className="text-ink-2">
                You&rsquo;ve generated{" "}
                <span className="font-medium text-ink">{stats?.my_reports ?? "—"}</span> of the{" "}
                registry&rsquo;s{" "}
                <span className="font-medium text-ink">{stats?.total_reports ?? "—"}</span> total
                reports.
              </p>
            </CardBody>
          </Card>
        </div>

        {/* System status -- reuses GET /health, already used on Login */}
        <Card>
          <CardHeader title="System status" />
          <CardBody>
            <div className="flex items-center gap-2 text-sm">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  backendStatus === "ok"
                    ? "bg-stable"
                    : backendStatus === "unreachable"
                      ? "bg-critical"
                      : "bg-ink-3",
                )}
              />
              <span className="text-ink-2">
                Backend:{" "}
                <span className="font-medium text-ink">
                  {backendStatus === "checking" ? "checking..." : backendStatus}
                </span>
              </span>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
