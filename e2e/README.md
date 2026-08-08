# E2E owner-flow harness

Drives the **owner happy-path through the real UI** (register → upload a real
chest X-ray → retrieve → questionnaire → generate → owner workspace → edit →
finalize → compare) over the Chrome DevTools Protocol, against the **real**
backend + Chroma + Ollama, and verifies it end to end.

Two safety properties are the whole point of this harness:

1. **Disposable database, fail closed.** The backend is started against a
   `test-e2e.db` seeded from a fixture (a copy of `dev.db`), and that file is
   dropped at teardown. The real `dev.db` is never opened by the backend.
   `E2E_DB` is **required** — the harness never guesses a target, so it can never
   fall back to `dev.db`; it refuses (exit 2) if `E2E_DB` is unset or equals the
   fixture/dev DB (`harness.assertSafeTarget`). A **pre-flight** then proves the
   `DATABASE_URL` override actually took effect (via a throwaway write it removes)
   *before* the expensive flow runs.

2. **ID-scoped cleanup.** The run records every id it creates (doctor, report,
   session, comparisons, uploaded image paths) and deletes **exactly those**.
   `db.mjs` contains no date-, name-, email-, or "created today" predicate — a
   row the run did not record cannot be reached. This replaces the prior ad-hoc
   cleanup, whose `created_at LIKE '2026-08-03%'` investigation nearly deleted a
   real account.

## Run

```bash
# owner happy-path proof (disposable DB + ID-scoped cleanup):
E2E_DB=backend/test-e2e.db node e2e/run.mjs

# read-only ownership proof (a second doctor is blocked at UI *and* API):
E2E_DB=backend/test-e2e.db node e2e/readonly-ownership.mjs
```

Exit `0` = the flow's assertions held **and** `dev.db` row counts were unchanged.
`readonly-ownership.mjs` additionally asserts a non-owner gets `403` on every
write (PATCH / finalize / regenerate) while `GET` stays `200`, and that the
report's `updated_at` is unchanged by the rejected writes.

## Files

- `run.mjs` — owner happy-path orchestrator.
- `readonly-ownership.mjs` — ownership / read-only verification (doctor A vs B).
- `owner-flow.mjs` — the CDP owner-flow driver (records the ids it creates).
- `harness.mjs` — shared orchestration: fail-closed guard, backend/Edge lifecycle,
  pre-flight override check, minimal CDP client.
- `db.mjs` — `node:sqlite` disposable-DB helpers + ID-scoped cleanup (no predicates).

## Configuration (env — no hardcoded DB path in the flow)

| Var | Default | Meaning |
| --- | --- | --- |
| `E2E_DB` | **required** | Disposable target DB. Unset ⇒ refuse; must NOT be the fixture. |
| `E2E_FIXTURE` | `backend/dev.db` | Snapshot copied into `E2E_DB` (read-only). |
| `E2E_API` / `E2E_FRONTEND` | `localhost:8000` / `:3000` | Backend / frontend base URLs. |
| `E2E_BACKEND_PORT` | `8000` | Port the harness starts the backend on. |
| `E2E_PYTHON` | `.venv/Scripts/python.exe` | Python for uvicorn (set `.venv/bin/python` on Linux). |
| `E2E_EDGE` | Windows Edge path | Chromium/Edge binary for headless CDP. |
| `E2E_IMAGE` | a dataset CXR | Chest X-ray to upload. |
| `E2E_PATIENT_ID` | `PAT-000003`'s id | An existing patient **with priors** (so compare works). |
| `E2E_OUT` | *(none)* | If set, per-state screenshots are written here. |

Requires the frontend dev server and Ollama running; the harness starts and
stops the backend itself. Runtime artifacts (`test-e2e.db*`, `e2e/.edge-profile/`,
screenshots) are gitignored.
