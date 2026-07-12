"""
app/services/structural_validator.py
====================================================================
Implements IStructuralValidator. Validates that a raw LLM response is
well-formed JSON matching ReportContent's shape -- structure only, per
the frozen Phase 7 architecture (development_log.md, "Phase 7 -- LLM
Orchestrator: Architecture (FROZEN)"). Content quality/non-emptiness
(e.g. empty-string fields) is explicitly NOT this validator's concern --
that's Phase 8's Response Validator.

Markdown fence stripping is lenient but bounded: a single well-known
``` ```json ... ``` ``` or ``` ``` ... ``` ``` wrapper is stripped before
parsing, nothing more elaborate. Anything still unparseable after that one
stripping step is a genuine content-validation failure, not a crash.
"""
from __future__ import annotations

import dataclasses
import json
import re

from app.domain.entities import ReportContent

# Field names read directly from the frozen entity, not hardcoded, so this
# validator can't silently drift from ReportContent's real shape -- same
# discipline as Phase 6's schema test.
REPORT_CONTENT_FIELD_NAMES = tuple(f.name for f in dataclasses.fields(ReportContent))

_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


class StructuralValidator:
    """Satisfies domain.interfaces.IStructuralValidator."""

    def validate(self, raw_response: str) -> tuple[bool, ReportContent | None, list[str]]:
        candidate = self._strip_markdown_fence(raw_response)

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            return False, None, [f"response is not valid JSON: {exc}"]

        if not isinstance(parsed, dict):
            return False, None, [f"parsed JSON is not an object (got {type(parsed).__name__})"]

        errors: list[str] = []
        for field_name in REPORT_CONTENT_FIELD_NAMES:
            if field_name not in parsed:
                errors.append(f"missing required field: {field_name}")
            elif not isinstance(parsed[field_name], str):
                errors.append(
                    f"field '{field_name}' must be a string, got "
                    f"{type(parsed[field_name]).__name__}"
                )

        if errors:
            return False, None, errors

        content = ReportContent(**{name: parsed[name] for name in REPORT_CONTENT_FIELD_NAMES})
        return True, content, []

    @staticmethod
    def _strip_markdown_fence(raw_response: str) -> str:
        text = raw_response.strip()
        match = _FENCE_PATTERN.match(text)
        return match.group(1).strip() if match else text
