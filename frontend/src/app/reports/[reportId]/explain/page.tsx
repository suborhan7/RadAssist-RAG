"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, explainReport, getReport } from "@/lib/api-client";
import { StepProgress, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Explainability Chat (Phase 12 Step 6), launched from the Radiologist
 * Workspace's "Explain Report" action. Single-turn only, per Phase 10's
 * frozen design -- no conversation history/memory is sent to or kept by
 * the backend, so only the current question+answer pair is shown at a
 * time (not an accumulating thread), honestly reflecting that each
 * question is an independent call, not a continued conversation. A doctor
 * can still ask a second, separate question afterward -- that's a fresh
 * independent call, not a follow-up with memory of the first.
 *
 * Real loading state, not instant: this is another real LLM call with
 * real latency (Phase 10's own integration test measured this for real),
 * so it gets the same StepProgress treatment as Step 4's guided flow --
 * a single real stage, not a fake/instant assumption.
 *
 * Two distinct real backend error cases, not collapsed into one generic
 * failure message: a malformed/nonexistent report_id (404, Step 5's
 * established precedent) and a real LLM transport failure (502 -- found
 * and fixed as a genuine pre-existing gap in app/api/explainability.py
 * this same step, see that file's module docstring).
 */
export default function ExplainPage() {
  const params = useParams<{ reportId: string }>();
  const reportId = params.reportId;

  const [report, setReport] = useState<ReportDetailResponse | null>(null);
  const [reportLoadError, setReportLoadError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<"idle" | "asking" | "done" | "error">("idle");
  const [elapsedMs, setElapsedMs] = useState<number | undefined>(undefined);
  const [askedQuestion, setAskedQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    getReport(reportId)
      .then(setReport)
      .catch((err) => {
        setReportLoadError(err instanceof ApiError ? err.message : "Failed to load report.");
      });
  }, [reportId]);

  async function handleAsk(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;

    setStatus("asking");
    setErrorDetail(null);
    const start = performance.now();

    try {
      const result = await explainReport(reportId, question);
      setElapsedMs(performance.now() - start);
      setAskedQuestion(result.question);
      setAnswer(result.answer);
      setStatus("done");
      setQuestion("");
    } catch (err) {
      setStatus("error");
      if (err instanceof ApiError && err.status === 502) {
        setErrorDetail(`The AI assistant is temporarily unavailable (LLM transport failure): ${err.message}`);
      } else if (err instanceof ApiError && err.status === 404) {
        setErrorDetail(`Report not found: ${err.message}`);
      } else {
        setErrorDetail(err instanceof ApiError ? err.message : "Failed to get an answer.");
      }
    }
  }

  const stepDisplay: WorkflowStepDisplay = {
    id: "explaining",
    label: "Asking AI Assistant",
    status: status === "asking" ? "active" : status === "done" ? "done" : status === "error" ? "error" : "pending",
    elapsedMs: status === "done" ? elapsedMs : undefined,
    detail: status === "error" ? (errorDetail ?? undefined) : undefined,
  };

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-xl flex-col gap-6 px-6 py-16">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">Explain Report</h1>
          <Link href={`/reports/${reportId}`} className="text-sm text-zinc-500 underline dark:text-zinc-400">
            Back to Workspace
          </Link>
        </div>

        {/* Brief report context -- a doctor arriving here should see what they're asking about */}
        {reportLoadError && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {reportLoadError}
          </p>
        )}
        {report && (
          <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Report Context
            </h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              <span className="font-medium text-zinc-700 dark:text-zinc-300">Findings:</span> {report.content.findings}
            </p>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              <span className="font-medium text-zinc-700 dark:text-zinc-300">Impression:</span>{" "}
              {report.content.impression}
            </p>
          </section>
        )}

        {/* Question input */}
        <form onSubmit={handleAsk} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Ask a question about this report
            </span>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Why do you think this is pneumonia and not just a normal finding?"
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </label>
          <button
            type="submit"
            disabled={status === "asking" || !question.trim()}
            className="flex h-11 w-full items-center justify-center rounded-lg bg-black px-5 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Ask
          </button>
        </form>

        {status !== "idle" && <StepProgress steps={[stepDisplay]} />}

        {status === "done" && askedQuestion && answer && (
          <section className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Question
              </p>
              <p className="text-sm text-zinc-700 dark:text-zinc-300">{askedQuestion}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Answer
              </p>
              <p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{answer}</p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
