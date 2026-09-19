"""
app/services/exceptions.py
====================================================================
Service-level exceptions shared across phases. Phase 7 (LLM Orchestrator):
two independent failure modes, two distinct exception types -- transport
failure (Ollama unreachable/timed out) and content failure (structural
validation never passed) are different problems with different retry
budgets, and must not be conflated into one exception type. Phase 8
(ReportGenerationService): SessionNotFoundError, distinguishable from any
other failure inside generate() by exception type, not by string matching.
Phase 10 (ExplainabilityService): ReportNotFoundError -- a NEW type, not a
reuse of SessionNotFoundError, since "no RetrievalSession for this
session_id" and "no ReportRecord for this report_id" are different lookups
against different tables; conflating them would make a caller's exception
handler (and its error message) describe the wrong missing resource.
Phase 11 (ComparisonService): a malformed/nonexistent
compare_against_report_id REUSES ReportNotFoundError rather than a new
type -- unlike the SessionNotFoundError/ReportNotFoundError split above,
this is the exact same failure mode against the exact same table as
current_report_id's own lookup (a specific report_id was looked up and no
ReportRecord row exists for it), so conflating them here is correct, not a
lapse of the "distinct failure modes deserve distinct types" principle.
NoPriorReportError IS a genuinely new type: "patient has no earlier report
to compare against" (the first-visit case, no compare_against_report_id
supplied) is not a failed lookup at all -- no report_id was ever looked up
and missed, there is simply no candidate to look up in the first place.
Conflating that with ReportNotFoundError would make a caller's exception
handler describe a lookup failure that never happened.
"""
from __future__ import annotations


class LLMTransportError(Exception):
    """Ollama unreachable or timed out after the transport retry budget."""


class LLMGenerationValidationError(Exception):
    """Content retry budget exhausted; structural validation never passed."""

    def __init__(self, last_raw_response: str, last_validation_errors: list[str]) -> None:
        super().__init__(
            f"LLM generation validation failed after exhausting the content retry "
            f"budget. Last validation errors: {last_validation_errors}"
        )
        self.last_raw_response = last_raw_response
        self.last_validation_errors = last_validation_errors


class SessionNotFoundError(Exception):
    """Raised by ReportGenerationService.generate() when session_id matches
    no RetrievalSession row -- distinguishable from any other failure inside
    generate() (LLM transport/content errors, DB persistence errors) so a
    caller (Step 7's API route) can map it to its own specific HTTP status
    rather than a generic 500."""


class ReportNotFoundError(Exception):
    """Raised by ExplainabilityService.explain() when report_id matches no
    ReportRecord row (or isn't a valid UUID) -- distinguishable from
    SessionNotFoundError since a report lookup and a session lookup are
    different failure modes against different tables. Also raised by
    ComparisonService.compare() for current_report_id or
    compare_against_report_id -- same failure mode, same table, deliberately
    reused rather than duplicated (see this module's docstring)."""


class NoPriorReportError(Exception):
    """Raised by ComparisonService.compare() when no compare_against_report_id
    is supplied and the patient has no earlier report to compare the current
    one against (the patient's first visit). Distinguishable from
    ReportNotFoundError: no report_id lookup ever failed here, there was
    simply no candidate report to look up (see this module's docstring)."""


class InvalidCredentialsError(Exception):
    """Phase 13: raised by AuthService.login() for EITHER a nonexistent
    email OR a correct-email-wrong-password attempt -- deliberately ONE
    type covering both, not split the way ReportNotFoundError/
    NoPriorReportError are elsewhere in this project. Distinguishing "no
    such account" from "wrong password" in the response would let an
    attacker enumerate registered doctor emails one probe at a time; the
    two failure modes are handled identically on purpose, a security
    property, not an oversight of this project's usual "distinct failure
    modes deserve distinct types" principle."""


class EmailAlreadyRegisteredError(Exception):
    """Raised by AuthService.register() when the email is already taken --
    distinct from InvalidCredentialsError since this is a registration-time
    conflict (409), not a login-time authentication failure (401), and
    unlike login there is no enumeration concern in refusing a duplicate
    registration outright (the caller already knows the email, since they
    just typed it into a registration form)."""


class InvalidTokenError(Exception):
    """Raised by JWTHandler.verify() for an expired, tampered, or malformed
    token alike -- ONE type, not split by sub-reason, since
    get_current_doctor (Step 5) reacts identically to all three (401,
    "log in again"); a caller that genuinely needed to distinguish
    "expired" from "tampered" for a different UX (e.g. auto-refresh vs.
    hard logout) would be the reason to split this later, not a
    speculative concern now."""


class ForbiddenError(Exception):
    """Phase 13: raised by a service's ownership check (e.g.
    ReportGenerationService.finalize()) when the authenticated doctor is
    not the owner of the work being mutated. Deliberately a NEW type, not
    a reuse of any NotFoundError above: the resource genuinely exists and
    was found (read already succeeded, since read is universal per the
    frozen Phase 13 shared-registry decision) -- this is an authorization
    failure on a real, located resource, mapped to 403, never 404 (a 404
    here would incorrectly suggest the report doesn't exist rather than
    that this doctor may not write to it). First real caller: Phase 17's
    ReportEditService.update_content()/finalize()."""


class ReportAlreadyFinalizedError(Exception):
    """Phase 17: raised by ReportEditService when either update_content()
    or finalize() targets a report whose status is already FINAL. ONE
    type for both call sites (not split) -- editing a signed report and
    re-finalizing an already-finalized one are the same underlying
    violation ("this report is immutable"), not two distinct failure
    modes. Maps to 409 at the API layer: the report and the request are
    both well-formed, but the resource's current state conflicts with the
    requested mutation."""


class InputAdmissionError(Exception):
    """Base for every ImageAdmissionService rejection (input_admission_
    projection_gate_architecture_v1.1_FROZEN.md §10). Exists so the API
    layer and the DR-2 audit path can catch "the upload was rejected at
    admission" once, while still mapping each concrete subclass below to
    its own distinct HTTP status -- the §10 table gives three different
    statuses for three different admission failures, so the subclasses
    are not interchangeable and this base never gets raised directly.

    **No instance of this class or any subclass may ever carry the
    uploaded file's name in its message.** That is DR-2's Warning and
    §10's closing Rule, and it is enforced structurally rather than by
    review: ImageAdmissionService is never given the file name in the
    first place (it takes raw bytes and a declared EXTENSION), so there
    is no name in scope at any raise site.
    """

    def __init__(self, message: str, reason_code: str, stage: str) -> None:
        super().__init__(message)
        # Carried on the exception, not re-derived by the caller: DR-2
        # requires a rejection reason code and a stage of rejection in
        # every audit row, and the raise site is the only place that
        # actually knows which control fired.
        self.reason_code = reason_code
        self.stage = stage


class UnsupportedImageFormatError(InputAdmissionError):
    """§10: bad extension (A1) or a magic-byte signature that disagrees
    with the declared extension (A2/A4). HTTP 415."""


class ImageTooLargeError(InputAdmissionError):
    """§10: file size above UPLOAD_MAX_BYTES (A5). HTTP 413. Split from
    InvalidImageError because §10's table gives it its own status --
    "too big" is a payload-size problem the client can act on, not a
    "this file is broken" problem."""


class InvalidImageError(InputAdmissionError):
    """§10: file too small (A6), damaged/undecodable (A7/A8), over the
    pixel limit (A9), or outside the dimension bounds (A10/A11).
    HTTP 422. One type for all of these because §10's table groups them
    into one status deliberately -- they are all "this file is not a
    usable image", and the specific control that fired is carried in
    `reason_code`/`stage` for the audit row rather than in the type."""


class LateralProjectionError(Exception):
    """§10 / A16 of input_admission_projection_gate_architecture_v1.1: the
    doctor DECLARED the projection LATERAL. Reason code `DECLARED_LATERAL`,
    HTTP 422.

    Deliberately NOT an InputAdmissionError subclass and deliberately NOT
    merged with ProjectionMismatchError or NotAChestRadiographError. §10's
    Rule is explicit: "A lateral image **is** a chest radiograph. A joined
    type makes the rejection counts wrong." The three types answer three
    different questions:

      NotAChestRadiographError  this is not a radiograph at all      (M5)
      LateralProjectionError    it is a radiograph, declared lateral (A16)
      ProjectionMismatchError   it measures as not-frontal           (M10)

    Merging any two of them would make the audit table unable to
    distinguish an out-of-scope-but-valid film from a strawberry, which is
    the count DR-2's reason-code field exists to produce.

    Raised at admission, before masking, embedding or any ChromaDB query
    (A17), so it carries no modality score -- none was calculated.

    `message_key` rather than a message: §10.1's Rule says to translate
    both projection messages through the i18n key set and not to write
    English text in the response body.
    """

    reason_code = "DECLARED_LATERAL"
    stage = "admission_projection"
    message_key = "error.projection.declaredLateral"

    def __init__(self, declared_projection: str) -> None:
        # The declared projection is a closed enum value the client itself
        # sent, never free text and never a file name -- safe to carry.
        super().__init__(f"declared projection {declared_projection!r} is not accepted")
        self.declared_projection = declared_projection


class ProjectionMismatchError(Exception):
    """§10 / M10-M12: the top-1 similarity is below the projection reject
    threshold. Reason code `FRONTAL_MISMATCH`, HTTP 422.

    Distinct from LateralProjectionError above even though both concern
    projection: that one is a rejection of what the doctor SAID, this one
    is a rejection of what the pixels MEASURE. A lateral image reaches
    this check only when the declaration was wrong.

    M12 governs the message: it must not tell the doctor the image is
    wrong, it must ask them to check the projection. The reason is in
    §6.2's Note -- a correct frontal image from a different hospital
    produces the same measurement as a mis-declared lateral, and the two
    causes are indistinguishable at this point. The message states a
    doubt, not a fact.
    """

    reason_code = "FRONTAL_MISMATCH"
    stage = "projection_mismatch"
    message_key = "error.projection.frontalMismatch"

    def __init__(self, top1_similarity: float, reject_threshold: float) -> None:
        super().__init__(
            f"top-1 similarity {top1_similarity:.4f} is below the projection reject "
            f"threshold {reject_threshold:.4f}"
        )
        self.top1_similarity = top1_similarity
        self.reject_threshold = reject_threshold


class NotAChestRadiographError(Exception):
    """§10: the modality score is below MODALITY_THRESHOLD (M5). HTTP 422.

    Deliberately NOT an InputAdmissionError subclass, even though both
    reject an upload: §1 and §10 are emphatic that the file check and the
    content check are different controls in different services at
    different points of the pipeline (§9 puts admission before the mask
    and the gate after the embed). A shared base would invite one
    `except` clause to swallow both, which is exactly the conflation the
    architecture forbids.

    Carries the measured modality score because DR-2's audit table
    records it ("Modality score, if calculated") and the raise site is
    the only place it exists."""

    def __init__(self, message: str, modality_score: float) -> None:
        super().__init__(message)
        self.modality_score = modality_score
        self.reason_code = "MODALITY_BELOW_THRESHOLD"
        self.stage = "modality_gate"


class ReportValidationError(Exception):
    """Phase 17: raised by ReportEditService.finalize() when
    final_content's findings or impression is empty/whitespace-only.
    Distinct from ReportAlreadyFinalizedError (a state-conflict, 409) --
    this is a content-shape failure on an otherwise-valid, non-finalized
    report, mapped to 422."""
