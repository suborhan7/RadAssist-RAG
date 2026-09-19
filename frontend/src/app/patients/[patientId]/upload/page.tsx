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
import { PhiRevealSlider } from "@/components/ui/phi-reveal-slider";
import { useDoctor } from "@/lib/doctor";
import { BackLink } from "@/components/layout/screen-header";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";
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

// Values are i18n keys; translated at render (labels change with the language).
const STEP_LABELS: Record<WorkflowStepId, string> = {
  uploading: "upload.stepUploading",
  retrieving_evidence: "upload.stepRetrieving",
  running_questionnaire: "upload.stepQuestionnaire",
  generating_report: "upload.stepGenerating",
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
  const { t, lang } = useT();
  const { topK, questionnaireSkip } = useDoctor();
  const params = useParams<{ patientId: string }>();
  const router = useRouter();
  const patientId = params.patientId;

  const [file, setFile] = useState<File | null>(null);
  // Requirement A14/A15: the doctor DECLARES the projection, and there is
  // no default. The initial state is deliberately empty rather than "PA" --
  // A15 says "Do not select a default value", and pre-selecting the
  // commonest answer is selecting a default on the doctor's behalf. The
  // submit button stays disabled until a real choice is made, so the
  // backend's PROJECTION_NOT_DECLARED path is a guard against a
  // hand-crafted request, not the normal UI experience.
  //
  // §5.5's Note is the reasoning: a radiographer knows the projection of
  // the film and the requisition states it. A declared value is exact; a
  // model prediction is not. So the system asks rather than predicts.
  const [declaredProjection, setDeclaredProjection] =
    useState<"" | "PA" | "AP" | "LATERAL">("");
  const [originalObjectUrl, setOriginalObjectUrl] = useState<string | null>(null);
  const [phase, setPhase] = useState<"form" | "running">("form");
  const [steps, setSteps] = useState<Record<WorkflowStepId, StepState>>(initialSteps());
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const questionnaireStepStart = useRef<number>(0);
  const questionnairePanel = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      if (originalObjectUrl) URL.revokeObjectURL(originalObjectUrl);
    };
  }, [originalObjectUrl]);

  // Bring the questionnaire into view when the pipeline stops for it. The panel
  // renders inside a scrolling column below the step list, so on a shorter
  // viewport the pipeline could appear to have stalled with the question that
  // was waiting sitting off-screen. `smooth` is honoured under
  // prefers-reduced-motion by tokens.css's global scroll-behavior override.
  useEffect(() => {
    if (!questionnaire) return;
    questionnairePanel.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [questionnaire]);

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
    if (!file || !declaredProjection) return;
    setPhase("running");

    const uploadStart = performance.now();
    updateStep("uploading", { status: "active" });
    let retrieveStepStartTime = uploadStart;

    let retrieveResult;
    try {
      retrieveResult = await retrieveWithProgress(
        file,
        { topK, minSimilarity: 0.0, patientId, declaredProjection },
        {
          onUploadComplete: () => {
            updateStep("uploading", { status: "done", elapsedMs: performance.now() - uploadStart });
            updateStep("retrieving_evidence", { status: "active" });
            retrieveStepStartTime = performance.now();
          },
        },
      );
    } catch (err) {
      // §10.1: the two projection rejections carry an i18n KEY, not a
      // sentence -- the server refuses to write English into the response
      // body. Translating the key here is what makes the doctor see the
      // M12 wording ("please check the view") in their own language rather
      // than a raw key or a stringified object.
      updateStep("retrieving_evidence", {
        status: "error",
        detail:
          err instanceof ApiError
            ? err.messageKey
              ? t(err.messageKey)
              : err.message
            : t("upload.errRetrieval"),
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

    // The doctor's saved default_questionnaire_skip goes straight to drafting,
    // exactly as pressing "skip" would. Read here rather than pre-checking a
    // box the doctor would still have to press through -- a preference that
    // only pre-fills a form they must confirm isn't a preference.
    if (questionnaireSkip) {
      void proceedToGeneration(null, retrieveResult.session_id);
      return;
    }

    try {
      const q = await getQuestionnaire(retrieveResult.session_id);
      setQuestionnaire(q);
    } catch (err) {
      updateStep("running_questionnaire", {
        status: "error",
        detail: err instanceof ApiError ? err.message : t("upload.errQuestionnaire"),
      });
    }
  }

  // `session` is passed explicitly rather than read from state: the skip path
  // calls this in the same tick as setSessionId(), where the state value is
  // still null.
  async function proceedToGeneration(
    finalAnswers: Record<string, string> | null,
    session: string,
  ) {
    updateStep("running_questionnaire", {
      status: finalAnswers === null ? "skipped" : "done",
      elapsedMs: performance.now() - questionnaireStepStart.current,
    });
    setQuestionnaire(null);

    const genStart = performance.now();
    updateStep("generating_report", { status: "active" });
    try {
      const result = await generateReport({
        session_id: session,
        // Follows the global language toggle: বাংলা drafts the report in Bengali.
        language: lang,
        questionnaire_answers: finalAnswers,
        clinical_notes: "",
      });
      updateStep("generating_report", { status: "done", elapsedMs: performance.now() - genStart });
      router.push(`/reports/${result.report_id}`);
    } catch (err) {
      updateStep("generating_report", {
        status: "error",
        detail: err instanceof ApiError ? err.message : t("upload.errGeneration"),
      });
    }
  }

  function handleSkipQuestionnaire() {
    if (!sessionId) return;
    void proceedToGeneration(null, sessionId);
  }

  function handleSubmitQuestionnaire(event: React.FormEvent) {
    event.preventDefault();
    if (!sessionId) return;
    const nonEmpty = Object.fromEntries(
      Object.entries(answers).filter(([, value]) => value.trim().length > 0),
    );
    void proceedToGeneration(Object.keys(nonEmpty).length > 0 ? nonEmpty : null, sessionId);
  }

  const stepDisplays: WorkflowStepDisplay[] = STEP_ORDER.map((id) => ({
    id,
    label: t(STEP_LABELS[id]),
    status: steps[id].status,
    elapsedMs: steps[id].elapsedMs,
    detail: steps[id].detail,
  }));

  const maskedReady = sessionId !== null && steps.retrieving_evidence.status === "done";

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg-app">
      <header className="flex h-header-bar flex-none items-center gap-14 border-b border-hairline px-30">
        <BackLink href={`/patients/${patientId}`} labelKey="upload.crumbPatient" />
        <h1 className="text-screen-title text-text-primary">{t("nav.newExam")}</h1>
        <span className="flex-1" />
        {/* Reads the same `topK` the retrieval call is given. It previously
            rendered the literal "K=5" beside a literal `topK: 5` argument, so a
            doctor who set k=3 saw 5 here and got 5 from the server, with no
            way to tell the label from the behaviour. One variable, both jobs. */}
        <span className="whitespace-nowrap font-mono text-mono-meta-lg uppercase text-text-tertiary">
          K={topK} · {lang === "bn" ? "BN" : "EN"}
        </span>
      </header>

      <div className="flex min-h-0 flex-1 overflow-x-auto">
        {/* Film -- the drop target in the form phase, the masked/original
            reveal in the running phase. The only pure-black surface. */}
        <div className="relative flex min-w-[360px] flex-1 items-center justify-center on-film bg-bg-film p-26">
          {phase === "form" ? (
            originalObjectUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={originalObjectUrl} alt={t("upload.altSelected")} className="max-h-full max-w-full object-contain" />
            ) : (
              <label className="flex cursor-pointer flex-col items-center gap-16 text-center">
                <span className="font-mono text-mono-meta uppercase tracking-[0.12em] text-cyan">
                  {t("upload.dropFilm")}
                </span>
                <span className="rounded-field border border-strong px-22 py-12 text-sm text-text-secondary transition-colors duration-hover hover:border-cyan-line hover:text-cyan">
                  {t("upload.chooseFile")}
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
              <img src={originalObjectUrl} alt={t("upload.altMasking")} className="max-h-full max-w-full object-contain opacity-70" />
            )
          )}

          {phase === "running" && maskedReady && (
            <span className="absolute left-26 top-26 font-mono text-mono-meta uppercase tracking-[0.12em] text-cyan">
              {t("upload.dragReveal")}
            </span>
          )}
          {file && (
            <span className="absolute bottom-26 left-26 font-mono text-mono-meta text-text-tertiary">
              {file.name} · {t("upload.neverStored")}
            </span>
          )}
        </div>

        {/* Pipeline panel */}
        <aside className="flex w-[600px] max-w-full flex-none flex-col border-l border-hairline">
          {phase === "form" ? (
            <form onSubmit={handleStart} className="flex flex-col gap-18 p-28">
              <h2 className="text-panel text-text-primary">{t("upload.startTitle")}</h2>
              <p className="text-sm leading-relaxed text-text-secondary">
                {t("upload.startDesc")}
              </p>

              {/* A14: the declared projection. No option is pre-selected
                  (A15), so the doctor makes a real choice. LATERAL is
                  offered and then rejected by the backend rather than
                  hidden -- a doctor holding a lateral film needs to be
                  told what to do (§10.1's message asks for the frontal
                  image of the same study), and a missing option would
                  read as a broken form instead of an answer. */}
              <fieldset className="flex flex-col gap-8">
                <legend className="font-mono text-eyebrow uppercase text-text-tertiary">
                  {t("upload.projectionLabel")}
                </legend>
                <div className="flex gap-8">
                  {(["PA", "AP", "LATERAL"] as const).map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setDeclaredProjection(value)}
                      aria-pressed={declaredProjection === value}
                      className={cn(
                        "flex-1 rounded-panel border px-12 py-10 font-mono text-mono-meta transition-colors duration-hover",
                        declaredProjection === value
                          ? "border-cyan text-cyan"
                          : "border-hairline text-text-secondary hover:text-text-primary",
                      )}
                    >
                      {t(`upload.projection${value}`)}
                    </button>
                  ))}
                </div>
                <p className="text-sm leading-relaxed text-text-secondary">
                  {t("upload.projectionNote")}
                </p>
              </fieldset>

              <Button
                type="submit"
                variant="primary"
                size="lg"
                disabled={!file || !declaredProjection}
              >
                {t("upload.startBtn")}
              </Button>
            </form>
          ) : (
            <>
              <div className="flex-none border-b border-hairline p-28">
                <h2 className="mb-18 text-panel text-text-primary">{t("upload.running")}</h2>
                <StepProgress steps={stepDisplays} />
              </div>

              <div className="flex-1 overflow-auto p-28">
                {questionnaire ? (
                  // The pipeline pauses here and waits for the reader, but the
                  // block used to render as plain body text below a run of
                  // completed steps -- frequently below the fold, and reported
                  // as easy to miss. A raised, cyan-edged panel (the accent
                  // this system already uses for "retrieval and interaction")
                  // plus scrollIntoView makes the stopping point look like one.
                  <div
                    ref={questionnairePanel}
                    className="enter-panel rounded-panel border border-cyan-line bg-bg-raised p-20"
                  >
                    <div className="mb-8 font-mono text-eyebrow uppercase text-cyan">
                      {t("upload.optionalQuestions")}
                    </div>
                    <p className="mb-20 text-sm leading-relaxed text-text-secondary">
                      {t("upload.basedOnPre")}{" "}
                      <span className="text-text-primary">{questionnaire.based_on_label}</span>
                      {t("upload.basedOnPost")}
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
                          {t("upload.reRetrieve")}
                        </Button>
                        <Button type="button" variant="secondary" size="md" onClick={handleSkipQuestionnaire}>
                          {t("upload.skipDraft")}
                        </Button>
                      </div>
                      <p className="text-caption text-text-tertiary">{t("upload.skipNote")}</p>
                    </form>
                  </div>
                ) : (
                  <p className="text-sm text-text-tertiary">
                    {t("upload.runningNote")}
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
