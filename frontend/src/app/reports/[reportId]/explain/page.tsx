"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, explainReport, getReport } from "@/lib/api-client";
import { StepProgress, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/layout/screen-header";
import { useT } from "@/lib/i18n";
import type { paths } from "@/lib/generated/api";

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];

// Meta-questions about the grounding, not fabricated clinical facts -- they
// only prefill the input, which the doctor still sends (in the active language).
const SUGGESTED_QUESTION_KEYS = ["explain.q1", "explain.q2", "explain.q3"];

/**
 * Explainability (Phase 12 Step 6, restyled Phase 14 per
 * design_specification.md §8.13, ported to the Reading Room theme in the
 * redesign step 4).
 *
 * "Why it does not look like ChatGPT" (§8.13): no bubbles, no avatars, no
 * left/right alternation, no typing dots. The question renders as a bold
 * rule; the answer is plain prose in the document register. Single-turn: the
 * backend returns one {question, answer} per ask and persists it to the
 * explanations table, so the latest exchange is shown here and the copy about
 * the audit trail is literal, not aspirational. Kept as its own route rather
 * than an in-place drawer (a routing change, out of a restyle's scope).
 *
 * The grounding notice is real, frozen copy (§8.13) -- it states an actual
 * constraint on what the LLM was prompted to do
 * (app/services/prompt_builder.py's build_explanation_prompt), not decoration.
 * The cases rail reads report.retrieved_cases (real); the mock's per-sentence
 * "sentence in question" selection has no backend and is not attempted -- the
 * report impression stands in as the real anchoring text.
 */
export default function ExplainPage() {
  const { t } = useT();
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
        setReportLoadError(err instanceof ApiError ? err.message : t("workspace.errLoad"));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        setErrorDetail(t("explain.err502", { msg: err.message }));
      } else if (err instanceof ApiError && err.status === 404) {
        setErrorDetail(t("explain.err404", { msg: err.message }));
      } else {
        setErrorDetail(err instanceof ApiError ? err.message : t("explain.errGeneric"));
      }
    }
  }

  const stepDisplay: WorkflowStepDisplay = {
    id: "explaining",
    label: t("explain.stepAsking"),
    status: status === "asking" ? "active" : status === "done" ? "done" : status === "error" ? "error" : "pending",
    elapsedMs: status === "done" ? elapsedMs : undefined,
    detail: status === "error" ? (errorDetail ?? undefined) : undefined,
  };

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        {/* Leading back arrow, same control and position as every other screen. */}
        <BackLink href={`/reports/${reportId}`} labelKey="compare.backToWorkspace" />
        <h1 className="text-screen-title text-text-primary">{t("nav.explain")}</h1>
        <span className="flex-1" />
      </header>

      <div className="flex min-h-0 flex-1 overflow-x-auto">
        {/* Conversation column */}
        <div className="flex min-w-[420px] flex-1 flex-col">
          {/* Grounding notice -- real constraint on the prompt, not decoration */}
          <p className="flex-none border-b border-hairline px-30 py-16 text-sm leading-relaxed text-cyan">
            {t("explain.grounding")}
          </p>

          <div className="flex-1 overflow-auto px-30 py-30">
            <div className="mx-auto flex max-w-[70ch] flex-col gap-24">
              {reportLoadError && (
                <p className="rounded-field border border-amber-line bg-amber-wash px-14 py-12 text-sm text-amber">
                  {reportLoadError}
                </p>
              )}

              {status !== "idle" && <StepProgress steps={[stepDisplay]} />}

              {status === "done" && askedQuestion && answer ? (
                <article className="flex flex-col gap-16">
                  <div className="flex items-baseline gap-14 border-b border-strong pb-12">
                    <h2 className="text-panel text-text-primary">{askedQuestion}</h2>
                    <span className="flex-1" />
                    {elapsedMs !== undefined && (
                      <span className="whitespace-nowrap font-mono text-mono-meta text-text-tertiary">
                        {(elapsedMs / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap text-findings text-text-primary">{answer}</p>
                </article>
              ) : status === "idle" ? (
                <p className="text-findings text-text-tertiary">
                  {t("explain.idlePrompt")}
                </p>
              ) : null}
            </div>
          </div>

          {/* Ask footer */}
          <div className="flex-none border-t border-hairline px-30 py-18">
            {status !== "asking" && (
              <div className="mb-14 flex flex-wrap gap-9">
                {SUGGESTED_QUESTION_KEYS.map((key) => {
                  const q = t(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setQuestion(q)}
                      className="rounded-full border border-strong px-14 py-7 text-sm-tight text-text-secondary transition-colors duration-hover hover:border-cyan-line hover:text-cyan"
                    >
                      {q}
                    </button>
                  );
                })}
              </div>
            )}
            <form onSubmit={handleAsk} className="flex gap-12">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                aria-label={t("explain.ariaAsk")}
                placeholder={t("explain.placeholder")}
                className="h-46 flex-1 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted"
              />
              <Button type="submit" variant="primary" size="lg" disabled={status === "asking" || !question.trim()}>
                {t("explain.ask")}
              </Button>
            </form>
          </div>
        </div>

        {/* Cases-in-context rail */}
        <aside className="w-explain-panel flex-none overflow-auto border-l border-hairline bg-bg-raised p-22">
          {report && (
            <>
              <h3 className="mb-14 font-mono text-eyebrow uppercase text-text-tertiary">
                {t("explain.reportImpression")}
              </h3>
              <blockquote className="mb-28 border-l-2 border-cyan pl-16 text-findings text-text-primary">
                {report.content.impression || t("compare.none")}
              </blockquote>

              <h3 className="mb-14 font-mono text-eyebrow uppercase text-text-tertiary">
                {t("explain.casesInContext")}
              </h3>
              <div className="flex flex-col gap-16 border-t border-hairline pt-16">
                {report.retrieved_cases.map((c) => (
                  <div key={c.rank} className="flex items-baseline gap-10">
                    <span className="whitespace-nowrap font-mono text-mono-meta-lg text-cyan">
                      {(c.similarity * 100).toFixed(1)}
                    </span>
                    <span className="whitespace-nowrap font-mono text-mono-meta text-text-tertiary">
                      #{c.rank}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm text-text-secondary">
                      {c.primary_label}
                    </span>
                  </div>
                ))}
              </div>

              <p className="mt-24 text-caption leading-relaxed text-text-tertiary">
                {t("explain.auditNote")}
              </p>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
