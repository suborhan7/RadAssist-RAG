## Phase 13 — Authentication & Doctor Ownership: Architecture (PROPOSED, NOT YET FROZEN)

**Status: draft, pending user review.** Do not implement until this section
is explicitly frozen, same discipline as every prior phase. This is a
correction of Phase 12's own gap #1 ("No authentication exists anywhere in
the backend... single-operator thesis demo, no authentication built in this
phase"), reopened at explicit user request to demonstrate multi-doctor
ownership.

### Why this is being reopened, stated plainly

Phase 12 froze "no auth" as a deliberate scope boundary, reasoned as "not
this thesis's core contribution." That reasoning was correct *at the time*.
The user has since decided multi-doctor demonstration has real thesis value
(showing shared-registry access with doctor-owned reports is itself a
piece of the system's design worth defending in front of examiners). This
phase does not contradict Phase 12's judgment — it supersedes the scope
decision on new information, which is exactly what "frozen unless a
critical issue is found" is supposed to allow for when the user, not the
implementer, decides the scope has changed.

### Decisions frozen (pending this section's approval)

1. **Self-registration**, not pre-seeded accounts. Any visitor can create a
   doctor account via `POST /auth/register`. No invite flow, no admin
   approval step — acceptable for a thesis demo; named explicitly as a
   scope boundary in Risks below, same as Phase 12 named "no auth" as one.
2. **Patients remain shared/institutional — no `doctor_id` on `patients`.**
   Any authenticated doctor can find and open any patient. This preserves
   Phase 11's `Patient` entity and `IPatientRepository` interface
   **unchanged** — no migration, no interface change, zero regression risk
   to Phase 11's frozen, tested code.
3. **Ownership attaches to the *work*, not the patient**: `retrieval_sessions`,
   `comparisons`, and `explanations` each gain a `doctor_id`. `reports` gains
   no column of its own — a report's owner is derived through
   `report.session_id -> retrieval_sessions.doctor_id`, the same
   single-source-of-truth principle already used elsewhere in this project
   (`master_metadata.csv` as the one place study state is computed, not
   duplicated). Two tables invented from scratch, three columns added,
   zero redundant ownership fields.
4. **Read is universal, write is owned.** Any authenticated doctor can
   *read* any patient, session, report, comparison, or explanation in the
   shared registry. Only the owning doctor may *write*: finalize a report,
   edit `final_content`, request regeneration, or initiate a new session
   against a patient. Creating a brand-new session/comparison/explanation
   makes the creating doctor its owner automatically — there is no
   "assign ownership" action.
5. **Auth mechanism**: Argon2 password hashing, JWT in an httpOnly cookie,
   a `get_current_doctor` FastAPI dependency injected into every route that
   currently has none. This is additive to every Phase 4–11 endpoint's
   *dependencies*, not to its request/response schema — no existing
   contract field changes shape.
6. **Enforcement lives in the service layer**, not the route layer — mirrors
   how `RetrievalService`, `ComparisonService`, etc. already own their
   business rules rather than leaving them in route handlers. A route that
   forgets to check ownership is one line; a service that forgets is the
   actual bug class this needs to prevent, so the check belongs where the
   mutation happens, not where the HTTP request lands.

### Entities (new)

```python
@dataclass(frozen=True)
class Doctor:
    id: str
    email: str
    password_hash: str
    full_name: str
    created_at: str
```

No changes to `Patient`, `Comparison`, or any Phase 8–11 entity's *shape* —
only new sibling fields at the persistence layer (see Database, below),
threaded through service method signatures as an additional
`current_doctor_id: str` parameter.

### Interfaces (new)

```python
class IDoctorRepository(Protocol):
    def create(self, email: str, password_hash: str, full_name: str) -> Doctor: ...
    def find_by_email(self, email: str) -> Doctor | None: ...
    def find_by_id(self, doctor_id: str) -> Doctor | None: ...

class IPasswordHasher(Protocol):
    def hash(self, plain: str) -> str: ...
    def verify(self, plain: str, hashed: str) -> bool: ...

class ITokenService(Protocol):
    def issue(self, doctor_id: str) -> str: ...
    def verify(self, token: str) -> str: ...   # returns doctor_id or raises
```

`IPatientRepository` is **not touched**. `IDeterministicComparator` is **not
touched** — comparison logic is ownership-blind by design; ownership is a
question of who *ran* the comparison, resolved one layer up in
`ComparisonService`, not inside the pure comparator.

### Database (additive only, Alembic batch mode — same tooling already used
in Phase 4 Step 10, not a new risk)

```
doctors:                        -- new
  id (UUID, PK)
  email (str, unique, indexed)
  password_hash (str)
  full_name (str)
  created_at

retrieval_sessions:              -- MODIFIED, additive only
  ... existing columns unchanged ...
  doctor_id (UUID, FK -> doctors.id, nullable)
  -- nullable: pre-Phase-13 sessions have none, identical precedent to
  -- Phase 11's patient_id addition to this same table

comparisons:                     -- MODIFIED, additive only
  ... existing columns unchanged ...
  doctor_id (UUID, FK -> doctors.id, nullable)
  -- records who RAN the comparison, which may differ from either report's
  -- author -- a doctor can compare another doctor's historical report
  -- against their own new one under the shared-registry model

explanations:                    -- MODIFIED, additive only
  ... existing columns unchanged ...
  doctor_id (UUID, FK -> doctors.id, nullable)
  -- records who ASKED, not who owns the underlying report

reports: no schema change. Ownership derived via
  reports.session_id -> retrieval_sessions.doctor_id
```

### Folder structure (additive to Phase 4–12's frozen layout)

```
backend/app/
|-- domain/entities/
|   `-- doctor.py                          # new
|-- application/interfaces/
|   `-- doctor_repository.py               # IDoctorRepository, new
|-- infrastructure/
|   |-- auth/
|   |   |-- password_hasher.py             # Argon2 wrapper, implements IPasswordHasher
|   |   `-- jwt_handler.py                 # implements ITokenService
|   `-- repositories/
|       `-- sql_doctor_repository.py       # new
|-- services/
|   `-- auth_service.py                    # register() / login() -- new
|-- api/
|   |-- deps.py                            # get_current_doctor dependency -- new
|   `-- routes/
|       `-- auth.py                        # POST /auth/register, POST /auth/login, GET /auth/me

frontend/src/app/
|-- login/page.tsx                         # new
|-- register/page.tsx                      # new
`-- page.tsx                               # Dashboard -- gains ownership framing, no route change
```

### API endpoints (new)

```
POST /auth/register   {email, password, full_name} -> {doctor, token}
POST /auth/login      {email, password}             -> {token}
GET  /auth/me         (auth required)                -> current doctor
```

Every existing Phase 4–11 endpoint gains `Depends(get_current_doctor)`.
Additive to the dependency graph only — no existing request or response
schema changes shape, so no OpenAPI-generated frontend type is broken,
only extended (new `doctor` field surfaces on session/report/comparison/
explanation response models, per Phase 12's precedent of generating types
from `/openapi.json` rather than hand-maintaining them).

### Sequence — ownership check on a write path (representative: finalize report)

```
Doctor B calls PATCH /reports/{id}/finalize
  -> get_current_doctor resolves JWT -> doctor_id = B
  -> ReportGenerationService.finalize(report_id, doctor_id=B)
       -> load report -> derive session.doctor_id via join
       -> if session.doctor_id != B: raise ForbiddenError (403)
       -> else: proceed exactly as Phase 8's frozen finalize logic
```

Read paths (`GET /patients/{id}/history`, `GET /reports/{id}`, etc.) gain
`Depends(get_current_doctor)` for *authentication* only — no ownership
comparison, since read is universal under the shared-registry decision.

### Step breakdown

1. `Doctor` entity + `IDoctorRepository` + `sql_doctor_repository.py` +
   `doctors` table migration
2. `IPasswordHasher` (Argon2) + `ITokenService` (JWT) + unit tests
3. `AuthService.register()` / `.login()` + `POST /auth/register`,
   `POST /auth/login`, `GET /auth/me`
4. `get_current_doctor` dependency; wire into every existing route
   (additive dependency only, one PR per Phase-4–11 router file to keep
   diffs reviewable against already-frozen code)
5. `doctor_id` columns on `retrieval_sessions`, `comparisons`,
   `explanations` + Alembic batch-mode migrations (three separate
   migrations, not one — matches this project's existing per-concern
   migration granularity)
6. Ownership check in `ReportGenerationService` (finalize, edit,
   regenerate) and `ComparisonService`/`ExplainabilityService` (creation
   only — reads stay universal)
7. Frontend: `login/`, `register/`, `api-client.ts` auth header/cookie,
   ownership chip + read-only banner on non-owned reports (reusable
   directly from the earlier visual design pass — this part of that spec
   never conflicted with anything, only the auth *existence* did)
8. Integration test: register two doctors -> doctor A creates a session +
   report on a shared patient -> doctor B reads it (200, read-only) ->
   doctor B attempts to finalize it (403) -> doctor B creates their own
   new session on the same patient (200, succeeds, owned by B)

### Testing strategy

Unit: password hashing round-trip, JWT issue/verify (including expired/
tampered token rejection), ownership-check helper in isolation.
Integration: the two-doctor flow in Step 8, end to end, real execution —
same discipline as every prior phase's integration test.

### Risks

- **Touches five frozen backend phases' services** (4, 8, 9, 10, 11) by
  threading `current_doctor_id` through existing method signatures. Each
  touch is additive (new required parameter, not a changed return type or
  altered business logic) but the surface area is real — recommend one
  isolated commit per service, full regression re-run after each, matching
  this project's own "confirmed by the user before proceeding at each
  gate" discipline rather than one large commit.
- **Self-registration has no access control on who can claim to be a
  doctor.** Acceptable for a thesis demo; must be named plainly as a scope
  boundary in the thesis, the same way Phase 12 named "no auth" as one.
- **SQLite + Alembic batch mode** required for three additive FK columns —
  known workaround, already used successfully in Phase 4 Step 10, not a
  new risk class.
- **`reports` has no `doctor_id` of its own.** This is a deliberate
  single-source-of-truth choice (§3), but it does mean every ownership
  check on a report requires a join through `retrieval_sessions` rather
  than a direct column read. Flagging so this isn't rediscovered as a
  surprise during implementation — it's a chosen tradeoff, not an
  oversight.
- **Existing Phase 12 frontend pages need auth guards retrofitted.** The
  guided upload flow (`patients/[patientId]/upload`) and the Radiologist
  Workspace must redirect to `/login` when unauthenticated without
  breaking their existing step-progress state machine.

### Explicitly not in this phase

- Password reset / email verification — self-registration has no email
  ownership proof; out of scope, name as future work.
- Role-based access (admin vs radiologist) — every registered doctor has
  identical permissions.
- Patient-level ownership or per-patient access control — explicitly
  rejected per the shared-registry decision (§2 above).
- Re-adopting the earlier design spec's `RA-{YYYY}-{NNNNNN}` patient ID
  format — Phase 11's `PAT-000001` format is real, tested, and already
  migrated; changing it now would be pure churn with no functional
  benefit and is out of scope for this phase.

---

**Once this section is reviewed and explicitly frozen, implementation
follows the same discipline as every prior phase: step-by-step, real
execution output at each gate, confirmed before proceeding to the next
step, `development_log.md` updated with an "Implementation & Validation"
section and a "How to Write This in Your Thesis" note when complete.**
