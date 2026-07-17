"""
app/api/dashboard.py
====================================================================
GET /dashboard/stats (Phase 15). Thin route: a single call into
DashboardService, typed response serialization. Real counts scoped to
the authenticated doctor via `Depends(get_current_doctor)`, per
frontend/CLAUDE.md's explicit "use real counts from the API, not the
invented '38 of 142' style stat" instruction.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import DashboardStatsResponse
from app.domain.entities import Doctor
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> DashboardStatsResponse:
    service = DashboardService(db=db)
    stats = service.get_stats(current_doctor.id)
    return DashboardStatsResponse(
        my_reports=stats.my_reports,
        total_reports=stats.total_reports,
        my_patients=stats.my_patients,
        total_patients=stats.total_patients,
    )
