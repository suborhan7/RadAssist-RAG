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


class HealthResponse(BaseModel):
    status: str


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