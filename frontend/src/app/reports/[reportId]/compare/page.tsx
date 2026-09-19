"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, createComparison, getCurrentDoctor, getReport, retrievalSessionImageUrl } from "@/lib/api-client";
import { StepProgress, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import { OwnerChip } from "@/components/ui/owner-chip";
import { BackLink } from "@/components/layout/screen-header";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];
type ComparisonResponse =
  paths["/comparisons"]["post"]["responses"][200]["content"]["application/json"];

/**
 * Comparison Workspace (Phase 12 Step 7, restyled Phase 14 per
 * design_specification.md §8.14, ported to the Reading Room theme in the
 * redesign step 4).
 *
 * §8.14's provenance split is the load-bearing content: Resolved / Persistent
 * / New findings are computed by ComparisonService (deterministic); the
 * narrative is written by an LLM from that diff only. Both authorships stay
 * visible. ComparisonResponse carries no llm_model field (that's on a
 * different endpoint), so the caption says "an LLM", never a hardcoded model
 * name it doesn't actually carry. Linked pan/zoom sync (§8.14's PACS feel)
 * and the mock's per-region "new since" overlay are real viewer engineering,
 * not attempted here. The mock's side-by-side full-report dump is dropped in
 * favour of the impressions the mock actually shows; the full text stays one
 * click away in the workspace.
 */
export default function ComparePage() {
  const { t } = useT();
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
          setErrorDetail(err instanceof ApiError ? err.message : t("compare.errCurrent"));
        }
        return;
      }

      if (!current.patient_id) {
        setStatus("error");
        setErrorDetail(t("compare.errNoPatient"));
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
          setErrorDetail(err instanceof ApiError ? err.message : t("compare.errGenerate"));
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
          setErrorDetail(err instanceof ApiError ? err.message : t("compare.errPrevious"));
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId, against]);

  const stepDisplay: WorkflowStepDisplay = {
    id: "comparing",
    label: t("compare.stepGenerating"),
    status: status === "comparing" || status === "loading" ? "active" : status === "done" ? "done" : "error",
  };

  const header = (
    <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
      {/* Back moved from a trailing right-hand link to the leading arrow every
          screen now carries. One position, one behaviour -- a return control
          that sits somewhere different on each screen is the reason the
          workspace's was never found. */}
      <BackLink href={`/reports/${reportId}`} labelKey="compare.backToWorkspace" />
      <h1 className="text-screen-title text-text-primary">{t("nav.compare")}</h1>
      {status === "done" && comparison && (
        <span className="whitespace-nowrap font-mono text-mono-meta-lg uppercase text-text-tertiary">
          {t("compare.daysApart", { count: comparison.facts.days_between_studies })}
        </span>
      )}
      <span className="flex-1" />
      {/* Same discoverability fix as the workspace: the explainability screen
          exists, so say so from here. */}
      <Link
        href={`/reports/${reportId}/explain`}
        className="text-sm text-text-secondary transition-colors duration-hover hover:text-cyan"
      >
        {t("workspace.askAbout")}
      </Link>
    </header>
  );

  if (status === "error") {
    return (
      <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
        {header}
        <div className="flex flex-1 items-center justify-center p-30">
          <div className="flex w-full max-w-md flex-col gap-16">
            <StepProgress steps={[stepDisplay]} />
            <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
              {errorDetail}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status !== "done" || !comparison || !currentReport || !previousReport) {
    return (
      <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
        {header}
        <div className="flex flex-1 items-center justify-center p-30">
          <div className="w-full max-w-md">
            <StepProgress steps={[stepDisplay]} />
          </div>
        </div>
      </div>
    );
  }

  const days = comparison.facts.days_between_studies;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      {header}

      {/* Safety principle (Phase 11): the comparison is a draft for review. */}
      <div className="flex-none border-b border-hairline bg-amber-wash px-30 py-12 text-sm font-medium text-amber">
        {t("compare.reviewBanner")}
      </div>

      {/* Two studies, side by side */}
      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-auto lg:grid-cols-2">
        <StudyColumn
          eyebrow={t("compare.priorEyebrow", { date: previousReport.report_date })}
          eyebrowClass="text-text-tertiary"
          ownerId={previousReport.doctor_id ?? null}
          currentDoctorId={currentDoctorId}
          imageUrl={retrievalSessionImageUrl(previousReport.session_id)}
          imageAlt={t("compare.altPrior")}
          impression={previousReport.content.impression}
          impressionClass="text-text-secondary"
          className="border-b border-hairline lg:border-b-0 lg:border-r"
        />
        <StudyColumn
          eyebrow={t("compare.thisStudyEyebrow", { date: currentReport.report_date })}
          eyebrowClass="text-cyan"
          ownerId={currentReport.doctor_id ?? null}
          currentDoctorId={currentDoctorId}
          imageUrl={retrievalSessionImageUrl(currentReport.session_id)}
          imageAlt={t("compare.altCurrent")}
          impression={currentReport.content.impression}
          impressionClass="font-medium text-text-primary"
        />
      </div>

      {/* Provenance split: deterministic findings, then the model's narrative */}
      <div className="flex-none grid grid-cols-1 gap-24 border-t border-hairline px-30 py-22 md:grid-cols-2 lg:grid-cols-[150px_190px_240px_1fr]">
        <FindingsColumn label={t("compare.resolved")} items={comparison.facts.resolved_findings} />
        <FindingsColumn label={t("compare.persistent")} items={comparison.facts.persistent_findings} />
        <FindingsColumn label={t("compare.new")} items={comparison.facts.new_findings} accent />
        <div className="min-w-0">
          <h3 className="mb-8 font-mono text-eyebrow uppercase text-text-tertiary">
            {t("compare.narrativeHeading")}
          </h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
            {comparison.narrative}
          </p>
        </div>
      </div>

      <p className="flex-none border-t border-hairline px-30 py-12 text-caption text-text-tertiary">
        {t("compare.provenanceNote", { days })}
      </p>
    </div>
  );
}

function StudyColumn({
  eyebrow,
  eyebrowClass,
  ownerId,
  currentDoctorId,
  imageUrl,
  imageAlt,
  impression,
  impressionClass,
  className,
}: {
  eyebrow: string;
  eyebrowClass: string;
  ownerId: string | null;
  currentDoctorId: string | null;
  imageUrl: string;
  imageAlt: string;
  impression: string;
  impressionClass: string;
  className?: string;
}) {
  const { t } = useT();
  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div className="flex flex-none items-center gap-12 border-b border-hairline px-22 py-14">
        <span className={cn("font-mono text-eyebrow uppercase", eyebrowClass)}>{eyebrow}</span>
        <span className="flex-1" />
        <OwnerChip ownerId={ownerId} currentDoctorId={currentDoctorId} />
      </div>
      <div className="flex h-[300px] flex-none items-center justify-center on-film bg-bg-film p-16">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imageUrl} alt={imageAlt} className="max-h-full max-w-full object-contain" />
      </div>
      <div className="px-22 py-20">
        <h3 className="mb-8 font-mono text-eyebrow uppercase text-text-tertiary">{t("compare.impression")}</h3>
        <p className={cn("text-findings", impressionClass)}>{impression || t("compare.none")}</p>
      </div>
    </div>
  );
}

function FindingsColumn({ label, items, accent = false }: { label: string; items: string[]; accent?: boolean }) {
  const { t } = useT();
  return (
    <div className="min-w-0">
      <h3 className={cn("mb-8 font-mono text-eyebrow uppercase", accent ? "text-amber" : "text-text-tertiary")}>
        {label}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-text-muted">{t("compare.noneLower")}</p>
      ) : (
        <ul className="flex flex-col gap-4 text-sm">
          {items.map((item) => (
            <li key={item} className={accent ? "text-amber" : "text-text-primary"}>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
