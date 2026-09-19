"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import {
  ApiError,
  deleteReport,
  getCurrentDoctor,
  getDashboardStats,
  listReports,
} from "@/lib/api-client";
import { ScreenHeader } from "@/components/layout/screen-header";
import { BUTTON_BASE, SIZE, VARIANT } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/chip";
import { DiscardIcon } from "@/components/layout/rail-icons";
import { toChipReportStatus } from "@/lib/report-status";
import { computeReportDiff, editableRecordFrom } from "@/lib/report-diff";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type DashboardStatsResponse =
  paths["/dashboard/stats"]["get"]["responses"][200]["content"]["application/json"];
type ReportListItemResponse =
  paths["/reports"]["get"]["responses"][200]["content"]["application/json"][number];

/** The clock never changes after mount, so the store never notifies. */
const subscribeNever = () => () => {};

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
  const { t } = useT();
  // The header clock is client-only: rendering a time on the server and a
  // different one on the client is a hydration mismatch. This was previously a
  // setNow(new Date()) inside the mount effect, which is the pattern
  // react-hooks/set-state-in-effect rejects (it was failing lint at HEAD).
  // useSyncExternalStore's server snapshot is the supported way to say "this
  // value does not exist until hydration" without a render-triggering write.
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);
  const now = mounted ? new Date() : null;
  const [doctorName, setDoctorName] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [recentReports, setRecentReports] = useState<ReportListItemResponse[] | null>(null);
  const [recentError, setRecentError] = useState<string | null>(null);
  // Separate from recentError on purpose: recentError REPLACES the table (the
  // list could not be loaded, so there is nothing to show). A failed discard
  // must not do that -- the queue is still there and still readable, and
  // hiding eight rows because one delete was refused would be a worse outcome
  // than the failure itself.
  const [discardError, setDiscardError] = useState<string | null>(null);

  useEffect(() => {
    getCurrentDoctor()
      .then((doctor) => setDoctorName(doctor?.full_name ?? null))
      .catch(() => setDoctorName(null));

    getDashboardStats()
      .then(setStats)
      .catch((err) => {
        setStatsError(err instanceof ApiError ? err.message : t("dashboard.errStats"));
      });

    listReports(RECENT_ACTIVITY_LIMIT)
      .then(setRecentReports)
      .catch((err) => {
        setRecentError(err instanceof ApiError ? err.message : t("dashboard.errRecent"));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        title={t("dashboard.title")}
        meta={now ? formatClock(now) : ""}
        actions={
          <div className="flex items-center gap-12">
            <Link href="/patients/search" className={cn(BUTTON_BASE, VARIANT.secondary, SIZE.md)}>
              {t("nav.find")}
            </Link>
            <Link href="/patients/new" className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}>
              {t("nav.newExam")}
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
                  {statsError ? t("dashboard.queueFallback") : t("dashboard.queueLoading")}
                </h1>
              ) : (
                <h1 className="text-page-title text-text-primary">
                  {hasAwaiting
                    ? t("dashboard.awaiting", { count: awaiting })
                    : firstName
                      ? t("dashboard.clearNamed", { name: firstName })
                      : t("dashboard.clear")}
                </h1>
              )}

              {hasAwaiting && stats?.oldest_awaiting_review_report_id && (
                <div className="mt-14 flex flex-wrap items-center gap-14">
                  <Link
                    href={`/reports/${stats.oldest_awaiting_review_report_id}`}
                    className={cn(BUTTON_BASE, VARIANT.primary, SIZE.md)}
                  >
                    {t("dashboard.openOldest")}
                  </Link>
                  {oldestAge !== null && (
                    <span className="text-sm text-amber">
                      {oldestName ? `${oldestName} · ` : ""}
                      {t("dashboard.waitingDays", { count: oldestAge })}
                    </span>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-none gap-34">
              <Metric value={stats?.examinations_today} label={t("dashboard.examToday")} />
              <Metric value={stats?.my_reports} label={t("dashboard.reportsByYou")} />
              <Metric value={stats?.my_patients} label={t("dashboard.patientsReported")} />
            </div>
          </div>

          {statsError && (
            <p className="mb-24 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {statsError}
            </p>
          )}

          {discardError && (
            <p className="mb-16 rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {discardError}
            </p>
          )}

          {/* Queue table: PATIENT / WAITING / STATUS / EDITED / action.
              Fixed-width columns scroll horizontally on narrow viewports. */}
          <div className="overflow-x-auto">
            <div className="min-w-[790px] border-t border-hairline">
              <div className="grid grid-cols-[minmax(0,1.6fr)_120px_140px_90px_190px] gap-14 border-b border-hairline px-4 py-12 font-mono text-eyebrow uppercase text-text-tertiary">
                <span>{t("dashboard.colPatient")}</span>
                <span>{t("dashboard.colWaiting")}</span>
                <span>{t("dashboard.colStatus")}</span>
                <span>{t("dashboard.colEdited")}</span>
                <span />
              </div>

              {recentError ? (
                <p className="px-4 py-16 text-sm text-amber">{recentError}</p>
              ) : recentReports === null ? (
                <p className="px-4 py-16 text-sm text-text-tertiary">{t("dashboard.loadingQueue")}</p>
              ) : recentReports.length === 0 ? (
                <p className="px-4 py-16 text-sm text-text-secondary">
                  {t("dashboard.emptyQueue")}
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
                    // The row was a single <Link> wrapping every cell. Delete
                    // needs its own control, and an interactive element cannot
                    // nest inside an anchor, so the row is now a grid whose
                    // first cell carries a stretched link (::after covering the
                    // row) and whose delete button sits above it on z-10. The
                    // whole row still opens the report on click.
                    <div
                      key={item.report_id}
                      className="group relative grid grid-cols-[minmax(0,1.6fr)_120px_140px_90px_190px] items-center gap-14 border-b border-hairline px-4 py-14 transition-colors duration-hover last:border-0 hover:bg-bg-hover"
                    >
                      <div className="min-w-0">
                        <Link
                          href={`/reports/${item.report_id}`}
                          className="truncate text-base font-medium text-text-primary after:absolute after:inset-0 after:content-['']"
                        >
                          {item.patient_name ?? t("dashboard.noPatientLinked")}
                        </Link>
                        {item.patient_code && (
                          <div className="mt-2 truncate font-mono text-mono-meta text-text-tertiary">
                            {item.patient_code}
                          </div>
                        )}
                      </div>
                      <div className={cn("text-sm", late ? "text-amber" : "text-text-secondary")}>
                        {relTime(item.created_at, t)}
                      </div>
                      <div>
                        <StatusChip status={chipStatus} />
                      </div>
                      <div className="font-mono text-sm text-text-secondary">
                        {editPercentage.toFixed(1)}%
                      </div>
                      <div className="flex items-center justify-end gap-12">
                        <span className="text-sm text-cyan transition-colors duration-hover group-hover:text-text-primary">
                          {rowAction(chipStatus, t)}
                        </span>
                        {/* Finalized reports are signed records and the server
                            refuses to delete them (409), so the control is not
                            offered for one -- a button whose only outcome is a
                            rejection is worse than its absence. */}
                        {chipStatus !== "final" && (
                          <DeleteRowButton
                            reportId={item.report_id}
                            patientLabel={item.patient_name ?? item.patient_code ?? ""}
                            onDeleted={() => {
                              setRecentReports((prev) =>
                                (prev ?? []).filter((r) => r.report_id !== item.report_id),
                              );
                              setDiscardError(null);
                              // The metric tiles above are derived from the same
                              // reports this row was one of. Dropping the row
                              // without re-reading them would leave the count
                              // disagreeing with the list -- the exact defect
                              // this queue was reported for.
                              getDashboardStats().then(setStats).catch(() => {});
                            }}
                            onError={setDiscardError}
                          />
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Ownership framing: taught through real registry arithmetic. Held
              back until the counts exist -- a half-empty sentence is noise. */}
          {stats && (
            <p className="mt-30 max-w-[56ch] text-sm leading-relaxed text-text-secondary">
              {t("dashboard.ownership", { reported: stats.my_patients, total: stats.total_patients })}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

/**
 * Per-row discard. Two-step by design: the first press arms it, the second
 * confirms, and it disarms on blur or after a few seconds. A destructive
 * action reachable in one click, inside a row whose entire surface is already
 * a link to somewhere else, is a misclick waiting to happen -- and there is no
 * undo behind this, the report and its audit rows are gone.
 */
function DeleteRowButton({
  reportId,
  patientLabel,
  onDeleted,
  onError,
}: {
  reportId: string;
  patientLabel: string;
  onDeleted: () => void;
  onError: (message: string) => void;
}) {
  const { t } = useT();
  const [armed, setArmed] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(timer);
  }, [armed]);

  async function handleClick(event: React.MouseEvent) {
    // The row's stretched link would otherwise navigate on the same click.
    event.preventDefault();
    event.stopPropagation();

    if (!armed) {
      setArmed(true);
      return;
    }

    setDeleting(true);
    try {
      await deleteReport(reportId);
      onDeleted();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : t("dashboard.errDelete"));
      setArmed(false);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      onBlur={() => setArmed(false)}
      disabled={deleting}
      // The visible label is short enough for the column; the accessible name
      // says which row it belongs to, since "Discard" alone is ambiguous when
      // a screen reader reaches four of them in a row.
      aria-label={t("dashboard.deleteAria", { patient: patientLabel })}
      className={cn(
        // transition-colors alone was a bug: the hover reveal below animates
        // OPACITY, which transition-colors does not cover, so the control
        // snapped in instead of fading. Name the properties being animated.
        "relative z-10 flex items-center gap-6 rounded-chip px-8 py-4 text-sm",
        "transition-[opacity,color] duration-hover active:scale-[0.98]",
        armed
          ? "bg-amber-wash text-amber"
          : // Revealed on row hover so the queue stays calm, but ONLY where
            // hovering exists. On a touch screen there is no hover state, so an
            // opacity-0 default would make discard permanently unreachable --
            // the control would simply not be in the product on those devices.
            "text-text-muted hover:text-amber focus-visible:opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100",
        deleting && "opacity-50",
      )}
    >
      <DiscardIcon className="flex-none" />
      <span>{t(armed ? "dashboard.deleteConfirm" : "dashboard.delete")}</span>
    </button>
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

function rowAction(
  status: ReturnType<typeof toChipReportStatus>,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  switch (status) {
    case "draft":
      return t("dashboard.actionReview");
    case "final":
      return t("dashboard.actionOpen");
    default:
      return t("dashboard.actionResume");
  }
}

function daysAgo(dateOnly: string): number {
  const then = new Date(dateOnly.length <= 10 ? `${dateOnly}T00:00:00` : dateOnly).getTime();
  return Math.max(0, Math.round((Date.now() - then) / 86_400_000));
}

/** Compact "waiting" duration: 25 min | 3 hours | 2 days (units localized). */
function relTime(iso: string, t: (key: string, params?: Record<string, unknown>) => string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (mins < 60) return t("dashboard.unitMin", { count: mins });
  const hours = Math.round(mins / 60);
  if (hours < 24) return t("dashboard.unitHours", { count: hours });
  const days = Math.round(hours / 24);
  return t("dashboard.unitDays", { count: days });
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
