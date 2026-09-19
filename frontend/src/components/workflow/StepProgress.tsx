/**
 * components/workflow/StepProgress.tsx
 * ====================================================================
 * Explicit per-stage checkmark/spinner progress UI (frozen Phase 12
 * Decision 7/Consolidation 7), directly visualizing the real backend
 * pipeline stages rather than a generic "loading" indicator -- addresses
 * the real "doctor thinks it's hung" risk from measured multi-second-to-
 * multi-minute real latency (Phase 7: ~6s single generation; Phase 11's
 * chained integration test: 60s+).
 *
 * Purely presentational: elapsedMs (when present) is the REAL wall-clock
 * duration the calling page measured around its own real fetch/XHR call
 * for that stage, not a simulated or estimated value -- this component
 * only renders whatever real numbers it's given.
 *
 * Phase 14: this is design_specification.md's PipelineProgress primitive
 * (§7) -- spinner-to-check at 150ms, elapsed counting up in mono (§10.9's
 * "signature motion" -- the only place waiting is honest work).
 */
"use client";

import { useT } from "@/lib/i18n";

export type StepStatus = "pending" | "active" | "done" | "error" | "skipped";

export interface WorkflowStepDisplay {
  id: string;
  label: string;
  status: StepStatus;
  elapsedMs?: number;
  detail?: string;
}

function StatusIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "done":
      return <span className="text-cyan">✓</span>;
    case "error":
      return <span className="text-amber">✗</span>;
    case "active":
      // The one honest place waiting is work: a blinking cyan dot (rr-blink,
      // one of the theme's two sanctioned keyframes), not a novelty spinner.
      return <span className="inline-block h-8 w-8 animate-rr-blink rounded-full bg-cyan" aria-hidden />;
    case "skipped":
      return <span className="text-text-muted">⏭</span>;
    case "pending":
    default:
      return <span className="text-text-muted">○</span>;
  }
}

export function StepProgress({ steps }: { steps: WorkflowStepDisplay[] }) {
  const { t } = useT();
  return (
    <ol className="flex flex-col gap-8">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`flex items-center gap-12 rounded-field border px-14 py-12 ${
            step.status === "error"
              ? "border-amber-line bg-amber-wash"
              : step.status === "active"
                ? "border-strong bg-bg-hover"
                : "border-hairline"
          }`}
        >
          <StatusIcon status={step.status} />
          <span className={step.status === "pending" ? "text-text-tertiary" : "text-text-primary"}>
            {step.label}
          </span>
          {step.status === "active" && (
            <span className="ml-auto text-caption text-text-tertiary">{t("step.running")}</span>
          )}
          {step.status === "done" && step.elapsedMs !== undefined && (
            <span className="ml-auto font-mono text-sm text-text-tertiary">
              {(step.elapsedMs / 1000).toFixed(1)}s
            </span>
          )}
          {step.status === "skipped" && (
            <span className="ml-auto text-caption text-text-tertiary">{t("step.skipped")}</span>
          )}
          {step.status === "error" && step.detail && (
            <span className="ml-auto text-caption text-amber">{step.detail}</span>
          )}
        </li>
      ))}
    </ol>
  );
}
