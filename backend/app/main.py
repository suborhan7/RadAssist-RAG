"""
app/main.py
====================================================================
FastAPI app assembly. Expensive singletons -- most importantly
BiomedCLIPAdapter, which loads the BiomedCLIP model -- are constructed
exactly ONCE at startup via the lifespan context manager and stored on
app.state, never per-request. RetrievalService/LabelVotingService are
wired from those singletons once and also stored on app.state; routes
(app/api/retrieval.py) read them off request.app.state rather than
constructing anything themselves.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.retrieval import router as retrieval_router
from app.infrastructure.biomedclip_adapter import BiomedCLIPAdapter
from app.infrastructure.chroma_store import ChromaVectorStore
from app.services.image_validator import ImageValidator
from app.services.label_voting_service import LabelVotingService
from app.services.retrieval_service import RetrievalService
from app.services.similarity_search import SimilaritySearchPolicy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan startup: loading BiomedCLIPAdapter (should log exactly once per app lifetime)")
    embedder = BiomedCLIPAdapter()
    vector_store = ChromaVectorStore()
    validator = ImageValidator()
    search_policy = SimilaritySearchPolicy()

    app.state.retrieval_service = RetrievalService(
        validator=validator,
        embedder=embedder,
        vector_store=vector_store,
        search_policy=search_policy,
    )
    app.state.label_voting_service = LabelVotingService()
    logger.info("lifespan startup complete")

    yield


app = FastAPI(title="RadAssist-RAG Backend", lifespan=lifespan)
app.include_router(retrieval_router)