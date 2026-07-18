"""
app/services/llm_orchestrator.py
====================================================================
Implements ILLMOrchestrator. Pure sequencing: build prompt (Phase 6's
frozen PromptBuilder) -> call Ollama -> structurally validate -> retry
with a correction prompt on content failure -> return a structurally-
valid ReportContent, or raise on retry-budget exhaustion. Zero prompt
composition, zero semantic judgment, zero persistence, zero business
logic of its own -- same discipline as RetrievalService (Phase 4).

Two independent retry budgets, per the frozen sequence diagram
(development_log.md, "Phase 7 -- LLM Orchestrator: Architecture (FROZEN)"),
corrected after an initial gap found during implementation (see the dev
log's Phase 7 Implementation & Validation entry): the transport-retry
budget applies to EVERY real LLM call, not only the first one. A single
`generate_freeform(prompt)` method (originally a private helper,
`_call_llm_with_transport_retry`, promoted to a public, neutrally-named
method in Phase 19 -- see that method's own docstring for why) owns "call
the LLM, retry up to LLM_TRANSPORT_RETRY_COUNT times on transport failure,
raise LLMTransportError if exhausted," and the initial call, every
content-retry's call, answer_question(), and Phase 19's section
regeneration all go through this same method -- each invocation gets its
own fresh transport-retry budget, independent of how many content-retries
have already happened. The content-retry budget and transport-retry
budget remain fully independent of each other.

build_generation_prompt is called exactly once, for the first attempt --
structurally guaranteed by having exactly one call site for it, at the top
of generate_draft(); every retry (transport or content) reuses that same
initial prompt string or goes through build_retry_prompt instead.
"""
from __future__ import annotations

from app.domain.entities import ClinicalContext, ReportContent
from app.domain.interfaces import ILLMClient, IPromptBuilder, IStructuralValidator
from app.services.exceptions import LLMGenerationValidationError, LLMTransportError


class LLMOrchestrator:
    """Satisfies domain.interfaces.ILLMOrchestrator."""

    def __init__(
        self,
        prompt_builder: IPromptBuilder,
        llm_client: ILLMClient,
        structural_validator: IStructuralValidator,
        transport_retry_count: int,
        content_retry_count: int,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client
        self._structural_validator = structural_validator
        self._transport_retry_count = transport_retry_count
        self._content_retry_count = content_retry_count

    def generate_draft(self, context: ClinicalContext, language: str) -> ReportContent:
        prompt = self._prompt_builder.build_generation_prompt(context, language)
        last_raw_response = self.generate_freeform(prompt)
        last_validation_errors: list[str] = []

        for attempt in range(self._content_retry_count + 1):
            is_valid, content, validation_errors = self._structural_validator.validate(last_raw_response)
            if is_valid:
                return content

            last_validation_errors = validation_errors
            if attempt == self._content_retry_count:
                break

            retry_prompt = self._prompt_builder.build_retry_prompt(
                context, language, last_raw_response, last_validation_errors
            )
            last_raw_response = self.generate_freeform(retry_prompt)

        raise LLMGenerationValidationError(last_raw_response, last_validation_errors)

    def answer_question(self, prompt: str) -> str:
        """Phase 10 (Explainability Chat): free-text answer, no schema to
        validate against, so NO content-retry/StructuralValidator loop --
        deliberately the mirror image of generate_draft()'s two-loop
        structure, reduced to just the transport-retry loop. Thin wrapper
        over generate_freeform() (Phase 19 extraction) -- a transport
        failure is exactly as real here as it is for generate_draft()."""
        return self.generate_freeform(prompt)

    def generate_freeform(self, prompt: str) -> str:
        """Phase 19 extraction: this was originally a private helper
        (_call_llm_with_transport_retry) that only answer_question() and
        generate_draft()'s retry loop called internally. Promoted to a
        public, neutrally-named method -- "generate_freeform," not
        "answer_question" -- because Phase 19's section-regeneration path
        needs the exact same transport-retry-only behavior (a real LLM
        call, no content-retry/structural-validation loop) for a candidate
        that is not an answer to a question at all. Renaming rather than
        letting the new caller reuse answer_question() directly keeps each
        method's name honest about what it's actually for.

        Owns the transport-retry budget for a single logical call: retries
        up to transport_retry_count additional times on LLMTransportError,
        with the SAME prompt, before raising. Used for every real LLM call
        this class makes -- generate_draft()'s initial and retry calls,
        answer_question(), and now section regeneration -- so transport
        protection is consistent regardless of caller."""
        last_error: LLMTransportError | None = None
        for _ in range(self._transport_retry_count + 1):
            try:
                return self._llm_client.complete(prompt)
            except LLMTransportError as exc:
                last_error = exc
        raise last_error
