/**
 * lib/api-client.ts
 * ====================================================================
 * Minimal typed API client. Types are read directly from the
 * OpenAPI-generated `paths` interface (lib/generated/api.d.ts,
 * regenerated from the running backend's /openapi.json via
 * `npm run generate-types`) rather than hand-written response
 * interfaces, so a backend contract change that isn't regenerated for
 * shows up as a real TypeScript error at the call site, not a silent
 * runtime mismatch. One typed function per endpoint, added as each page
 * needs it, rather than a full client generated up front for endpoints
 * nothing calls yet.
 *
 * ApiError carries the real HTTP status so callers can distinguish
 * failure modes the backend itself distinguishes -- e.g.
 * GET /patients/search's 400 ("malformed request: no usable lookup
 * params") is a real error, but a 200 with an empty array ("well-formed
 * search, zero matches") is NOT an error at all, per Phase 11 Step 4's
 * backend semantics. That distinction has to be preserved here, not
 * collapsed into "the fetch succeeded or it didn't."
 *
 * Phase 13: every request now sends `credentials: "include"` -- the
 * real auth mechanism is an httpOnly cookie (radassist_token) set by
 * POST /auth/register and /auth/login, and every other route now
 * requires it (Depends(get_current_doctor), Phase 13a Step 5). Without
 * `credentials: "include"`, fetch() never sends cookies on a
 * cross-origin request (frontend :3000, backend :8000 are different
 * origins even though same-site), so every call would silently 401
 * despite a valid cookie sitting in the browser. retrieveWithProgress()
 * gets the equivalent via `xhr.withCredentials = true`.
 */
import { API_URL } from "./env";
import type { paths } from "./generated/api";

type HealthResponse =
  paths["/health"]["get"]["responses"][200]["content"]["application/json"];

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : String(item)))
          .join("; ");
      }
      // LLMGenerationValidationError's 422 (app/api/generation.py) returns
      // detail as an object ({message, last_raw_response,
      // last_validation_errors}), not a string or array -- the other two
      // shapes FastAPI itself produces (plain HTTPException(detail=str)
      // and 422 validation-error lists).
      if (detail && typeof detail === "object" && "message" in detail) {
        return String((detail as { message: unknown }).message);
      }
    }
  } catch {
    // response body wasn't JSON -- fall through to the generic message
  }
  return null;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) {
    throw new Error(`GET /health failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<HealthResponse>;
}

type CreatePatientRequest =
  paths["/patients"]["post"]["requestBody"]["content"]["application/json"];
type PatientResponse =
  paths["/patients"]["post"]["responses"][200]["content"]["application/json"];

export async function createPatient(body: CreatePatientRequest): Promise<PatientResponse> {
  const response = await fetch(`${API_URL}/patients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `POST /patients failed: ${response.status}`);
  }
  return response.json() as Promise<PatientResponse>;
}

type SearchPatientsQuery = NonNullable<
  paths["/patients/search"]["get"]["parameters"]["query"]
>;
type SearchPatientsResponse =
  paths["/patients/search"]["get"]["responses"][200]["content"]["application/json"];

export async function searchPatients(
  query: SearchPatientsQuery,
): Promise<SearchPatientsResponse> {
  const params = new URLSearchParams();
  if (query.code) params.set("code", query.code);
  if (query.name) params.set("name", query.name);
  if (query.dob) params.set("dob", query.dob);

  const response = await fetch(`${API_URL}/patients/search?${params.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `GET /patients/search failed: ${response.status}`);
  }
  return response.json() as Promise<SearchPatientsResponse>;
}

type GetPatientResponse =
  paths["/patients/{patient_id}"]["get"]["responses"][200]["content"]["application/json"];

export async function getPatient(patientId: string): Promise<GetPatientResponse> {
  const response = await fetch(`${API_URL}/patients/${patientId}`, { credentials: "include" });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `GET /patients/${patientId} failed: ${response.status}`);
  }
  return response.json() as Promise<GetPatientResponse>;
}

type PatientHistoryResponse =
  paths["/patients/{patient_id}/history"]["get"]["responses"][200]["content"]["application/json"];

export async function getPatientHistory(patientId: string): Promise<PatientHistoryResponse> {
  const response = await fetch(`${API_URL}/patients/${patientId}/history`, { credentials: "include" });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(
      response.status,
      detail ?? `GET /patients/${patientId}/history failed: ${response.status}`,
    );
  }
  return response.json() as Promise<PatientHistoryResponse>;
}

type RetrieveResponse =
  paths["/retrieve"]["post"]["responses"][200]["content"]["application/json"];

/**
 * Uses XMLHttpRequest, not fetch(), specifically so upload progress is a
 * real signal, not a guess: `xhr.upload.onload` fires when the browser
 * has actually finished SENDING the multipart body (the real end of the
 * "uploading" phase), distinct from `xhr.onload`, which fires only once
 * the full response comes back (the real end of "retrieving_evidence" --
 * server-side image validation + BiomedCLIP embedding + ChromaDB
 * retrieval + voting). fetch() exposes no upload-progress event at all,
 * which would force guessing where "uploading" ends and "retrieving_evidence"
 * begins -- these two callbacks are genuine browser-reported milestones
 * within the SAME real request, not simulated timing.
 */
export function retrieveWithProgress(
  file: File,
  options: { topK?: number; minSimilarity?: number; patientId?: string },
  callbacks: { onUploadComplete: () => void },
): Promise<RetrieveResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("top_k", String(options.topK ?? 5));
    formData.append("min_similarity", String(options.minSimilarity ?? 0.0));
    if (options.patientId) formData.append("patient_id", options.patientId);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/retrieve`);
    xhr.withCredentials = true;
    xhr.upload.onload = () => callbacks.onUploadComplete();
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as RetrieveResponse);
      } else {
        let detail: string | null = null;
        try {
          const parsed: unknown = JSON.parse(xhr.responseText);
          if (parsed && typeof parsed === "object" && "detail" in parsed) {
            detail = String((parsed as { detail: unknown }).detail);
          }
        } catch {
          // response body wasn't JSON -- fall through to the generic message
        }
        reject(new ApiError(xhr.status, detail ?? `POST /retrieve failed: ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("POST /retrieve: network error"));
    xhr.send(formData);
  });
}

type QuestionnaireResponse =
  paths["/questionnaire/{session_id}"]["get"]["responses"][200]["content"]["application/json"];

export async function getQuestionnaire(sessionId: string): Promise<QuestionnaireResponse> {
  const response = await fetch(`${API_URL}/questionnaire/${sessionId}`, { credentials: "include" });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(
      response.status,
      detail ?? `GET /questionnaire/${sessionId} failed: ${response.status}`,
    );
  }
  return response.json() as Promise<QuestionnaireResponse>;
}

type GenerateReportRequest =
  paths["/generate-report"]["post"]["requestBody"]["content"]["application/json"];
type GenerateReportResponse =
  paths["/generate-report"]["post"]["responses"][200]["content"]["application/json"];

export async function generateReport(
  body: GenerateReportRequest,
): Promise<GenerateReportResponse> {
  const response = await fetch(`${API_URL}/generate-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `POST /generate-report failed: ${response.status}`);
  }
  return response.json() as Promise<GenerateReportResponse>;
}

type ReportDetailResponse =
  paths["/reports/{report_id}"]["get"]["responses"][200]["content"]["application/json"];

export async function getReport(reportId: string): Promise<ReportDetailResponse> {
  const response = await fetch(`${API_URL}/reports/${reportId}`, { credentials: "include" });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `GET /reports/${reportId} failed: ${response.status}`);
  }
  return response.json() as Promise<ReportDetailResponse>;
}

type ExplainRequest =
  paths["/reports/{report_id}/explain"]["post"]["requestBody"]["content"]["application/json"];
type ExplainResponse =
  paths["/reports/{report_id}/explain"]["post"]["responses"][200]["content"]["application/json"];

/**
 * 404 (malformed/nonexistent report_id) and 502 (real LLM transport
 * failure, found and fixed as a real backend gap in Phase 12 Step 6 --
 * see app/api/explainability.py) are both real, distinct failure modes
 * this client must be able to distinguish, not collapse into "the
 * request failed" -- ApiError.status carries the real HTTP status back
 * to the caller for exactly this reason.
 */
export async function explainReport(reportId: string, question: string): Promise<ExplainResponse> {
  const body: ExplainRequest = { question };
  const response = await fetch(`${API_URL}/reports/${reportId}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(
      response.status,
      detail ?? `POST /reports/${reportId}/explain failed: ${response.status}`,
    );
  }
  return response.json() as Promise<ExplainResponse>;
}

type CreateComparisonRequest =
  paths["/comparisons"]["post"]["requestBody"]["content"]["application/json"];
type ComparisonResponse =
  paths["/comparisons"]["post"]["responses"][200]["content"]["application/json"];

/**
 * Both real backend failure modes (NoPriorReportError and
 * ReportNotFoundError, Phase 11) map to 404 but arrive with distinct
 * prefixed detail messages ("No prior report available: ..." vs "Report
 * not found: ...") -- ApiError.message already carries that
 * distinguishing text through unmodified, so the UI can show it directly
 * rather than re-deriving which failure occurred from the status code
 * alone (which can't, by design -- see app/api/comparisons.py).
 */
export async function createComparison(
  body: CreateComparisonRequest,
): Promise<ComparisonResponse> {
  const response = await fetch(`${API_URL}/comparisons`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `POST /comparisons failed: ${response.status}`);
  }
  return response.json() as Promise<ComparisonResponse>;
}

/** Raw image bytes (GET /retrieval-sessions/{session_id}/image, Phase 12
 * Step 7) are served directly by the backend, not JSON -- this just
 * builds the URL for a plain <img src=...>, no fetch/parsing needed. */
export function retrievalSessionImageUrl(sessionId: string): string {
  return `${API_URL}/retrieval-sessions/${sessionId}/image`;
}

type RegisterRequest =
  paths["/auth/register"]["post"]["requestBody"]["content"]["application/json"];
type RegisterResponse =
  paths["/auth/register"]["post"]["responses"][200]["content"]["application/json"];

/**
 * The response body's `token` field is deliberately ignored by every
 * caller here -- the real session mechanism is the httpOnly cookie the
 * backend already set on this same response (Set-Cookie: radassist_token,
 * per Phase 13a). Storing the body's token in JS state/localStorage would
 * duplicate the session in a location an XSS payload COULD read, defeating
 * the entire point of making the cookie httpOnly in the first place.
 */
export async function registerDoctor(body: RegisterRequest): Promise<RegisterResponse> {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `POST /auth/register failed: ${response.status}`);
  }
  return response.json() as Promise<RegisterResponse>;
}

type LoginRequest =
  paths["/auth/login"]["post"]["requestBody"]["content"]["application/json"];
type LoginResponse =
  paths["/auth/login"]["post"]["responses"][200]["content"]["application/json"];

export async function loginDoctor(body: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `POST /auth/login failed: ${response.status}`);
  }
  return response.json() as Promise<LoginResponse>;
}

type CurrentDoctorResponse =
  paths["/auth/me"]["get"]["responses"][200]["content"]["application/json"];

/**
 * 401 (no cookie, or an expired/invalid one) is the normal "not logged
 * in" case here, not a real error -- callers use this to check auth
 * state (e.g. redirecting to /login), so it returns null on 401 instead
 * of throwing, unlike every other function in this client.
 */
export async function getCurrentDoctor(): Promise<CurrentDoctorResponse | null> {
  const response = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
  if (response.status === 401) return null;
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `GET /auth/me failed: ${response.status}`);
  }
  return response.json() as Promise<CurrentDoctorResponse>;
}

type DoctorPublicResponse =
  paths["/doctors/{doctor_id}"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Phase 15: resolves an arbitrary doctor_id to a display name for
 * OwnershipChip's "other doctor" case (design_specification.md §7).
 * Deliberately returns only {id, full_name} -- another doctor's email
 * isn't this caller's business, per the backend route's own docstring.
 */
export async function getDoctor(doctorId: string): Promise<DoctorPublicResponse> {
  const response = await fetch(`${API_URL}/doctors/${doctorId}`, { credentials: "include" });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `GET /doctors/${doctorId} failed: ${response.status}`);
  }
  return response.json() as Promise<DoctorPublicResponse>;
}

type DashboardStatsResponse =
  paths["/dashboard/stats"]["get"]["responses"][200]["content"]["application/json"];

/**
 * Phase 15: real counts for the Dashboard's ownership framing --
 * "your reports vs. the shared registry" -- per frontend/CLAUDE.md's
 * explicit instruction not to invent a placeholder stat.
 */
export async function getDashboardStats(): Promise<DashboardStatsResponse> {
  const response = await fetch(`${API_URL}/dashboard/stats`, { credentials: "include" });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail ?? `GET /dashboard/stats failed: ${response.status}`);
  }
  return response.json() as Promise<DashboardStatsResponse>;
}
