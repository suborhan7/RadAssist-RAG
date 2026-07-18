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


class ReportValidationError(Exception):
    """Phase 17: raised by ReportEditService.finalize() when
    final_content's findings or impression is empty/whitespace-only.
    Distinct from ReportAlreadyFinalizedError (a state-conflict, 409) --
    this is a content-shape failure on an otherwise-valid, non-finalized
    report, mapped to 422."""
