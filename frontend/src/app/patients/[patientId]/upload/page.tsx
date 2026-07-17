"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  generateReport,
  getQuestionnaire,
  retrievalSessionImageUrl,
  retrieveWithProgress,
} from "@/lib/api-client";
import { StepProgress, type StepStatus, type WorkflowStepDisplay } from "@/components/workflow/StepProgress";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PhiRevealSlider } from "@/components/ui/phi-reveal-slider";
import type { paths } from "@/lib/generated/api";

type QuestionnaireResponse =
  paths["/questionnaire/{session_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Upload -> Retrieval -> Questionnaire -> Generate (Phase 12 Step 4, PHI
 * slider added Phase 14), one guided flow per the frozen spec -- not
 * separate routes, since a doctor experiences this as one continuous
 * action.
 *
 * design_specification.md §8.9's PHI reveal slider: `originalObjectUrl`
 * is built from the SAME File object already sitting in this component's
 * state before upload (URL.createObjectURL, never re-uploaded or
 * persisted) -- this system deliberately never stores the raw image
 * (Phase 1/12's masking invariant), so this is the only "original" the
 * slider can legitimately show. Revoked on unmount/file-change to avoid
 * leaking the object URL.
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
  const [originalObjectUrl, setOriginalObjectUrl] = useState<string | null>(null);
  const [phase, setPhase] = useState<"form" | "running">("form");
  const [steps, setSteps] = useState<Record<WorkflowStepId, StepState>>(initialSteps());
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const questionnaireStepStart = useRef<number>(0);

  useEffect(() => {
    return () => {
      if (originalObjectUrl) URL.revokeObjectURL(originalObjectUrl);
    };
  }, [originalObjectUrl]);

  function handleFileChange(selected: File | null) {
    if (originalObjectUrl) URL.revokeObjectURL(originalObjectUrl);
    setFile(selected);
    setOriginalObjectUrl(selected ? URL.createObjectURL(selected) : null);
  }

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

  const maskedReady = sessionId !== null && steps.retrieving_evidence.status === "done";

  return (
    <div className="flex min-h-screen flex-col items-center bg-paper">
      <main className="flex w-full max-w-lg flex-col gap-6 px-page py-16">
        <h1 className="text-h1 text-ink">New Examination</h1>

        {phase === "form" && (
          <form onSubmit={handleStart} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-2">Chest X-ray Image</span>
              <input
                required
                type="file"
                accept="image/*"
                onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                className="rounded-btn border border-hairline-strong bg-surface px-3 py-2 text-ink"
              />
            </label>
            <Button type="submit" variant="primary" size="lg" block disabled={!file}>
              Start Examination
            </Button>
          </form>
        )}

        {phase === "running" && (
          <>
            <StepProgress steps={stepDisplays} />

            {maskedReady && originalObjectUrl && sessionId && (
              <Card className="p-card">
                <h2 className="mb-2 text-eyebrow uppercase text-ink-3">PHI masking</h2>
                <PhiRevealSlider
                  maskedSrc={retrievalSessionImageUrl(sessionId)}
                  originalSrc={originalObjectUrl}
                />
              </Card>
            )}

            {questionnaire && (
              <Card className="flex flex-col gap-4 p-card">
                <p className="text-sm text-ink-2">
                  Optional clinical questions (based on top candidate label:{" "}
                  <span className="font-medium text-ink">{questionnaire.based_on_label}</span>)
                </p>
                <form onSubmit={handleSubmitQuestionnaire} className="flex flex-col gap-4">
                  {questionnaire.questions.map((q) => (
                    <label key={q.key} className="flex flex-col gap-1">
                      <span className="text-sm font-medium text-ink-2">{q.text}</span>
                      <input
                        type="text"
                        value={answers[q.key] ?? ""}
                        onChange={(e) => setAnswers((prev) => ({ ...prev, [q.key]: e.target.value }))}
                        className="h-10 rounded-btn border border-hairline-strong bg-surface px-3 text-ink"
                      />
                    </label>
                  ))}
                  <div className="flex gap-3 pt-2">
                    <Button type="submit" variant="primary" size="md" className="flex-1">
                      Continue
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="md"
                      className="flex-1"
                      onClick={handleSkipQuestionnaire}
                    >
                      Skip Questionnaire
                    </Button>
                  </div>
                </form>
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}
