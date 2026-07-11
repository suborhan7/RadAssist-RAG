"""
app/database/base.py
====================================================================
SQLAlchemy 2.0 declarative base, engine, and session factory. Reads
DATABASE_URL from Settings -- no hardcoded connection string here.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.DATABASE_URL)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    # SQLite does not enforce FOREIGN KEY constraints unless told to, per
    # connection -- without this, retrieved_evidence.session_id could point
    # at a nonexistent retrieval_sessions row with no error. No-op on
    # non-SQLite backends (e.g. once Postgres is introduced).
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
