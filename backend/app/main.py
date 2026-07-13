"""
app/main.py
====================================================================
FastAPI app assembly. Expensive singletons -- most importantly
BiomedCLIPAdapter, which loads the BiomedCLIP model -- are constructed
exactly ONCE at startup via the lifespan context manager and stored on
app.state, never per-request. RetrievalService/LabelVotingService/
ContextBuilder/LLMOrchestrator/ResponseValidator/ReportFormatter are wired
from those singletons once and also stored on app.state; routes
(app/api/retrieval.py, app/api/generation.py) read them off
request.app.state rather than constructing anything themselves.
`vector_store` itself is also stored directly on app.state (not just
buried inside retrieval_service) since Phase 8's ReportGenerationService
needs the same ChromaVectorStore instance independently, for get_by_ids().
`prompt_builder` is likewise stored directly on app.state (Phase 10) --
previously constructed inline as an LLMOrchestrator constructor arg only,
with no standalone reference route code could reach; ExplainabilityService
needs the same PromptBuilder instance independently, for
build_explanation_prompt().

PatientService (Phase 11) is NOT stored on app.state -- unlike every
service above, it depends on nothing but a per-request db session (no
shared collaborator singleton to wire), so app/api/patients.py constructs
it directly in each route, same as it would even if a singleton existed
to read here. `deterministic_comparator` IS stored on app.state (Phase
11) -- same reasoning as `response_validator`: it takes no db session,
only an optional taxonomy_classes override, so it is constructed once and
reused, not rebuilt per request. app/api/comparisons.py's ComparisonService
mixes both patterns: patient_repository is a per-request PatientService
(db-dependent), while deterministic_comparator/prompt_builder/
llm_orchestrator are read off app.state (shared singletons).

CORS (Phase 12 Step 1): a real, necessary backend change, not silent
scope creep into frontend/'s territory -- every route above was built and
tested Phases 4-11 with no browser origin involved at all (TestClient/
pytest bypass CORS entirely), so this is genuinely new backend surface
area, flagged as such rather than folded in unannounced. Local dev only,
per the frozen Phase 12 spec's explicit "deployment packaging out of
scope" decision; `settings.CORS_ALLOWED_ORIGINS` defaults to the Next.js
dev server's origin (http://localhost:3000), not hardcoded here.

`phi_masker` (Phase 12 Step 7): a real prerequisite fix for the
Comparison page -- POST /retrieve previously deleted every uploaded query
image immediately after embedding, so there was no way to redisplay a
past visit's X-ray at all. Persisting the raw upload would have broken
this system's own PHI-masking invariant (every image this system stores/
serves has been masked first, since Phase 1); PHIMasker is loaded once
here, same "expensive singleton, constructed exactly once" rule as
BiomedCLIPAdapter, and POST /retrieve now masks the upload before
persisting it -- see app/api/retrieval.py.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.comparisons import router as comparisons_router
from app.api.explainability import router as explainability_router
from app.api.generation import router as generation_router
from app.api.patients import router as patients_router
from app.api.questionnaire import router as questionnaire_router
from app.api.reports import router as reports_router
from app.api.retrieval import router as retrieval_router
from app.core.config import settings
from app.infrastructure.biomedclip_adapter import BiomedCLIPAdapter
from app.infrastructure.chroma_store import ChromaVectorStore
from app.infrastructure.ollama_client import OllamaClient
from app.services.context_builder import ContextBuilder
from app.services.deterministic_comparator import DeterministicComparator
from app.services.image_validator import ImageValidator
from app.services.label_voting_service import LabelVotingService
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.prompt_builder import PromptBuilder
from app.services.questionnaire_templates import QuestionnaireTemplateProvider
from app.services.report_formatter import ReportFormatter
from app.services.response_validator import ResponseValidator
from app.services.retrieval_service import RetrievalService
from app.services.similarity_search import SimilaritySearchPolicy
from app.services.structural_validator import StructuralValidator
from shared.phi_masking.masker import PHIMasker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan startup: loading BiomedCLIPAdapter (should log exactly once per app lifetime)")
    embedder = BiomedCLIPAdapter()
    vector_store = ChromaVectorStore()
    validator = ImageValidator()
    search_policy = SimilaritySearchPolicy()
    logger.info("lifespan startup: loading PHIMasker (EasyOCR model load, should log exactly once)")
    app.state.phi_masker = PHIMasker()

    app.state.vector_store = vector_store
    app.state.retrieval_service = RetrievalService(
        validator=validator,
        embedder=embedder,
        vector_store=vector_store,
        search_policy=search_policy,
    )
    app.state.label_voting_service = LabelVotingService()
    app.state.context_builder = ContextBuilder()
    prompt_builder = PromptBuilder()
    app.state.prompt_builder = prompt_builder
    app.state.llm_orchestrator = LLMOrchestrator(
        prompt_builder=prompt_builder,
        llm_client=OllamaClient(),
        structural_validator=StructuralValidator(),
        transport_retry_count=settings.LLM_TRANSPORT_RETRY_COUNT,
        content_retry_count=settings.LLM_CONTENT_RETRY_COUNT,
    )
    app.state.response_validator = ResponseValidator()
    app.state.report_formatter = ReportFormatter()
    app.state.questionnaire_provider = QuestionnaireTemplateProvider()
    app.state.deterministic_comparator = DeterministicComparator()
    logger.info("lifespan startup complete")

    yield


app = FastAPI(title="RadAssist-RAG Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(retrieval_router)
app.include_router(generation_router)
app.include_router(questionnaire_router)
app.include_router(explainability_router)
app.include_router(patients_router)
app.include_router(comparisons_router)
app.include_router(reports_router)