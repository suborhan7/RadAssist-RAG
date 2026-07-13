"""
app/api/dependencies.py
====================================================================
Shared FastAPI dependencies used by more than one route module.
get_db() was previously duplicated identically in both api/retrieval.py
(Phase 4) and api/generation.py (Phase 8) -- consolidated here since
neither is a frozen interface, unlike the get_db()-in-retrieval.py
duplication that would have required touching a frozen file to fix.
"""
from __future__ import annotations

from app.database.base import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
