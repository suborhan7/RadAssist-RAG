"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  getCurrentDoctor,
  getDashboardStats,
  listReports,
} from "@/lib/api-client";
import { ScreenHeader } from "@/components/layout/screen-header";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
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
const LATE_AFTER_DAYS = 1;

/**
 * Dashboard -- "Reading queue" (design/github (1).md, isDashboard screen).
 * Ported to the Reading Room theme in the Phase-20 redesign step 4. The work
 * leads: one H1 stating what's owed, the oldest reachable in a single click, a
 * quiet row of throughput metrics, then the queue itself.
 *
 * Deliberate omissions vs the mock, kept as named omissions rather than faked
 * data: no accession/STUDY column (a report carries no accession field), no
 * "median edit" hero metric (never instrumented as an aggregate -- a per-row
 * edit % is computed client-side, but a true all-time median is not available),
 * and no system-status block (health lives on Login; the queue leads with work,
 * per the mock, which shows no status here).
 */
export default function DashboardPage() {
  const [now, setNow] = useState<Date | null>(null);
  const [doctorName, setDoctorName] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [recentReports, setRecentReports] = useState<ReportListItemResponse[] | null>(null);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    // Set on the client to avoid an SSR/CSR clock mismatch.
    setNow(new Date());

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

  const awaiting = stats?.awaiting_review ?? 0;
  const hasAwaiting = awaiting > 0;
  const oldestAge = stats?.oldest_awaiting_review_report_date
    ? daysAgo(stats.oldest_awaiting_review_report_date)
    : null;
  // The oldest report's patient name isn't on the stats payload; resolve it from
  // the recent list when present, otherwise show the waiting time alone.
  const oldestName =
    recentReports?.find((r) => r.report_id === stats?.oldest_awaiting_review_report_id)
      ?.patient_name ?? null;

  const firstName = doctorName ? doctorName.replace(/^Dr\.?\s+/i, "").split(" ")[0] : null;

  return (
    <>
      <ScreenHeader
        title="Reading queue"
        meta={now ? formatClock(now) : ""}
        actions={
          <div className="flex items-center gap-12">
            <Link href="/patients/search" className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md)}>
              Find patient
            </Link>
            <Link href="/patients/new" className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}>
              New examination
            </Link>
          </div>
        }
      />

      <div className="flex-1 overflow-auto px-30 pb-30 pt-34">
        <div className="mx-auto max-w-[1180px]">
          {/* Hero: what's owed, on the left; throughput metrics on the right. */}
          <div className="mb-34 flex flex-col gap-24 md:flex-row md:items-end md:gap-36">
            <div className="min-w-0 flex-1">
              {stats === null ? (
                <h1 className="text-page-title text-text-tertiary">
                  {statsError ? "Your reading queue" : "Loading your queue…"}
                </h1>
              ) : (
                <h1 className="text-page-title text-text-primary">
                  {hasAwaiting
                    ? `${awaiting} ${awaiting === 1 ? "report is" : "reports are"} waiting on you.`
                    : firstName
                      ? `Your queue is clear, ${firstName}.`
                      : "Your queue is clear."}
                </h1>
              )}

              {hasAwaiting && stats?.oldest_awaiting_review_report_id && (
                <div className="mt-14 flex flex-wrap items-center gap-14">
                  <Link
                    href={`/reports/${stats.oldest_awaiting_review_report_id}`}
                    className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}
                  >
                    Open the oldest
                  </Link>
                  {oldestAge !== null && (
                    <span className="text-sm text-amber">
                      {oldestName ? `${oldestName} · ` : ""}
                      waiting {oldestAge} {oldestAge === 1 ? "day" : "days"}
                    </span>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-none gap-34">
              <Metric value={stats?.examinations_today} label="examinations today" />
              <Metric value={stats?.my_reports} label="reports by you" />
              <Metric value={stats?.my_patients} label="patients reported" />
            </div>
          </div>

          {statsError && (
            <p className="mb-24 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {statsError}
            </p>
          )}

          {/* Queue table: PATIENT / WAITING / STATUS / EDITED / action.
              Fixed-width columns scroll horizontally on narrow viewports. */}
          <div className="overflow-x-auto">
            <div className="min-w-[720px] border-t border-hairline">
              <div className="grid grid-cols-[minmax(0,1.6fr)_130px_150px_100px_110px] gap-14 border-b border-hairline px-4 py-12 font-mono text-eyebrow uppercase text-text-tertiary">
                <span>Patient</span>
                <span>Waiting</span>
                <span>Status</span>
                <span>Edited</span>
                <span />
              </div>

              {recentError ? (
                <p className="px-4 py-16 text-sm text-amber">{recentError}</p>
              ) : recentReports === null ? (
                <p className="px-4 py-16 text-sm text-text-tertiary">Loading queue…</p>
              ) : recentReports.length === 0 ? (
                <p className="px-4 py-16 text-sm text-text-secondary">
                  No reports yet. Start a new examination to build the queue.
                </p>
              ) : (
                recentReports.map((item) => {
                  const chipStatus = toChipReportStatus(item.status);
                  const late = chipStatus === "draft" && daysAgo(item.created_at) >= LATE_AFTER_DAYS;
                  const editPercentage = computeReportDiff(
                    editableRecordFrom(item.ai_draft_content),
                    editableRecordFrom(item.content),
                  ).editPercentage;

                  return (
                    <Link
                      key={item.report_id}
                      href={`/reports/${item.report_id}`}
                      className="group grid grid-cols-[minmax(0,1.6fr)_130px_150px_100px_110px] items-center gap-14 border-b border-hairline px-4 py-14 transition-colors duration-hover last:border-0 hover:bg-bg-hover"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-base font-medium text-text-primary">
                          {item.patient_name ?? "No patient linked"}
                        </div>
                        {item.patient_code && (
                          <div className="mt-2 truncate font-mono text-mono-meta text-text-tertiary">
                            {item.patient_code}
                          </div>
                        )}
                      </div>
                      <div className={cn("text-sm", late ? "text-amber" : "text-text-secondary")}>
                        {relTime(item.created_at)}
                      </div>
                      <div>
                        <StatusChip status={chipStatus} />
                      </div>
                      <div className="font-mono text-sm text-text-secondary">
                        {editPercentage.toFixed(1)}%
                      </div>
                      <div className="text-right">
                        <span className="text-sm text-cyan transition-colors duration-hover group-hover:text-text-primary">
                          {rowAction(chipStatus)}
                        </span>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </div>

          {/* Ownership framing: taught through real registry arithmetic. Held
              back until the counts exist -- a half-empty sentence is noise. */}
          {stats && (
            <p className="mt-30 max-w-[56ch] text-sm leading-relaxed text-text-secondary">
              You have reported on{" "}
              <span className="text-text-primary">{stats.my_patients}</span>{" "}
              of the hospital&rsquo;s{" "}
              <span className="text-text-primary">{stats.total_patients}</span>{" "}
              registered patients. You can open any colleague&rsquo;s patient; you cannot open their
              unsigned drafts.
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function Metric({ value, label }: { value: number | undefined; label: string }) {
  return (
    <div>
      {value === undefined ? (
        // Static skeleton, sized to the number line. No shimmer -- the theme's
        // motion budget is spent elsewhere, and the "Loading" H1 carries intent.
        <div className="h-30 w-44 rounded-chip bg-bg-hover" aria-hidden />
      ) : (
        <div className="whitespace-nowrap font-mono text-metric-sm text-text-primary">{value}</div>
      )}
      <div className="mt-3 whitespace-nowrap text-caption text-text-secondary">{label}</div>
    </div>
  );
}

function rowAction(status: ReturnType<typeof toChipReportStatus>): string {
  switch (status) {
    case "draft":
      return "Review";
    case "final":
      return "Open";
    default:
      return "Resume";
  }
}

function daysAgo(dateOnly: string): number {
  const then = new Date(dateOnly.length <= 10 ? `${dateOnly}T00:00:00` : dateOnly).getTime();
  return Math.max(0, Math.round((Date.now() - then) / 86_400_000));
}

/** Compact "waiting" duration: 25 min | 3 hours | 2 days. */
function relTime(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (mins < 60) return `${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"}`;
  const days = Math.round(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"}`;
}

/** THU 31 JUL 2026 · 09:14 -- mono metadata in the screen header. */
function formatClock(d: Date): string {
  const date = d
    .toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric" })
    .toUpperCase()
    .replace(/,/g, "");
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  return `${date} · ${time}`;
}
