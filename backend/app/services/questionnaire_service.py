"""
app/services/questionnaire_service.py
====================================================================
Implements the Phase 9 questionnaire-fetch use case: re-runs
retrieval+voting against a real, already-persisted session (via the same
reconstruct_session_evidence() shared with ReportGenerationService -- no
new persistence needed) and returns a Questionnaire of static, label-keyed
questions for that session's real top voted label.

Pure sequencing -- no business logic of its own. The only "decision" made
here is voted_labels[0].label as the top label, which is the existing,
already-frozen LabelVotingService convention (Phase 4), not a new rule.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.entities import Questionnaire
from app.domain.interfaces import ILabelVoter, IQuestionnaireProvider, IVectorStore
from app.services.session_reconstruction import reconstruct_session_evidence


class QuestionnaireService:
    def __init__(
        self,
        db: Session,
        vector_store: IVectorStore,
        label_voting_service: ILabelVoter,
        questionnaire_provider: IQuestionnaireProvider,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._label_voting_service = label_voting_service
        self._questionnaire_provider = questionnaire_provider

    def get_questionnaire(self, session_id: str) -> Questionnaire:
        _retrieval_session, _retrieved_cases, voted_labels = reconstruct_session_evidence(
            self._db, self._vector_store, self._label_voting_service, session_id
        )

        top_label = voted_labels[0].label if voted_labels else ""
        questions = self._questionnaire_provider.get_questions_for_label(top_label)

        return Questionnaire(session_id=session_id, based_on_label=top_label, questions=questions)
