"""
app/api/system.py
====================================================================
GET /system/stats (Phase 16). Thin route: a single call into
SystemStatsService (built from the app.state.vector_store singleton,
same pattern as every other route reading it), typed response
serialization. Requires authentication (Depends(get_current_doctor)),
same as every other Phase 4-15 route, even though the data itself isn't
doctor-specific -- there is no genuinely public, unauthenticated route
in this system apart from GET /health.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_current_doctor
from app.api.schemas import SystemStatsResponse
from app.domain.entities import Doctor
from app.services.system_stats_service import SystemStatsService

router = APIRouter()


@router.get("/system/stats", response_model=SystemStatsResponse)
def get_system_stats(
    request: Request,
    current_doctor: Doctor = Depends(get_current_doctor),
) -> SystemStatsResponse:
    service = SystemStatsService(vector_store=request.app.state.vector_store)
    stats = service.get_stats()
    return SystemStatsResponse(
        masked_images_stored=stats.masked_images_stored,
        original_images_stored=stats.original_images_stored,
        index_size=stats.index_size,
        embedding_model=stats.embedding_model,
        embedding_version=stats.embedding_version,
        collection_name=stats.collection_name,
    )
