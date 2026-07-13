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
      return <span className="text-green-600 dark:text-green-500">✓</span>;
    case "error":
      return <span className="text-red-600 dark:text-red-500">✗</span>;
    case "active":
      return (
        <span className="inline-block animate-spin text-zinc-500 dark:text-zinc-400" aria-hidden>
          ⏳
        </span>
      );
    case "skipped":
      return <span className="text-zinc-400 dark:text-zinc-600">⏭</span>;
    case "pending":
    default:
      return <span className="text-zinc-300 dark:text-zinc-700">○</span>;
  }
}

export function StepProgress({ steps }: { steps: WorkflowStepDisplay[] }) {
  return (
    <ol className="flex flex-col gap-2">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`flex items-center gap-3 rounded-md border px-3 py-2 ${
            step.status === "error"
              ? "border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950"
              : step.status === "active"
                ? "border-zinc-300 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900"
                : "border-zinc-200 dark:border-zinc-800"
          }`}
        >
          <StatusIcon status={step.status} />
          <span
            className={
              step.status === "pending"
                ? "text-zinc-400 dark:text-zinc-600"
                : "text-zinc-800 dark:text-zinc-200"
            }
          >
            {step.label}
          </span>
          {step.status === "active" && (
            <span className="ml-auto text-xs text-zinc-500 dark:text-zinc-400">running...</span>
          )}
          {step.status === "done" && step.elapsedMs !== undefined && (
            <span className="ml-auto text-xs font-mono text-zinc-500 dark:text-zinc-400">
              {(step.elapsedMs / 1000).toFixed(1)}s
            </span>
          )}
          {step.status === "skipped" && (
            <span className="ml-auto text-xs text-zinc-400 dark:text-zinc-600">skipped</span>
          )}
          {step.status === "error" && step.detail && (
            <span className="ml-auto text-xs text-red-600 dark:text-red-400">{step.detail}</span>
          )}
        </li>
      ))}
    </ol>
  );
}
