"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, explainReport, getReport } from "@/lib/api-client";
import { StepProgress, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Explainability (Phase 12 Step 6, restyled Phase 14 per
 * design_specification.md §8.13 -- frontend/CLAUDE.md cites this as §8.11,
 * a citation slip; §8.11 is actually "Questionnaire", a different screen).
 *
 * "Why it does not look like ChatGPT" (§8.13): no bubbles, no avatars, no
 * left/right alternation, no typing dots. The question renders as a bold
 * rule; the answer is plain prose in the document register. Kept as its
 * own route rather than converted into an actual overlay drawer over the
 * Workspace -- frontend/CLAUDE.md's Phase 14 scope is explicitly "styling
 * and interaction, not new routes," and turning a page navigation into an
 * in-place drawer is a real interaction/routing change, not a restyle;
 * the visual/typographic register described in §8.13 is applied without
 * that architectural change.
 *
 * The grounding notice is real, frozen copy (§8.13), not decoration --
 * it states an actual constraint on what the LLM was prompted to do
 * (app/services/prompt_builder.py's build_explanation_prompt), not an
 * aspirational claim.
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
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-xl flex-col gap-6 px-page py-16">
        <div className="flex items-center justify-between">
          <h1 className="text-h1 text-ink">Explainability</h1>
          <Link href={`/reports/${reportId}`} className="text-sm text-ink-3 underline">
            Back to Workspace
          </Link>
        </div>

        {reportLoadError && (
          <p className="rounded-card border border-critical-bd bg-critical-bg px-3 py-2 text-sm text-critical-ink">
            {reportLoadError}
          </p>
        )}

        {report && (
          <Card className="p-card">
            <h2 className="text-eyebrow uppercase text-ink-3">Report context</h2>
            <p className="mt-2 text-report text-ink-2">
              <span className="font-medium text-ink">Findings:</span> {report.content.findings}
            </p>
            <p className="mt-1 text-report text-ink-2">
              <span className="font-medium text-ink">Impression:</span> {report.content.impression}
            </p>
          </Card>
        )}

        {/* Non-dismissible grounding notice -- real constraint, not decoration */}
        <p className="rounded-card border border-steel-bd bg-steel-tint px-3 py-2 text-sm text-steel-ink">
          Answers are grounded in the retrieved cases and this report. The assistant cannot
          introduce new findings.
        </p>

        <form onSubmit={handleAsk} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-ink-2">Ask a question about this report</span>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Why do you think this is pneumonia and not just a normal finding?"
              className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
            />
          </label>
          <Button
            type="submit"
            variant="primary"
            size="lg"
            block
            disabled={status === "asking" || !question.trim()}
          >
            Ask
          </Button>
        </form>

        {status !== "idle" && <StepProgress steps={[stepDisplay]} />}

        {status === "done" && askedQuestion && answer && (
          <div className="flex flex-col gap-3 border-t border-hairline pt-4">
            <p className="text-h3 text-ink">{askedQuestion}</p>
            <p className="whitespace-pre-wrap text-report text-ink-2">{answer}</p>
          </div>
        )}
      </main>
    </div>
  );
}
