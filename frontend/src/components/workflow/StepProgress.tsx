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
      return <span className="text-stable">✓</span>;
    case "error":
      return <span className="text-critical">✗</span>;
    case "active":
      return (
        <span className="inline-block animate-spin text-ink-3" aria-hidden>
          ⏳
        </span>
      );
    case "skipped":
      return <span className="text-ink-3">⏭</span>;
    case "pending":
    default:
      return <span className="text-hairline-strong">○</span>;
  }
}

export function StepProgress({ steps }: { steps: WorkflowStepDisplay[] }) {
  return (
    <ol className="flex flex-col gap-2">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`flex items-center gap-3 rounded-card border px-3 py-2 ${
            step.status === "error"
              ? "border-critical-bd bg-critical-bg"
              : step.status === "active"
                ? "border-hairline-strong bg-sunken"
                : "border-hairline"
          }`}
        >
          <StatusIcon status={step.status} />
          <span className={step.status === "pending" ? "text-ink-3" : "text-ink"}>
            {step.label}
          </span>
          {step.status === "active" && (
            <span className="ml-auto text-xs text-ink-3">running...</span>
          )}
          {step.status === "done" && step.elapsedMs !== undefined && (
            <span className="ml-auto font-mono text-data-sm text-ink-3">
              {(step.elapsedMs / 1000).toFixed(1)}s
            </span>
          )}
          {step.status === "skipped" && <span className="ml-auto text-xs text-ink-3">skipped</span>}
          {step.status === "error" && step.detail && (
            <span className="ml-auto text-xs text-critical-ink">{step.detail}</span>
          )}
        </li>
      ))}
    </ol>
  );
}
