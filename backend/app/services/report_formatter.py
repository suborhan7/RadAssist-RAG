"""
app/services/report_formatter.py
====================================================================
Implements IReportFormatter. Formats an already-validated ReportContent
into a structured FormattedReport object -- never rendered PDF/HTML
(frozen Phase 8 Decision 4). Pure function: report_date is passed through
exactly as given, never generated here -- generating it internally would
read the wall clock and break determinism. ReportGenerationService
(Phase 8 Step 6) is responsible for producing report_date and passing it
in; this class only formats with whatever date it's handed.

Unsupported/unknown `language` values raise ValueError rather than
silently falling back to "en": a caller passing an unexpected language
code is a real bug worth surfacing immediately, not masking -- silently
defaulting to English section headers while the LLM was actually asked
(Phase 6's PromptBuilder) to respond in a different language would
produce a mismatched, mislabeled report, which is a worse failure mode
in a medical-report system than a loud, immediate error.
"""
from __future__ import annotations

from app.domain.entities import FormattedReport, ReportContent

_EN_SECTION_HEADERS = {
    "examination": "Examination",
    "clinical_history": "Clinical History",
    "technique": "Technique",
    "findings": "Findings",
    "impression": "Impression",
    "recommendation": "Recommendation",
    "disclaimer": "Disclaimer",
}

# PROVISIONAL, UNREVIEWED placeholder terms -- a best-effort draft only.
# Per the frozen Phase 8 architecture (Decision 5), these must NOT be
# presented as clinically/linguistically validated terminology without a
# domain reviewer's sign-off. Do not ship to a real clinical user without
# that review.
_BN_SECTION_HEADERS = {
    "examination": "পরীক্ষা",
    "clinical_history": "ক্লিনিক্যাল ইতিহাস",
    "technique": "কৌশল",
    "findings": "পর্যবেক্ষণ",
    "impression": "মন্তব্য",
    "recommendation": "সুপারিশ",
    "disclaimer": "দাবিত্যাগ",
}

_SECTION_HEADERS_BY_LANGUAGE = {
    "en": _EN_SECTION_HEADERS,
    "bn": _BN_SECTION_HEADERS,
}


class ReportFormatter:
    """Satisfies domain.interfaces.IReportFormatter."""

    def format(self, content: ReportContent, language: str, report_date: str) -> FormattedReport:
        try:
            section_headers = _SECTION_HEADERS_BY_LANGUAGE[language]
        except KeyError:
            raise ValueError(
                f"unsupported language '{language}' -- expected one of "
                f"{sorted(_SECTION_HEADERS_BY_LANGUAGE)}"
            ) from None

        return FormattedReport(
            content=content,
            language=language,
            report_date=report_date,
            section_headers=dict(section_headers),
        )
