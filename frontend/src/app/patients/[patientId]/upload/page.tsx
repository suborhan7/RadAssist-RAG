"use client";

import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import {
  ApiError,
  generateReport,
  getQuestionnaire,
  retrieveWithProgress,
} from "@/lib/api-client";
import { StepProgress, type StepStatus, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import type { paths } from "@/lib/generated/api";

type QuestionnaireResponse =
  paths["/questionnaire/{session_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Upload -> Retrieval -> Questionnaire -> Generate (Phase 12 Step 4), one
 * guided flow per the frozen spec -- not separate routes, since a doctor
 * experiences this as one continuous action.
 *
 * WorkflowStep progress states are wired to the REAL backend calls this
 * page makes, not simulated timing: "uploading" and "retrieving_evidence"
 * are two real, browser-reported milestones within the SAME real
 * POST /retrieve XHR (see retrieveWithProgress's own docstring for why
 * XHR, not fetch, is used here), "running_questionnaire" covers the real
 * GET /questionnaire/{session_id} call plus however long the doctor takes
 * filling it in (a real elapsed duration, not fake), and
 * "generating_report" covers the real POST /generate-report call --
 * exactly the latency Phase 7 (~6s single generation) and Phase 11
 * (60s+ chained) measured, made visible per-stage rather than hidden
 * behind one generic spinner.
 *
 * Questionnaire is genuinely optional (frozen Phase 9 design) -- "Skip
 * Questionnaire" proceeds straight to generation with
 * questionnaire_answers: null, exercised for real below.
 */
type WorkflowStepId = "uploading" | "retrieving_evidence" | "running_questionnaire" | "generating_report";

const STEP_LABELS: Record<WorkflowStepId, string> = {
  uploading: "Uploading Chest X-ray",
  retrieving_evidence: "Retrieving Similar Cases",
  running_questionnaire: "Clinical Questionnaire",
  generating_report: "Generating AI Report",
};

const STEP_ORDER: WorkflowStepId[] = [
  "uploading",
  "retrieving_evidence",
  "running_questionnaire",
  "generating_report",
];

type StepState = { status: StepStatus; elapsedMs?: number; detail?: string };

function initialSteps(): Record<WorkflowStepId, StepState> {
  return {
    uploading: { status: "pending" },
    retrieving_evidence: { status: "pending" },
    running_questionnaire: { status: "pending" },
    generating_report: { status: "pending" },
  };
}

export default function UploadFlowPage() {
  const params = useParams<{ patientId: string }>();
  const router = useRouter();
  const patientId = params.patientId;

  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"form" | "running">("form");
  const [steps, setSteps] = useState<Record<WorkflowStepId, StepState>>(initialSteps());
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // Real wall-clock moment the "running_questionnaire" step became active
  // (right after GET /questionnaire/{session_id} resolves) -- read back in
  // proceedToGeneration() to compute the step's real elapsed duration,
  // including however long the doctor spent filling in or deciding to
  // skip the form. A ref, not state, since it must survive re-renders
  // without itself triggering one.
  const questionnaireStepStart = useRef<number>(0);

  function updateStep(id: WorkflowStepId, patch: Partial<StepState>) {
    setSteps((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }

  async function handleStart(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setPhase("running");

    const uploadStart = performance.now();
    updateStep("uploading", { status: "active" });
    let retrieveStepStartTime = uploadStart;

    let retrieveResult;
    try {
      retrieveResult = await retrieveWithProgress(
        file,
        { topK: 5, minSimilarity: 0.0, patientId },
        {
          onUploadComplete: () => {
            updateStep("uploading", { status: "done", elapsedMs: performance.now() - uploadStart });
            updateStep("retrieving_evidence", { status: "active" });
            retrieveStepStartTime = performance.now();
          },
        },
      );
    } catch (err) {
      updateStep("retrieving_evidence", {
        status: "error",
        detail: err instanceof ApiError ? err.message : "Retrieval failed.",
      });
      return;
    }
    updateStep("retrieving_evidence", {
      status: "done",
      elapsedMs: performance.now() - retrieveStepStartTime,
    });
    setSessionId(retrieveResult.session_id);

    updateStep("running_questionnaire", { status: "active" });
    questionnaireStepStart.current = performance.now();
    try {
      const q = await getQuestionnaire(retrieveResult.session_id);
      setQuestionnaire(q);
      // intentionally NOT marking this step "done" yet -- it stays
      // "active" (real elapsed time still accruing) while the doctor
      // fills in or skips the form; finalized in proceedToGeneration().
    } catch (err) {
      updateStep("running_questionnaire", {
        status: "error",
        detail: err instanceof ApiError ? err.message : "Failed to load questionnaire.",
      });
    }
  }

  async function proceedToGeneration(finalAnswers: Record<string, string> | null) {
    updateStep("running_questionnaire", {
      status: finalAnswers === null ? "skipped" : "done",
      elapsedMs: performance.now() - questionnaireStepStart.current,
    });
    setQuestionnaire(null);

    const genStart = performance.now();
    updateStep("generating_report", { status: "active" });
    try {
      const result = await generateReport({
        session_id: sessionId!,
        language: "en",
        questionnaire_answers: finalAnswers,
        clinical_notes: "",
      });
      updateStep("generating_report", { status: "done", elapsedMs: performance.now() - genStart });
      router.push(`/reports/${result.report_id}`);
    } catch (err) {
      updateStep("generating_report", {
        status: "error",
        detail: err instanceof ApiError ? err.message : "Report generation failed.",
      });
    }
  }

  function handleSkipQuestionnaire() {
    void proceedToGeneration(null);
  }

  function handleSubmitQuestionnaire(event: React.FormEvent) {
    event.preventDefault();
    const nonEmpty = Object.fromEntries(
      Object.entries(answers).filter(([, value]) => value.trim().length > 0),
    );
    void proceedToGeneration(Object.keys(nonEmpty).length > 0 ? nonEmpty : null);
  }

  const stepDisplays: WorkflowStepDisplay[] = STEP_ORDER.map((id) => ({
    id,
    label: STEP_LABELS[id],
    status: steps[id].status,
    elapsedMs: steps[id].elapsedMs,
    detail: steps[id].detail,
  }));

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-lg flex-col gap-6 px-6 py-16">
        <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">New Examination</h1>

        {phase === "form" && (
          <form onSubmit={handleStart} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Chest X-ray Image
              </span>
              <input
                required
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </label>
            <button
              type="submit"
              disabled={!file}
              className="flex h-12 w-full items-center justify-center rounded-lg bg-black px-5 text-base font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
            >
              Start Examination
            </button>
          </form>
        )}

        {phase === "running" && (
          <>
            <StepProgress steps={stepDisplays} />

            {questionnaire && (
              <form
                onSubmit={handleSubmitQuestionnaire}
                className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
              >
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  Optional clinical questions (based on top candidate label:{" "}
                  <span className="font-medium">{questionnaire.based_on_label}</span>)
                </p>
                {questionnaire.questions.map((q) => (
                  <label key={q.key} className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{q.text}</span>
                    <input
                      type="text"
                      value={answers[q.key] ?? ""}
                      onChange={(e) => setAnswers((prev) => ({ ...prev, [q.key]: e.target.value }))}
                      className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                    />
                  </label>
                ))}
                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    className="flex h-10 flex-1 items-center justify-center rounded-lg bg-black px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
                  >
                    Continue
                  </button>
                  <button
                    type="button"
                    onClick={handleSkipQuestionnaire}
                    className="flex h-10 flex-1 items-center justify-center rounded-lg border border-zinc-300 px-4 text-sm font-medium text-black transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-900"
                  >
                    Skip Questionnaire
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </main>
    </div>
  );
}
