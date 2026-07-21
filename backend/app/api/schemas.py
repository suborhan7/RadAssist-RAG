"""
app/api/schemas.py
====================================================================
Pydantic response models for the API layer only -- these are HTTP-boundary
DTOs, not domain entities (app/domain/entities.py stays framework-free by
design; see that file's own docstring). Field-for-field, RetrieveResponse
mirrors the frozen response contract (development_log.md, Phase 4
"Input/output contracts") plus the Step 11 voted_labels extension, so
FastAPI's generated OpenAPI schema actually documents the real shape
instead of an unspecified object.

GenerateReportResponse (Phase 8) mirrors that same frozen-response-contract
discipline from the start -- typed models built up front, not retrofitted
after an untyped-dict gap like Phase 4 Step 12 had to fix.
"""
from __future__ import annotations

from pydantic import BaseModel


class ServiceStatusResponse(BaseModel):
    status: str  # "ok" | "degraded" | "unreachable"
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    # Priority §16.1 (design_specification.md): real backend-half of the
    # §8.2 four-service status strip. Optional/nullable so existing
    # callers reading only `status` (e.g. the Dashboard's simple ok/
    # unreachable indicator) are unaffected -- purely additive.
    fastapi: ServiceStatusResponse | None = None
    ollama: ServiceStatusResponse | None = None
    chromadb: ServiceStatusResponse | None = None
    gpu: ServiceStatusResponse | None = None


class RetrievedCaseResponse(BaseModel):
    rank: int
    similarity: float
    study_uid: str
    primary_label: str
    label_set: str
    cluster_id: int
    findings: str
    impression: str
    image_path: str


class VotedLabelResponse(BaseModel):
    label: str
    vote_weight: float
    agreement: float


class RetrieveResponse(BaseModel):
    session_id: str
    retrieval_time_ms: int
    embedding_model: str
    embedding_version: str
    collection_name: str
    retrieved_cases: list[RetrievedCaseResponse]
    voted_labels: list[VotedLabelResponse]


class ReportContentResponse(BaseModel):
    examination: str
    clinical_history: str
    technique: str
    findings: str
    impression: str
    recommendation: str
    disclaimer: str


class FormattedReportResponse(BaseModel):
    content: ReportContentResponse
    language: str
    report_date: str
    section_headers: dict[str, str]


class ValidationResponse(BaseModel):
    is_clean: bool
    warnings: list[str]


class GenerationMetadataResponse(BaseModel):
    llm_model: str
    llm_temperature: float
    embedding_model: str
    embedding_version: str
    collection_name: str


class GenerateReportResponse(BaseModel):
    report_id: str
    session_id: str
    formatted_report: FormattedReportResponse
    validation: ValidationResponse
    generation_metadata: GenerationMetadataResponse


class QuestionnaireQuestionResponse(BaseModel):
    key: str
    text: str
    input_type: str


class QuestionnaireResponse(BaseModel):
    session_id: str
    based_on_label: str
    questions: list[QuestionnaireQuestionResponse]


class ExplanationResponse(BaseModel):
    id: str
    report_id: str
    question: str
    answer: str
    created_at: str
    doctor_id: str | None = None


class PatientResponse(BaseModel):
    id: str
    patient_code: str
    name: str
    date_of_birth: str
    gender: str


class PatientHistoryReportResponse(BaseModel):
    id: str
    language: str
    status: str
    ai_content: ReportContentResponse
    created_at: str
    doctor_id: str | None = None


class ComparisonFactsResponse(BaseModel):
    previous_report_id: str
    current_report_id: str
    resolved_findings: list[str]
    persistent_findings: list[str]
    new_findings: list[str]
    days_between_studies: int


class ComparisonResponse(BaseModel):
    id: str
    patient_id: str
    previous_report_id: str
    current_report_id: str
    facts: ComparisonFactsResponse
    narrative: str
    created_at: str
    doctor_id: str | None = None


class ReportAuditLogEntryResponse(BaseModel):
    """Phase 17: one row per successful PATCH /reports/{id} edit. Nested on
    ReportDetailResponse rather than a separate endpoint -- same "embed the
    related list on the detail response" convention this schema already
    uses for retrieved_cases, not a new precedent."""

    id: str
    doctor_id: str
    action: str
    at: str


class ReportDetailResponse(BaseModel):
    """Phase 12: GET /reports/{report_id} -- reuses ReportContentResponse/
    ValidationResponse/GenerationMetadataResponse/RetrievedCaseResponse
    rather than duplicating their field definitions, same discipline as
    every prior schema reuse in this project. patient_id is nullable --
    a report's underlying RetrievalSession may predate Phase 11's patient
    linkage, or may never have had a patient_id supplied.

    Phase 17 additions (additive only): `content` now sources
    final_content (what the report currently says); `ai_draft_content` is
    new, the immutable AI draft, for the frontend's "Restore AI Draft"
    action. `finalized_at`/`finalized_by` are nullable -- only set once a
    report has actually been finalized. `audit_log` is the edit history,
    oldest first."""

    report_id: str
    session_id: str
    patient_id: str | None
    content: ReportContentResponse
    ai_draft_content: ReportContentResponse
    language: str
    status: str
    validation: ValidationResponse
    generation_metadata: GenerationMetadataResponse
    report_date: str
    created_at: str
    retrieved_cases: list[RetrievedCaseResponse]
    doctor_id: str | None = None
    finalized_at: str | None = None
    finalized_by: str | None = None
    audit_log: list[ReportAuditLogEntryResponse] = []


class ReportListItemResponse(BaseModel):
    """GET /reports -- ownership-scoped, recency-ordered list. General
    enough to later back a full My Reports page, not a Dashboard-only
    shape: no evidence/agreement (that needs a real vector-store query
    per report, a real cost a list endpoint shouldn't impose on every
    caller -- see ReportListItem's own docstring), but content/
    ai_draft_content are both included so a caller can compute Phase 18's
    Report Edit Percentage via the existing computeReportDiff() with zero
    new logic."""

    report_id: str
    patient_id: str | None
    patient_name: str | None
    patient_code: str | None
    status: str
    report_date: str
    created_at: str
    content: ReportContentResponse
    ai_draft_content: ReportContentResponse


class RegenerateSectionResponse(BaseModel):
    """Phase 19: POST /reports/{report_id}/regenerate-section. `candidate`,
    not `content` -- this codebase already overloads "content" heavily
    (ReportContent, final_content, ai_draft_content); naming this field
    distinctly makes "not yet persisted" part of the name itself, not just
    a comment (phase19_section_regeneration_architecture.md's Endpoints
    section). Nothing about this call is written to final_content or
    logged anywhere -- accepting the candidate is a normal
    PATCH /reports/{report_id} call, made separately by the caller.

    `context_incomplete` is true only when this report predates
    questionnaire_answers/clinical_notes persistence (both NULL together,
    Phase 19 Decision 4) -- the candidate was generated from retrieval
    evidence alone, without whatever questionnaire answers or clinical
    notes the ORIGINAL generation may have used. The frontend surfaces
    this as an honest warning, not a silent gap."""

    field: str
    candidate: str
    context_incomplete: bool


class DoctorResponse(BaseModel):
    """Phase 13. Deliberately excludes password_hash -- never serialized
    back to any client, registering or otherwise.

    Phase 16: bmdc_number/default_* are self-only fields (Settings/Profile).
    They belong ONLY here, never on DoctorPublicResponse below -- same
    reasoning that already kept email/created_at out of that one."""

    id: str
    email: str
    full_name: str
    created_at: str
    bmdc_number: str | None = None
    default_top_k: int | None = None
    default_language: str | None = None
    default_questionnaire_skip: bool | None = None
    default_rail_state: str | None = None
    default_export_format: str | None = None


class UpdateProfileRequest(BaseModel):
    """Phase 16: PATCH /auth/me. Every field optional -- a partial update,
    not a full replace; omitted fields are left untouched. email is
    deliberately not here -- no re-verification workflow exists for
    changing it."""

    full_name: str | None = None
    bmdc_number: str | None = None
    default_top_k: int | None = None
    default_language: str | None = None
    default_questionnaire_skip: bool | None = None
    default_rail_state: str | None = None
    default_export_format: str | None = None


class DoctorPublicResponse(BaseModel):
    """Phase 15: GET /doctors/{doctor_id}, for rendering another doctor's
    name on an OwnershipChip. Deliberately narrower than DoctorResponse --
    excludes email/created_at, not just password_hash -- a doctor's own
    identity is fully visible to themselves (GET /auth/me), but the
    shared-registry read model (§2 of phase13_auth_architecture.md) only
    needs a name to attribute someone else's work, not their contact
    details. Phase 16: bmdc_number/default_* are likewise excluded here on
    purpose -- self-only data, never exposed via the public
    name-resolution endpoint."""

    id: str
    full_name: str


class RegisterResponse(BaseModel):
    doctor: DoctorResponse
    token: str


class LoginResponse(BaseModel):
    token: str


class LogoutResponse(BaseModel):
    success: bool


class DashboardStatsResponse(BaseModel):
    """Phase 15. Real counts, per frontend/CLAUDE.md's explicit
    instruction not to invent a placeholder stat."""

    my_reports: int
    total_reports: int
    my_patients: int
    total_patients: int
    examinations_today: int
    awaiting_review: int
    oldest_awaiting_review_report_id: str | None = None
    oldest_awaiting_review_report_date: str | None = None


class SystemStatsResponse(BaseModel):
    """Phase 16: GET /system/stats, design_specification.md §8.16's
    "storage & privacy" + index-stats section.

    original_images_stored is a STRUCTURAL guarantee, not a live query --
    confirmed by reading app/api/retrieval.py: POST /retrieve is the only
    file-upload endpoint in this backend, and the raw upload only ever
    exists as a tempfile.NamedTemporaryFile, synchronously deleted in
    _saved_upload's `finally` block before the request even returns.
    There is no directory this system could count originals in, so this
    is always 0 by construction, not a coincidence of current usage."""

    masked_images_stored: int
    original_images_stored: int
    index_size: int
    embedding_model: str
    embedding_version: str
    collection_name: str