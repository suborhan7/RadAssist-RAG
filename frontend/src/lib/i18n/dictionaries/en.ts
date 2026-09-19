/**
 * English dictionary — the SOURCE OF TRUTH for i18n keys. Every key that exists
 * here must exist in `bn.ts`; the dev-time parity check in `check-i18n.mjs`
 * flags drift. Keys are namespaced by screen (`common.*`, `nav.*`, `landing.*`,
 * …). Values are either a plain string or a function of params for interpolation.
 *
 * Do NOT add dynamic clinical/report content, patient names, IDs, dates, model
 * names, or numeric codes here — those are never translated.
 */
import type { Dict } from "../shared";

export const en: Dict = {
  // ── common ────────────────────────────────────────────────────────────────
  "common.signIn": "Sign in",
  "common.register": "Register",
  "common.dashboard": "Dashboard",
  "common.email": "Email",
  "common.password": "Password",
  "common.researchPrototype": "Research prototype",
  "common.cancel": "Cancel",
  "common.save": "Save",
  "common.retry": "Retry",
  "common.loading": "Loading…",

  // ── nav (left rail) ───────────────────────────────────────────────────────
  "nav.queue": "Queue",
  "nav.find": "Find patient",
  "nav.patients": "Patients",
  "nav.newExam": "New examination",
  "nav.workspace": "Workspace",
  "nav.explain": "Explainability",
  "nav.compare": "Compare",
  "nav.settings": "Settings",
  "nav.signOut": "Sign out",
  "nav.signingOut": "Signing out…",
  "nav.back": "Back",
  // Shown on hover for a rail item that has no patient/report in context yet,
  // so the redirect to a chooser reads as intentional rather than as a misfire.
  "nav.requiresPatient": "Choose a patient first",
  "nav.requiresReport": "Choose a report first",

  // ── language toggle ───────────────────────────────────────────────────────
  "lang.label": "Language",

  // ── theme toggle ──────────────────────────────────────────────────────────
  "theme.label": "Appearance",
  "theme.dark": "Dark",
  "theme.light": "Light",

  // ── landing ───────────────────────────────────────────────────────────────
  "landing.headerCtaSignIn": "Sign in",
  "landing.headerCtaDashboard": "Dashboard",
  "landing.ctaSignIn": "Sign in to your workspace",
  "landing.ctaDashboard": "Go to your dashboard",
  "landing.heroTitle": "Evidence-grounded chest X-ray reporting.",
  "landing.heroSubtitle":
    "Every AI draft is grounded in real, retrieved prior cases. Never generated from nothing, and never signed without a radiologist.",
  "landing.aiDraft": "AI Draft",
  "landing.proofPhrase1": "Diffuse interstitial markings are prominent throughout both lungs",
  "landing.proofConnective": ", consistent with ",
  "landing.proofPhrase2": "fibrotic change rather than acute infection",
  "landing.proofTrace": "Every underlined statement traces to the retrieved cases that support it.",
  "landing.neverFinalized": "No report has ever been finalised without a radiologist.",
  "landing.pipelineTitle": "How a report is grounded",
  "landing.stageChestXray": "Chest X-ray",
  "landing.stagePhi": "PHI protection",
  "landing.stageSimilar": "Similar cases",
  "landing.stageAiDraft": "AI draft",
  "landing.stageReview": "Radiologist review",
  "landing.footer": "Research prototype. Not for clinical use. Every report requires review by a qualified radiologist.",

  // ── login ─────────────────────────────────────────────────────────────────
  "login.filmTitle": "Retrieval-grounded chest X-ray reporting.",
  "login.filmBody":
    "Every AI draft cites the retrieved cases it was grounded in. No report has ever been finalised without a radiologist.",
  "login.notForClinical": "Not for clinical use. Every report requires review by a qualified radiologist.",
  "login.heading": "Sign in",
  "login.subtitle": "RadAssist-RAG · Radiologist workflow",
  "login.systemStatus": "System status",
  "login.backendUnreachable": "Backend unreachable.",
  "login.signingIn": "Signing in…",
  "login.noAccount": "No account?",
  "login.errCredentials": "Email or password is incorrect.",
  "login.errFailed": "Login failed.",

  // ── register ──────────────────────────────────────────────────────────────
  "register.title": "Register a doctor account",
  "register.subtitle": "The patient registry is shared with your department. Your unsigned drafts are not.",
  "register.fullName": "Full name, as printed on reports",
  "register.qualifications": "Qualifications",
  "register.bmdcOptional": "BMDC number (optional)",
  "register.creating": "Creating account…",
  "register.create": "Create account",
  "register.already": "Already registered?",
  "register.sigBlock": "Signature block · live",
  "register.yourName": "Your name",
  "register.bmdcNotEntered": "BMDC not entered",
  "register.sigNote":
    "Recorded as entered and printed on every report you sign. This system has no access to the BMDC registry and cannot verify it.",
  "register.errExists": "An account with this email already exists.",
  "register.errFailed": "Registration failed.",

  // ── dashboard (reading queue) ─────────────────────────────────────────────
  "dashboard.title": "Reading queue",
  "dashboard.queueFallback": "Your reading queue",
  "dashboard.queueLoading": "Loading your queue…",
  "dashboard.awaiting": (p) => `${Number(p.count)} ${Number(p.count) === 1 ? "report is" : "reports are"} waiting on you.`,
  "dashboard.clear": "Your queue is clear.",
  "dashboard.clearNamed": (p) => `Your queue is clear, ${String(p.name)}.`,
  "dashboard.openOldest": "Open the oldest",
  "dashboard.waitingDays": (p) => `waiting ${Number(p.count)} ${Number(p.count) === 1 ? "day" : "days"}`,
  "dashboard.examToday": "examinations today",
  "dashboard.reportsByYou": "reports by you",
  "dashboard.patientsReported": "patients reported",
  "dashboard.errStats": "Failed to load dashboard stats.",
  "dashboard.errRecent": "Failed to load recent activity.",
  "dashboard.colPatient": "Patient",
  "dashboard.colWaiting": "Waiting",
  "dashboard.colStatus": "Status",
  "dashboard.colEdited": "Edited",
  "dashboard.loadingQueue": "Loading queue…",
  "dashboard.emptyQueue": "No reports yet. Start a new examination to build the queue.",
  // Two-step discard: the row's control arms on the first press and confirms
  // on the second. "Discard" not "Delete" -- what goes is an unfinished draft,
  // and a finalized report cannot be removed at all.
  "dashboard.delete": "Discard",
  "dashboard.deleteConfirm": "Confirm discard",
  "dashboard.deleteAria": (p) => `Discard the draft for ${p.patient}`,
  "dashboard.errDelete": "Could not discard this draft.",
  "dashboard.noPatientLinked": "No patient linked",
  "dashboard.actionReview": "Review",
  "dashboard.actionOpen": "Open",
  "dashboard.actionResume": "Resume",
  "dashboard.unitMin": (p) => `${Number(p.count)} min`,
  "dashboard.unitHours": (p) => `${Number(p.count)} ${Number(p.count) === 1 ? "hour" : "hours"}`,
  "dashboard.unitDays": (p) => `${Number(p.count)} ${Number(p.count) === 1 ? "day" : "days"}`,
  "dashboard.ownership": (p) =>
    `You have reported on ${Number(p.reported)} of the hospital's ${Number(p.total)} registered patients. You can open any colleague's patient; you cannot open their unsigned drafts.`,

  // ── shared verbs / patient actions ────────────────────────────────────────
  "common.open": "Open",
  "common.registerNewPatient": "Register new patient",

  // ── find patient (search) ─────────────────────────────────────────────────
  "search.byCode": "By patient code",
  "search.byNameDob": "By name and date of birth",
  "search.patientCode": "Patient code",
  "search.name": "Name",
  "search.dob": "Date of birth",
  "search.searching": "Searching…",
  "search.search": "Search",
  "search.helper": "One code, or a name and date of birth. Spelling is never the reason you cannot find a patient.",
  "search.errFailed": "Search failed.",
  "search.zeroMatches":
    "A well-formed search that finds nothing is not an error. Register the patient, or add a date of birth to narrow a common name.",
  "search.matches": (p) => `${Number(p.count)} ${Number(p.count) === 1 ? "match" : "matches"}`,

  // ── patients directory (list all + name/ID search) ────────────────────────
  "directory.searchPlaceholder": "Search by name or patient ID",
  "directory.colId": "Patient ID",
  "directory.count": (p) => `${Number(p.count)} ${Number(p.count) === 1 ? "patient" : "patients"}`,
  "directory.empty": "No patients registered yet.",
  "directory.noMatches": "No patients match your search.",
  "directory.loading": "Loading patients…",
  "directory.errLoad": "Failed to load patients.",
  "directory.clear": "Clear",

  // ── patient profile ───────────────────────────────────────────────────────
  "patient.errLoad": "Failed to load patient profile.",
  "patient.loading": "Loading patient profile…",
  "patient.compareLatestTwo": "Compare latest two",
  "patient.years": (p) => `${Number(p.count)} years`,
  "patient.born": "born",
  "patient.onRecord": "On record",
  "patient.studies": (p) => `${Number(p.count)} ${Number(p.count) === 1 ? "study" : "studies"}`,
  "patient.since": (p) => `since ${String(p.since)}`,
  "patient.priorStudies": "Prior studies · same patient",
  "patient.noPriors": "No prior visits recorded for this patient yet.",
  "patient.noImpression": "(no impression recorded)",
  "patient.openReport": "Open report",
  "patient.compareWithThis": "Compare with this",
  "patient.priorNote":
    "Prior studies are this patient over time. Archive cases, other patients' films retrieved by similarity, never appear here; they exist only inside the workspace.",

  // ── register patient (patients/new) ───────────────────────────────────────
  // Sex option VALUES stay English (sent to the backend as `gender`); only the
  // visible label is localized.
  "newPatient.title": "Register patient",
  "newPatient.fullName": "Full name",
  "newPatient.sex": "Sex",
  "newPatient.sexFemale": "Female",
  "newPatient.sexMale": "Male",
  "newPatient.sexOther": "Other",
  "newPatient.registering": "Registering…",
  "newPatient.errFailed": "Failed to register patient.",
  "newPatient.registeredPre": "Patient registered as",
  "newPatient.registeredPost": ". Opening the profile…",
  "newPatient.willAssign": "Will be assigned",
  "newPatient.assignNote":
    "Sequential and permanent, assigned on registration. Written on the film envelope at reception.",

  // ── new examination (upload → retrieve → questionnaire → generate) ─────────
  "upload.crumbPatient": "Patient",
  "upload.stepUploading": "Uploading chest X-ray",
  "upload.stepRetrieving": "Retrieving similar cases",
  "upload.stepQuestionnaire": "Clinical questionnaire",
  "upload.stepGenerating": "Generating AI report",
  "upload.dropFilm": "Drop the chest film",
  "upload.chooseFile": "Choose a file",
  "upload.altSelected": "Selected chest X-ray",
  "upload.altMasking": "Chest X-ray, masking in progress",
  "upload.dragReveal": "Drag to reveal the original",
  "upload.neverStored": "original never stored",
  "upload.startTitle": "Start a new examination",
  "upload.startDesc":
    "Drop the chest film on the left. It is masked on upload, then matched against the archive and drafted. Everything runs locally; nothing leaves the building.",
  "upload.startBtn": "Start examination",
  "upload.running": "Running the pipeline",
  "upload.optionalQuestions": "Optional clinical questions",
  "upload.basedOnPre": "Based on the top candidate label",
  "upload.basedOnPost": ". Your answers go into the prompt and are kept with the report.",
  "upload.reRetrieve": "Re-retrieve with answers",
  "upload.skipDraft": "Skip and draft anyway",
  "upload.skipNote": "Skipping is recorded on the report.",
  "upload.runningNote": "Retrieval and drafting are running. This can take several seconds on local hardware.",
  "upload.errRetrieval": "Retrieval failed.",
  "upload.errQuestionnaire": "Failed to load questionnaire.",
  "upload.errGeneration": "Report generation failed.",

  // ── radiologist workspace ─────────────────────────────────────────────────
  "workspace.errLoad": "Failed to load report.",
  "workspace.errSave": "Failed to save edit.",
  "workspace.errRestore": "Failed to restore AI draft.",
  "workspace.errRegen": "Failed to regenerate section.",
  "workspace.loading": "Loading report…",
  "workspace.reportFallback": "Report",
  "workspace.confirmLeave": "You have an unsaved edit in progress. Leave without saving?",
  "workspace.confirmRestore": "Replace your edits with the original AI draft? This cannot be undone.",
  "workspace.askAbout": "Ask about this report",
  "workspace.showChanges": "Changes vs draft",
  "workspace.hideChanges": "Hide changes vs draft",
  "workspace.finalize": "Finalize",
  "workspace.belongsToPre": "This report belongs to",
  "workspace.belongsToPost": ". You can read it and compare against it.",
  "workspace.anotherDoctor": "another doctor",
  "workspace.phiMasked": "PHI masked",
  "workspace.altXrayPrefix": "Chest X-ray",
  "workspace.finalizedReport": "Finalized report",
  "workspace.aiReport": "AI report",
  "workspace.restoring": "Restoring…",
  "workspace.restoreDraft": "Restore draft",
  "workspace.finalizedBy": (p) => `Finalized by ${String(p.name)} on ${String(p.date)}`,
  "workspace.thisDoctor": "this doctor",
  "workspace.validation": "Validation",
  "workspace.noWarnings": "No validation warnings.",
  "workspace.explainReport": "Explain report",
  "workspace.comparePrevious": "Compare previous",
  "workspace.downloadPdf": "Download PDF",
  "workspace.downloadPdfTitle": "Out of scope for this thesis (frozen Phase 12 spec)",
  "workspace.draftedFrom": (p) =>
    `Drafted from ${Number(p.count)} archive ${Number(p.count) === 1 ? "case" : "cases"}, then reviewed and edited by the reporting radiologist. Not an autonomous diagnosis.`,
  "workspace.tabEvidence": "Evidence",
  "workspace.tabAgreement": "Agreement",
  "workspace.tabAlternatives": "Alternatives",
  "workspace.archiveCases": (p) => `Archive cases · other patients (${Number(p.count)})`,
  "workspace.presentInSet": "Present in the retrieved set",
  "workspace.countOfK": (p) => `${Number(p.count)} of ${Number(p.k)}`,
  "workspace.altNotePre": "Absence from this list means no retrieved case carried the label.",
  "workspace.altNoteEmph": "It is not an exclusion.",
  "workspace.altNotePost": "Only labels present are reported, not a complete positive or negative taxonomy.",

  // ── comparison workspace ──────────────────────────────────────────────────
  "compare.errCurrent": "Failed to load current report.",
  "compare.errNoPatient": "This report has no patient linked, so it cannot be compared against patient history.",
  "compare.errGenerate": "Failed to generate comparison.",
  "compare.errPrevious": "Failed to load previous report.",
  "compare.stepGenerating": "Generating comparison",
  "compare.daysApart": (p) => `${Number(p.count)} days apart`,
  "compare.backToWorkspace": "Back to workspace",
  "compare.reviewBanner": "Doctor review required. This AI-generated comparison is a draft, not a final verdict.",
  "compare.priorEyebrow": (p) => `Prior · ${String(p.date)}`,
  "compare.thisStudyEyebrow": (p) => `This study · ${String(p.date)}`,
  "compare.altPrior": "Prior chest X-ray",
  "compare.altCurrent": "Current chest X-ray",
  "compare.impression": "Impression",
  "compare.none": "(none)",
  "compare.resolved": "Resolved",
  "compare.persistent": "Persistent",
  "compare.new": "New",
  "compare.noneLower": "none",
  "compare.narrativeHeading": "Narrative · written by the model from the split at left",
  "compare.provenanceNote": (p) =>
    `Resolved, persistent and new findings are computed by ComparisonService (deterministic), ${Number(p.days)} days between studies. The narrative is generated by an LLM from that diff only; the diff itself is not decided by the model.`,

  // ── explainability ────────────────────────────────────────────────────────
  "explain.q1": "Why this impression?",
  "explain.q2": "Which retrieved case is closest?",
  "explain.q3": "What would change this impression?",
  "explain.err502": (p) => `The AI assistant is temporarily unavailable (LLM transport failure): ${String(p.msg)}`,
  "explain.err404": (p) => `Report not found: ${String(p.msg)}`,
  "explain.errGeneric": "Failed to get an answer.",
  "explain.stepAsking": "Asking AI assistant",
  "explain.grounding":
    "Answers are grounded in the retrieved cases and this report. The assistant cannot introduce new findings, and it is not a second opinion.",
  "explain.idlePrompt":
    "Ask a question about this report to see a grounded answer. Every answer is drawn only from the retrieved cases and the report text.",
  "explain.ariaAsk": "Ask a question about this report",
  "explain.placeholder": "Ask about a sentence in this report…",
  "explain.ask": "Ask",
  "explain.reportImpression": "Report impression",
  "explain.casesInContext": "Cases in context",
  "explain.auditNote": "Questions and answers stay with the report as part of its audit trail.",

  // ── settings / profile ────────────────────────────────────────────────────
  "settings.signInToView": "Sign in to view Settings.",
  "settings.errLoadProfile": "Failed to load profile.",
  "settings.errSave": "Failed to save.",
  "settings.loading": "Loading settings…",
  "settings.allSaved": "All changes saved",
  "settings.identityTitle": "Identity and signature",
  "settings.identityDesc": "Printed at the foot of every report you sign.",
  "settings.bmdcNumber": "BMDC number",
  "settings.bmdcNote": "Recorded as entered. This system has no access to the BMDC registry and cannot verify it.",
  "settings.sigPreview": "As it appears on a signed report",
  "settings.defaultsTitle": "Reading defaults",
  "settings.defaultsDesc": "Applied to every new examination you start.",
  "settings.defaultK": "Default K (retrieved cases)",
  "settings.defaultKNote": "Five is what the evaluation used. More cases means slower generation.",
  "settings.defaultLanguage": "Default language",
  "settings.langEnglish": "English",
  "settings.langBangla": "Bangla",
  "settings.skipQuestionnaire": "Skip the questionnaire by default",
  "settings.railState": "Evidence rail state",
  "settings.expanded": "Expanded",
  "settings.collapsed": "Collapsed",
  "settings.exportFormat": "Export format",
  "settings.exportNote": "Stored as a preference only. Export (Download PDF) is not yet implemented anywhere in this app.",
  "settings.saving": "Saving…",
  "settings.saveChanges": "Save changes",
  "settings.savedShort": "Saved.",
  "settings.thisMachine": "This machine",
  "settings.localNote": "Everything runs locally. Nothing leaves the building.",
  "settings.backend": "Backend",
  "settings.checking": "checking…",
  "settings.statusOk": "ok",
  "settings.statusUnreachable": "unreachable",
  "settings.indexSize": "Index size",
  "settings.embeddingModel": "Embedding model",
  "settings.maskedStored": "Masked images stored",
  "settings.originalStored": "Original images stored",
  "settings.casesValue": (p) => `${Number(p.count)} cases`,
  "settings.phiNote": "The system cannot disclose unmasked PHI from storage, because unmasked PHI is never stored.",

  // ── report document fields + diff + finalize + editable section ────────────
  "report.examination": "Examination",
  "report.clinicalHistory": "Clinical History",
  "report.technique": "Technique",
  "report.findings": "Findings",
  "report.impression": "Impression",
  "report.recommendation": "Recommendation",
  "report.disclaimer": "Disclaimer",
  "report.sectionsChanged": (p) => `${Number(p.changed)} of ${Number(p.total)} sections changed`,
  "report.editedOfDraft": (p) => `${String(p.pct)}% of the AI draft was edited`,
  "report.noEdits": "No edits made.",
  "report.diffFooter":
    "Comparing the original AI draft against the current report. This shows what changed overall, not a step-by-step edit history.",
  "report.errFinalize": "Failed to finalize report.",
  "report.previewTitle": "Preview before finalizing",
  "report.previewDesc": "Once finalized, this report cannot be edited further.",
  "report.changesAi": "Changes vs AI draft",
  "report.hideChangesAi": "Hide changes vs AI draft",
  "report.backToEdit": "Back to Edit",
  "report.finalizing": "Finalizing…",
  "report.confirmFinalize": "Confirm Finalize",
  "report.editedByDoctor": "Edited by doctor",
  "report.editedAria": "Edited",
  "report.edited": "Edited",
  "report.saving": "Saving…",
  "report.regenerating": "Regenerating…",
  "report.regenerate": "Regenerate",
  "report.edit": "Edit",
  "report.candidateNotApplied": "Regenerated candidate, not applied",
  "report.contextIncomplete":
    "This report predates full context capture. This candidate was generated from retrieved evidence only, so it may not reflect the original questionnaire context.",
  "report.accept": "Accept",
  "report.discard": "Discard",
  "report.discardNote": "Discarding fires no request.",

  // ── status / ownership chips ──────────────────────────────────────────────
  "chip.statusDraft": "AI Draft",
  "chip.statusReview": "Under Review",
  "chip.statusEdited": "Doctor Edited",
  "chip.statusFinal": "Final",
  "chip.you": "You",

  // ── evidence agreement ────────────────────────────────────────────────────
  "agreement.title": "Evidence agreement",
  "agreement.strong": "Strong",
  "agreement.mixed": "Mixed",
  "agreement.weak": "Weak",
  "agreement.agreeLine": (p) => `${Number(p.agreeing)} of ${Number(p.k)} retrieved cases agree on the primary finding.`,
  "agreement.top1": "Top-1 similarity",
  "agreement.meanSim": (p) => `Mean similarity (K=${Number(p.k)})`,
  "agreement.clinHistory": "Clinical history provided",
  "agreement.notRecorded": "Not recorded",
  "agreement.yes": "Yes",
  "agreement.no": "No",
  "agreement.labelSpread": "Label spread",
  "agreement.labelsCount": (p) => `${Number(p.count)} labels`,
  "agreement.defPre": "Measures agreement among retrieved cases.",
  "agreement.defBold": "Not a probability that the report is correct.",

  // Retrieval support -- the second evidence signal (§7 of
  // input_admission_modality_gate_architecture_v1.0_FROZEN.md). Every
  // string here obeys §7.2's closing Rule: state what was measured (the
  // top-1 similarity fell below the configured threshold), never the
  // stronger claim that no similar case exists in the archive.
  "support.title": "Retrieval support",
  "support.atOrAbove": "Met",
  "support.below": "Below threshold",
  "support.notRecorded": "Not recorded",
  "support.top1": "Top-1 similarity",
  "support.def": "Measures how near the retrieved cases are to this image.",
  // Projection rejection messages -- §10.1 of
  // input_admission_projection_gate_architecture_v1.1_FROZEN.md. The
  // backend sends only these KEYS; §10.1's Rule forbids English text in
  // the response body, so both languages are defined here and cannot
  // drift apart through a hardcoded server-side default.
  //
  // The two strings differ in force on purpose. A16 knows the projection
  // is lateral, because the doctor said so -- it states a fact. M10 only
  // knows the top-1 similarity is below the reject threshold, and §6.2's
  // Note is that a correct frontal image from a different hospital
  // produces the same measurement -- so per M12 it states a DOUBT and
  // asks the doctor to check, rather than telling them the image is wrong.
  // A14 -- the declared projection selector on the upload flow.
  "upload.projectionLabel": "Projection (required)",
  "upload.projectionPA": "PA",
  "upload.projectionAP": "AP",
  "upload.projectionLATERAL": "Lateral",
  "upload.projectionNote":
    "Select the view stated on the requisition. RadAssist reports frontal chest X-rays (PA or AP).",
  "error.projection.declaredLateral":
    "Frontal view required. RadAssist reports frontal chest X-rays (PA or AP). Please upload the frontal image from this study.",
  "error.projection.frontalMismatch":
    "This does not appear to be a frontal chest X-ray. RadAssist reports frontal views only (PA or AP). If this is a frontal image, it may differ from the reference archive. Please check the view and try again.",

  "support.belowNote":
    "No retrieved case meets the minimum retrieval-support threshold. The agreement score alone does not indicate strong evidence. This does not mean no similar case exists — only that none of the cases retrieved met the threshold.",

  // ── step progress ─────────────────────────────────────────────────────────
  "step.running": "running",
  "step.skipped": "skipped",

  // ── PHI reveal slider ─────────────────────────────────────────────────────
  "phi.altMasked": "Masked chest X-ray",
  "phi.altOriginal": "Original chest X-ray, before masking",
  "phi.ariaReveal": "Reveal original image beneath the masked copy",
  "phi.caption": "Drag to reveal the original beneath the masked copy. Original shown from this session only. Not stored.",
};
