"""
app/services/structural_validator.py
====================================================================
Implements IStructuralValidator. Validates that a raw LLM response uses
the delimiter-marker format matching ReportContent's shape -- structure
only, per the frozen Phase 7 architecture (development_log.md, "Phase 7
-- LLM Orchestrator: Architecture (FROZEN)"). Content quality/non-emptiness
(e.g. empty-string fields) is explicitly NOT this validator's concern --
that's Phase 8's Response Validator.

Delimiter-marker format, not JSON -- changed after Phase 20's real
generation-quality evaluation found every one of that run's 17 real
content-validation failures (17/477) was the same root cause: the LLM
inconsistently quoting label names inside the disclaimer field's JSON
string value, breaking json.loads() at that boundary (development_log.md,
"Finding: All 17 Generation Failures Share One Root Cause"). Rather than
relying on the LLM's own JSON string-escaping discipline (never fully
reliable), each field is now delimited by a plain ###FIELDNAME### marker
line -- there is no nested-string-inside-string boundary for a stray
quote character to ever break, for this field or any other.

Markdown fence stripping is lenient but bounded, same discipline as
before: a single well-known fenced block is stripped before marker
parsing, nothing more elaborate.
"""
from __future__ import annotations

import dataclasses
import re

from app.domain.entities import ReportContent

# Field names read directly from the frozen entity, not hardcoded, so this
# validator can't silently drift from ReportContent's real shape -- same
# discipline as Phase 6's schema test.
REPORT_CONTENT_FIELD_NAMES = tuple(f.name for f in dataclasses.fields(ReportContent))
FIELD_MARKERS = {name: f"###{name.upper()}###" for name in REPORT_CONTENT_FIELD_NAMES}

_FENCE_PATTERN = re.compile(r"^```(?:\w*)?\s*\n?(.*?)\n?```$", re.DOTALL)
_MARKER_LINE_PATTERN = re.compile(r"^[ \t]*(#{2,})[ \t]*([A-Za-z_]+)[ \t]*(#{2,})[ \t]*$", re.MULTILINE)


class StructuralValidator:
    """Satisfies domain.interfaces.IStructuralValidator."""

    def validate(self, raw_response: str) -> tuple[bool, ReportContent | None, list[str]]:
        candidate = self._strip_markdown_fence(raw_response)

        matches = list(_MARKER_LINE_PATTERN.finditer(candidate))
        if not matches:
            return False, None, [
                "response contains no recognized field markers "
                f"(expected e.g. {FIELD_MARKERS['findings']})"
            ]

        errors: list[str] = []
        seen: dict[str, int] = {}
        found_order: list[str] = []
        segments: dict[str, str] = {}

        for i, match in enumerate(matches):
            marker_text = match.group(0).strip()
            raw_name = match.group(2)
            field_name = raw_name.lower()

            if field_name not in FIELD_MARKERS:
                errors.append(f"unrecognized field marker: {marker_text!r}")
                continue
            if marker_text != FIELD_MARKERS[field_name]:
                errors.append(
                    f"malformed field marker: {marker_text!r} "
                    f"(expected exactly {FIELD_MARKERS[field_name]!r})"
                )
                continue
            if field_name in seen:
                errors.append(f"field marker for '{field_name}' appeared more than once")
                continue

            seen[field_name] = i
            found_order.append(field_name)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(candidate)
            segments[field_name] = candidate[start:end].strip()

        for name in REPORT_CONTENT_FIELD_NAMES:
            if name not in seen:
                errors.append(f"missing required field marker: {FIELD_MARKERS[name]}")

        expected_order = [name for name in REPORT_CONTENT_FIELD_NAMES if name in seen]
        if found_order != expected_order:
            errors.append(f"fields are out of order: got {found_order}, expected order {expected_order}")

        if errors:
            return False, None, errors

        content = ReportContent(**{name: segments[name] for name in REPORT_CONTENT_FIELD_NAMES})
        return True, content, []

    @staticmethod
    def _strip_markdown_fence(raw_response: str) -> str:
        text = raw_response.strip()
        match = _FENCE_PATTERN.match(text)
        return match.group(1).strip() if match else text
