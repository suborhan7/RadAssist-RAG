"""
tests/conftest.py
====================================================================
Isolates the ENTIRE test session from the real, persistent backend/dev.db
a real running server actually uses.

Real bug found while working on Phase 12 (the frontend): app/database/base.py's
`engine`/`SessionLocal` are module-level singletons bound to whatever
DATABASE_URL resolves to at import time. Several integration tests
(test_generate_report_integration.py, test_comparison_integration.py,
test_explainability_integration.py, test_questionnaire_integration.py)
import that SAME shared `engine` directly and call
Base.metadata.create_all(engine)/drop_all(engine) to set up/tear down
their own schema. With no env override anywhere, that engine WAS the
real dev.db -- simply running `pytest` silently dropped every real table
in a developer's local database at test teardown. This has been true
since Phase 8; it never surfaced as a problem because no prior phase ran
a persistent dev server against dev.db at the same time the test suite
ran, until Phase 12's frontend made that a real, everyday workflow.

This must be the FIRST thing that executes in the test session, before
any other import anywhere -- Settings() is constructed at
app.core.config's IMPORT time, not lazily, so DATABASE_URL has to be set
in the environment before that module is ever imported by anything.
pytest guarantees conftest.py files are discovered and imported before
any test module is collected, which is what makes this reliable without
having to touch any of the four existing integration test files above.
"""
import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_BACKEND_DIR / 'test.db'}")
