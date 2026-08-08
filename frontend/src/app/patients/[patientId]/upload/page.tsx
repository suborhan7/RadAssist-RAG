"use client";

import Link from "next/link";
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
import { PhiRevealSlider } from "@/components/ui/phi-reveal-slider";
import type { paths } from "@/lib/generated/api";

type QuestionnaireResponse =
  paths["/questionnaire/{session_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Upload -> Retrieval -> Questionnaire -> Generate (Phase 12 Step 4, PHI
 * slider Phase 14, ported to the Reading Room theme in the redesign step 4),
 * one guided flow -- a doctor experiences this as one continuous action.
 *
 * PHI reveal slider (§8.9): `originalObjectUrl` is built from the SAME File
 * object in this component's state (URL.createObjectURL, never re-uploaded or
 * persisted). This system never stores the raw image (Phase 1/12 masking
 * invariant), so this local object URL is the only "original" the slider can
 * legitimately show, and the "original never stored" caption is literal.
 * Revoked on unmount/file-change. The mock's multiple-choice pill questions
 * are aspirational; the real backend returns free-text questions, kept as-is.
 */
type WorkflowStepId = "uploading" | "retrieving_evidence" | "running_questionnaire" | "generating_report";

const STEP_LABELS: Record<WorkflowStepId, string> = {
  uploading: "Uploading chest X-ray",
  retrieving_evidence: "Retrieving similar cases",
  running_questionnaire: "Clinical questionnaire",
  generating_report: "Generating AI report",
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
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <Link
          href={`/patients/${patientId}`}
          className="text-sm text-text-tertiary transition-colors duration-hover hover:text-cyan"
        >
          Patient
        </Link>
        <span className="text-text-muted">/</span>
        <h1 className="text-screen-title text-text-primary">New examination</h1>
        <span className="flex-1" />
        <span className="whitespace-nowrap font-mono text-mono-meta-lg uppercase text-text-tertiary">
          K=5 · EN
        </span>
      </header>

      <div className="flex min-h-0 flex-1 overflow-x-auto">
        {/* Film -- the drop target in the form phase, the masked/original
            reveal in the running phase. The only pure-black surface. */}
        <div className="relative flex min-w-[360px] flex-1 items-center justify-center bg-bg-film p-26">
          {phase === "form" ? (
            originalObjectUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={originalObjectUrl} alt="Selected chest X-ray" className="max-h-full max-w-full object-contain" />
            ) : (
              <label className="flex cursor-pointer flex-col items-center gap-16 text-center">
                <span className="font-mono text-mono-meta uppercase tracking-[0.12em] text-cyan">
                  Drop the chest film
                </span>
                <span className="rounded-field border border-strong px-22 py-12 text-sm text-text-secondary transition-colors duration-hover hover:border-cyan-line hover:text-cyan">
                  Choose a file
                </span>
                <input
                  required
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                  className="sr-only"
                />
              </label>
            )
          ) : maskedReady && originalObjectUrl && sessionId ? (
            <PhiRevealSlider maskedSrc={retrievalSessionImageUrl(sessionId)} originalSrc={originalObjectUrl} />
          ) : (
            originalObjectUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={originalObjectUrl} alt="Chest X-ray, masking in progress" className="max-h-full max-w-full object-contain opacity-70" />
            )
          )}

          {phase === "running" && maskedReady && (
            <span className="absolute left-26 top-26 font-mono text-mono-meta uppercase tracking-[0.12em] text-cyan">
              Drag to reveal the original
            </span>
          )}
          {file && (
            <span className="absolute bottom-26 left-26 font-mono text-mono-meta text-text-tertiary">
              {file.name} · original never stored
            </span>
          )}
        </div>

        {/* Pipeline panel */}
        <aside className="flex w-[600px] max-w-full flex-none flex-col border-l border-hairline">
          {phase === "form" ? (
            <form onSubmit={handleStart} className="flex flex-col gap-18 p-28">
              <h2 className="text-panel text-text-primary">Start a new examination</h2>
              <p className="text-sm leading-relaxed text-text-secondary">
                Drop the chest film on the left. It is masked on upload, then matched against the
                archive and drafted. Everything runs locally; nothing leaves the building.
              </p>
              <Button type="submit" variant="primary" size="lg" disabled={!file}>
                Start examination
              </Button>
            </form>
          ) : (
            <>
              <div className="flex-none border-b border-hairline p-28">
                <h2 className="mb-18 text-panel text-text-primary">Running the pipeline</h2>
                <StepProgress steps={stepDisplays} />
              </div>

              <div className="flex-1 overflow-auto p-28">
                {questionnaire ? (
                  <>
                    <div className="mb-8 font-mono text-eyebrow uppercase text-text-tertiary">
                      Optional clinical questions
                    </div>
                    <p className="mb-20 text-sm leading-relaxed text-text-secondary">
                      Based on the top candidate label{" "}
                      <span className="text-text-primary">{questionnaire.based_on_label}</span>. Your
                      answers go into the prompt and are kept with the report.
                    </p>
                    <form onSubmit={handleSubmitQuestionnaire} className="flex flex-col gap-18">
                      {questionnaire.questions.map((q) => (
                        <label key={q.key} className="flex flex-col gap-8">
                          <span className="text-sm text-text-secondary">{q.text}</span>
                          <input
                            type="text"
                            value={answers[q.key] ?? ""}
                            onChange={(e) => setAnswers((prev) => ({ ...prev, [q.key]: e.target.value }))}
                            className="h-46 rounded-field border border-strong bg-bg-raised px-16 text-text-primary placeholder:text-text-muted"
                          />
                        </label>
                      ))}
                      <div className="flex flex-wrap items-center gap-12 pt-4">
                        <Button type="submit" variant="primary" size="md">
                          Re-retrieve with answers
                        </Button>
                        <Button type="button" variant="secondary" size="md" onClick={handleSkipQuestionnaire}>
                          Skip and draft anyway
                        </Button>
                      </div>
                      <p className="text-caption text-text-tertiary">Skipping is recorded on the report.</p>
                    </form>
                  </>
                ) : (
                  <p className="text-sm text-text-tertiary">
                    Retrieval and drafting are running. This can take several seconds on local
                    hardware.
                  </p>
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
