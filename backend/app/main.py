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
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.explainability import router as explainability_router
from app.api.generation import router as generation_router
from app.api.questionnaire import router as questionnaire_router
from app.api.retrieval import router as retrieval_router
from app.core.config import settings
from app.infrastructure.biomedclip_adapter import BiomedCLIPAdapter
from app.infrastructure.chroma_store import ChromaVectorStore
from app.infrastructure.ollama_client import OllamaClient
from app.services.context_builder import ContextBuilder
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan startup: loading BiomedCLIPAdapter (should log exactly once per app lifetime)")
    embedder = BiomedCLIPAdapter()
    vector_store = ChromaVectorStore()
    validator = ImageValidator()
    search_policy = SimilaritySearchPolicy()

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
    logger.info("lifespan startup complete")

    yield


app = FastAPI(title="RadAssist-RAG Backend", lifespan=lifespan)
app.include_router(retrieval_router)
app.include_router(generation_router)
app.include_router(questionnaire_router)
app.include_router(explainability_router)