"""
app/services/report_generation_service.py
====================================================================
Orchestrates the full Phase 8 chain, per the frozen sequence diagram:
fetch session evidence -> reconstruct cases -> vote -> build context ->
generate -> semantically validate -> format -> persist. Pure sequencing
over its injected collaborators -- no business logic, no clinical
judgment, no prompt/report content decisions of its own -- same discipline
as RetrievalService (Phase 4).

Exception propagation policy (deliberate, stated explicitly): LLMTransportError
and LLMGenerationValidationError from llm_orchestrator.generate_draft() are
NOT caught here -- they propagate unchanged to the caller (Step 7's API
route). This mirrors Phase 4's precedent exactly: RetrievalService lets
ValueError propagate up to app/api/retrieval.py, the one place that knows
how to translate a domain exception into an HTTP status code. Catching and
re-wrapping here would duplicate that translation responsibility in two
places instead of one.

Reproducibility-metadata gap, flagged rather than silently worked around:
RetrievalSession (Phase 4's frozen schema) does NOT persist collection_name/
embedding_model/embedding_version per-session -- only Settings holds these
(as the current config, not necessarily what was true at the original
retrieval time if config has changed since). Sourced from Settings here,
consistent with how /retrieve's own response and Phase 7's integration test
both already source the identical values -- not a new precedent, but worth
naming as a real limitation: if the collection/model config changes between
a session's original retrieval and a later report-generation call, the
persisted reproducibility metadata reflects the LATER config, not
necessarily what actually produced that session's retrieved cases.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.entities import (
    FormattedReport,
    GenerationMetadata,
    ReportStatus,
    RetrievalMetadata,
    SemanticValidationResult,
)
from app.domain.interfaces import (
    IContextBuilder,
    ILabelVoter,
    ILLMOrchestrator,
    IReportFormatter,
    IResponseValidator,
    IVectorStore,
)
from app.models.report import ReportRecord
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.evidence_disclaimer import render_disclaimer
from app.services.session_reconstruction import reconstruct_session_evidence


class ReportGenerationService:
    def __init__(
        self,
        db: Session,
        vector_store: IVectorStore,
        label_voting_service: ILabelVoter,
        context_builder: IContextBuilder,
        llm_orchestrator: ILLMOrchestrator,
        response_validator: IResponseValidator,
        report_formatter: IReportFormatter,
        modality_gate_service=None,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._label_voting_service = label_voting_service
        self._context_builder = context_builder
        self._llm_orchestrator = llm_orchestrator
        self._response_validator = response_validator
        self._report_formatter = report_formatter
        # Input Admission and Modality Gate §7: the ONE implementation of
        # S1 ("calculate the retrieval support category from the top-1
        # similarity and the retrieval floor") lives on ModalityGateService
        # and is reused here rather than reimplemented, so /retrieve's
        # M7-M9 category and the report's stored S5 category can never be
        # computed by two rules that drift apart.
        #
        # Defaulted to None so the eight existing unit tests that construct
        # this service with seven positional collaborators keep working
        # unchanged. A None gate means the support signal is simply not
        # computed and both columns stay NULL -- which is the same honest
        # "no recorded support state" that pre-migration rows carry, not a
        # silent fallback to some assumed category.
        self._modality_gate_service = modality_gate_service

    def generate(
        self,
        session_id: str,
        language: str,
        questionnaire_answers: dict[str, str] | None = None,
        clinical_notes: str = "",
    ) -> tuple[uuid.UUID, FormattedReport, SemanticValidationResult, GenerationMetadata]:
        # Phase 9 additive extension: questionnaire_answers/clinical_notes
        # default to None/"" (same null-handling convention as
        # PromptBuilder's own build() defaults from Phase 6 --
        # None-then-convert for the mutable dict, never a mutable literal
        # as the actual default argument value). Omitting both entirely
        # must be byte-identical to Phase 8's existing behavior -- see
        # test_no_questionnaire_data_produces_byte_identical_behavior_to_phase_8.
        questionnaire_answers = questionnaire_answers or {}
        # Phase 19: clinical_notes gets the SAME normalization, added here
        # (not just relied on via the API layer's non-Optional `str` type)
        # so the two persisted columns are structurally guaranteed non-None
        # together, regardless of caller -- not merely true for the one
        # real caller today. Closes a real gap found during Phase 19: this
        # line was missing, so the guarantee previously depended entirely
        # on GenerateReportRequest's Pydantic type, not on this service's
        # own code.
        clinical_notes = clinical_notes or ""

        # Shared with QuestionnaireService (Phase 9) -- see
        # session_reconstruction.py's own docstring for why this is
        # extracted rather than duplicated.
        retrieval_session, retrieved_cases, voted_labels = reconstruct_session_evidence(
            self._db, self._vector_store, self._label_voting_service, session_id
        )

        retrieval_metadata = RetrievalMetadata(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.CHROMA_EMBEDDING_MODEL,
            embedding_version=settings.CHROMA_EMBEDDING_VERSION,
            retrieved_at=retrieval_session.created_at.isoformat() if retrieval_session.created_at else "",
        )
        context = self._context_builder.build(
            retrieved_cases,
            voted_labels,
            questionnaire_answers=questionnaire_answers,
            clinical_notes=clinical_notes,
            retrieval_metadata=retrieval_metadata,
        )

        # LLMTransportError / LLMGenerationValidationError intentionally
        # NOT caught here -- see module docstring's propagation policy.
        content = self._llm_orchestrator.generate_draft(context, language)

        validation_result = self._response_validator.validate_semantic(
            content, context.evidence_summary, voted_labels
        )

        # --- Input Admission and Modality Gate §7: the evidence support
        # signal (S1, S2, S5). ---
        #
        # The top-1 similarity is read back out of `retrieved_evidence`,
        # NOT off the reconstructed `retrieved_cases`. That is not a
        # roundabout way of getting the same number: reconstruct_session_
        # evidence() fetches cases through IVectorStore.get_by_ids(), an
        # ID-based fetch with no ranking, which documents that it forces
        # distance 0.0 and therefore reports similarity 1.0 for every case.
        # Using that value would record every single report as being at or
        # above the floor. The real, ranked similarity from the original
        # query survives only in the retrieved_evidence rows Phase 4
        # persisted at /retrieve time -- which is also what S5 means by
        # storing the evidence state as it was, rather than as it can be
        # re-derived later.
        top1_similarity = self._top1_similarity(retrieval_session.id)
        top_agreement = voted_labels[0].agreement if voted_labels else None

        retrieval_support = None
        if self._modality_gate_service is not None:
            retrieval_support = self._modality_gate_service.classify_retrieval_support(
                top1_similarity
            )

            # S2 + S3: the disclaimer is rendered here, on the server, from
            # a parameterised template fed BOTH signals -- replacing the
            # text the LLM wrote into this field. §7.1's Rule is that the
            # disclaimer must read both signals; a model-authored
            # disclaimer reads whichever it feels like, and the Phase 7 dev
            # log's real sample ("Clinical uncertainty due to low agreement
            # score (0.60)") shows it reading only agreement -- the exact
            # single-signal failure §7.1's Warning describes.
            #
            # This runs AFTER validate_semantic() on purpose. That
            # validator's subject is the model's clinical claims in
            # findings/impression; handing it a server-authored string that
            # no model produced would be validating this system's own
            # template output as though it were generated content.
            content.disclaimer = render_disclaimer(
                agreement=top_agreement,
                support=retrieval_support,
                top1_similarity=top1_similarity,
                retrieval_floor=self._modality_gate_service.retrieval_floor,
                agreement_threshold=settings.DISCLAIMER_AGREEMENT_THRESHOLD,
                language=language,
            )

        # report_date generated HERE, not inside ReportFormatter (which must
        # stay a pure, deterministic function -- Phase 8 Decision 4).
        report_date = datetime.now(timezone.utc).date().isoformat()

        formatted_report = self._report_formatter.format(content, language, report_date)

        # Phase 17: ai_draft_content is the immutable AI draft; final_content
        # starts as a deep copy (Decision 3) that PATCH /reports/{id} is the
        # only thing that ever touches. asdict(content) is called twice
        # deliberately, not once with the result assigned to both fields --
        # each call builds a genuinely independent dict, so there is no
        # shared-reference risk if either field is later mutated in place
        # rather than reassigned wholesale.
        # Phase 19 Decision 4's resolution: persisted from here on, so an
        # existing report's original generation context can be fully
        # reconstructed for section regeneration. questionnaire_answers is
        # already normalized to a real dict (never None) by line 93 above;
        # clinical_notes is already guaranteed a real str (never None) by
        # GenerateReportRequest's own non-Optional `str` typing at the API
        # boundary (app/api/generation.py) -- so this write always
        # persists two real, non-null values, never exactly one of them.
        # Pre-migration rows stay NULL on both (no backfill, per that
        # migration's own docstring); this is the only code path that ever
        # writes either column, so the two can never independently drift
        # to one-null-one-not.
        report_record = ReportRecord(
            session_id=retrieval_session.id,
            language=language,
            status=ReportStatus.AI_DRAFT,
            ai_draft_content=asdict(content),
            final_content=asdict(content),
            validation_warnings=list(validation_result.warnings),
            report_date=report_date,
            llm_model=settings.OLLAMA_MODEL,
            llm_temperature=settings.LLM_TEMPERATURE,
            embedding_model=retrieval_metadata.embedding_model,
            embedding_version=retrieval_metadata.embedding_version,
            collection_name=retrieval_metadata.collection_name,
            questionnaire_answers=questionnaire_answers,
            clinical_notes=clinical_notes,
            # S5: stored WITH the report, at generation time. Written from
            # the same two values the disclaimer above was rendered from,
            # not re-derived, so the stored category and the sentence the
            # radiologist reads can never describe different measurements.
            retrieval_support=retrieval_support.value if retrieval_support is not None else None,
            top1_similarity=top1_similarity,
            # S7 / D4: the other two fields of the evidence snapshot,
            # written from the SAME `voted_labels` this method already
            # voted, built the context from, validated against and
            # rendered the disclaimer from -- not re-voted here, so the
            # stored snapshot and the report's own reasoning cannot
            # describe different votes.
            #
            # The whole descending-sorted list is stored, not just the
            # top entry: the disclaimer, the semantic validator and the
            # frontend each read different parts of it (see the
            # migration's docstring).
            voted_labels=[asdict(v) for v in voted_labels],
            agreement=top_agreement,
        )
        self._db.add(report_record)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        # Populated from the exact same values just persisted onto
        # report_record (not re-queried from the DB) -- one computation,
        # reused, rather than a second, potentially-inconsistent read.
        generation_metadata = GenerationMetadata(
            llm_model=report_record.llm_model,
            llm_temperature=report_record.llm_temperature,
            embedding_model=report_record.embedding_model,
            embedding_version=report_record.embedding_version,
            collection_name=report_record.collection_name,
        )

        # report_id returned as uuid.UUID (its native type here, same as
        # RetrievalSession.id/ReportRecord.id throughout the service layer)
        # -- consistent with Phase 4's own boundary convention: the domain/
        # service layer works in real uuid.UUID objects, and only the API
        # layer (Step 7) converts to str for JSON serialization, same as
        # app/api/retrieval.py's _build_response() does for session_id.
        return report_record.id, formatted_report, validation_result, generation_metadata

    def _top1_similarity(self, session_id: uuid.UUID) -> float | None:
        """The rank-1 similarity actually measured by the original
        /retrieve call (§7 M7's "top-1 similarity score from the
        RetrievalService").

        Ordered by rank rather than by max(similarity): rank 1 IS the top-1
        result by definition, SimilaritySearchPolicy having already sorted
        descending before these rows were written. Reading the rank is
        reading what was recorded; recomputing a max would be a second,
        independently-derivable opinion about the same fact.

        None when the session has no evidence rows at all -- a retrieval
        that returned nothing. ModalityGateService.classify_retrieval_
        support() maps that to BELOW_FLOOR, since no retrieved case meets
        the threshold when there is no retrieved case.
        """
        row = (
            self._db.query(RetrievedEvidence)
            .filter(RetrievedEvidence.session_id == session_id)
            .order_by(RetrievedEvidence.rank)
            .first()
        )
        return row.similarity if row is not None else None
