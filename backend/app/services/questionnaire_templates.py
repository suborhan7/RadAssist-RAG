"""
app/services/questionnaire_templates.py
====================================================================
Implements IQuestionnaireProvider. Static question bank keyed by the
frozen Phase 0 18-class taxonomy -- no LLM call (frozen Phase 9 Decision
1: questions come from predefined templates, not LLM-generated).

Taxonomy loading reuses response_validator.py's existing
_load_taxonomy_classes()/DEFAULT_LABEL_MAPPING_PATH directly (imported,
not reimplemented) -- per Phase 8 Step 4's precedent of loading
label_mapping.yaml straight from ml/config/ rather than importing across
the frozen ml/<->backend/ boundary, there must be exactly ONE function in
this codebase that parses that YAML into class names, not a second,
divergent copy.

Clinical content disclosure, same honesty convention as Phase 8 Step 5's
Bengali section headers: the question text below is a best-reasonable-
effort draft by a non-clinician (an LLM-assisted engineering pass, not a
certified medical reviewer), included to make the questionnaire feature
functionally complete for this thesis pipeline. It must not be presented
as clinically validated or deployed to real patients without review and
sign-off by an actual radiologist/clinician.
"""
from __future__ import annotations

from app.domain.entities import QuestionnaireQuestion
from app.services.response_validator import DEFAULT_LABEL_MAPPING_PATH, _load_taxonomy_classes


def _q(key: str, text: str, input_type: str) -> QuestionnaireQuestion:
    return QuestionnaireQuestion(key=key, text=text, input_type=input_type)


# Explicit default/fallback set: used for ANY label not present as a key in
# QUESTION_TEMPLATES below (an unmapped/future label, not one of the 18
# taxonomy classes) -- never raises, never returns empty for an
# unrecognized label.
DEFAULT_QUESTIONS: tuple[QuestionnaireQuestion, ...] = (
    _q("symptom_reason", "What symptom or clinical concern prompted this chest X-ray?", "text"),
    _q("duration", "How long has this concern been present?", "text"),
    _q(
        "relevant_history",
        "Is there any other relevant medical history or recent exposure the clinician should know about?",
        "text",
    ),
)

QUESTION_TEMPLATES: dict[str, tuple[QuestionnaireQuestion, ...]] = {
    "Normal": (
        _q("symptom_reason", "What symptom or concern prompted this chest X-ray?", "text"),
        _q("prior_abnormal", "Has the patient had any prior abnormal chest X-ray or CT?", "yes_no"),
        _q("smoking_history", "What is the patient's smoking history?", "select"),
    ),
    "Lung Opacity": (
        _q("duration", "How long has the respiratory symptom (cough, breathlessness) been present?", "text"),
        _q("fever", "Is fever present?", "yes_no"),
        _q(
            "travel_exposure",
            "Any recent travel, known TB exposure, or occupational dust/chemical exposure?",
            "yes_no",
        ),
    ),
    "Cardiomegaly": (
        _q(
            "known_heart_disease",
            "Does the patient have a known history of heart disease (e.g. hypertension, heart failure, valve disease)?",
            "yes_no",
        ),
        _q("swelling", "Does the patient have swelling in the legs, ankles, or abdomen?", "yes_no"),
        _q(
            "exertional_dyspnea",
            "Does the patient experience shortness of breath with exertion or when lying flat?",
            "yes_no",
        ),
        _q("medication", "Is the patient currently taking any heart or blood-pressure medications?", "text"),
    ),
    "Calcinosis/Atherosclerosis": (
        _q(
            "known_vascular_disease",
            "Does the patient have known atherosclerosis, coronary artery disease, or peripheral vascular disease?",
            "yes_no",
        ),
        _q(
            "risk_factors",
            "How many cardiovascular risk factors does the patient have (diabetes, hypertension, hyperlipidemia, smoking)?",
            "select",
        ),
        _q("age", "What is the patient's age?", "text"),
    ),
    "Atelectasis": (
        _q("recent_surgery", "Has the patient had recent surgery or been immobile/bedridden?", "yes_no"),
        _q("productive_cough", "Is there a productive cough or difficulty clearing secretions?", "yes_no"),
        _q("known_lung_disease", "Does the patient have a known underlying lung condition?", "yes_no"),
    ),
    "Granuloma": (
        _q("tb_exposure", "Any history of tuberculosis or known TB exposure?", "yes_no"),
        _q(
            "endemic_travel",
            "Any travel to or residence in a fungal-endemic region (histoplasmosis/coccidioidomycosis areas)?",
            "yes_no",
        ),
        _q("prior_imaging", "Is this finding stable compared to prior imaging, if available?", "yes_no"),
    ),
    "Scarring": (
        _q(
            "prior_lung_disease",
            "Does the patient have a history of prior lung infection, TB, or surgery in this area?",
            "yes_no",
        ),
        _q("symptom_change", "Has the patient had any new or worsening respiratory symptoms?", "yes_no"),
    ),
    "Pleural Effusion": (
        _q("breathing_difficulty", "How would you rate the patient's shortness of breath?", "select"),
        _q(
            "known_organ_disease",
            "Does the patient have known heart failure, liver disease, or kidney disease?",
            "yes_no",
        ),
        _q("chest_pain", "Is there associated chest pain, especially with breathing?", "yes_no"),
        _q("fever", "Is fever present?", "yes_no"),
    ),
    "Degenerative/Bone": (
        _q("back_pain", "Does the patient have chronic back or chest wall pain?", "yes_no"),
        _q(
            "known_arthritis",
            "Does the patient have a known history of arthritis or degenerative spine disease?",
            "yes_no",
        ),
        _q("trauma_history", "Any history of trauma to the chest or spine?", "yes_no"),
    ),
    "Emphysema/COPD": (
        _q("smoking_history", "What is the patient's smoking history?", "select"),
        _q("known_copd", "Does the patient have a known diagnosis of COPD or emphysema?", "yes_no"),
        _q("breathing_difficulty", "How would you rate the patient's baseline shortness of breath?", "select"),
        _q("productive_cough", "Is there a chronic productive cough?", "yes_no"),
    ),
    "Edema/Congestion": (
        _q("known_heart_failure", "Does the patient have known heart failure or cardiac disease?", "yes_no"),
        _q("swelling", "Is there swelling in the legs, ankles, or abdomen?", "yes_no"),
        _q("orthopnea", "Does the patient have difficulty breathing when lying flat (orthopnea)?", "yes_no"),
        _q("weight_gain", "Has the patient had recent rapid weight gain or fluid retention?", "yes_no"),
    ),
    "Nodule/Mass": (
        _q("duration", "How long has this finding been known, if previously identified?", "text"),
        _q("smoking_history", "What is the patient's smoking history?", "select"),
        _q("weight_loss", "Has the patient had unexplained weight loss?", "yes_no"),
        _q("prior_imaging", "Is prior imaging available for comparison?", "yes_no"),
        _q("family_history_cancer", "Is there a family history of lung cancer?", "yes_no"),
    ),
    "Pneumonia": (
        _q("duration", "How long have symptoms (cough, fever, chest pain) been present?", "text"),
        _q("fever", "Does the patient currently have a fever?", "yes_no"),
        _q("productive_cough", "Is the cough productive (bringing up phlegm/sputum)?", "yes_no"),
        _q("breathing_difficulty", "How would you rate the patient's shortness of breath?", "select"),
        _q("recent_illness", "Has the patient had a recent upper respiratory infection or illness?", "yes_no"),
    ),
    "Pneumothorax": (
        _q("onset", "Was the onset of chest pain/breathlessness sudden or gradual?", "select"),
        _q(
            "trauma_history",
            "Any recent chest trauma or invasive procedure (e.g. central line, biopsy)?",
            "yes_no",
        ),
        _q(
            "known_lung_disease",
            "Does the patient have known lung disease (e.g. COPD, cystic fibrosis)?",
            "yes_no",
        ),
        _q("chest_pain", "Is there sudden, sharp chest pain?", "yes_no"),
    ),
    "Fibrosis/Interstitial": (
        _q("duration", "How long has the shortness of breath or dry cough been present?", "text"),
        _q(
            "occupational_exposure",
            "Any occupational or environmental exposure (asbestos, silica, birds, mold)?",
            "yes_no",
        ),
        _q(
            "known_autoimmune_disease",
            "Does the patient have a known autoimmune or connective tissue disease?",
            "yes_no",
        ),
        _q("dry_cough", "Is the cough dry (non-productive)?", "yes_no"),
    ),
    "Hernia/Diaphragm": (
        _q("reflux_symptoms", "Does the patient have symptoms of acid reflux or heartburn?", "yes_no"),
        _q("known_hiatal_hernia", "Is there a known history of hiatal hernia?", "yes_no"),
        _q("postprandial_symptoms", "Are symptoms worse after eating or when lying down?", "yes_no"),
    ),
    "Support Devices": (
        _q(
            "device_type",
            "What device(s) does the patient have in place (e.g. central line, pacemaker, chest tube, endotracheal tube)?",
            "text",
        ),
        _q("placement_date", "When was the device placed, if known?", "text"),
        _q("symptoms_since_placement", "Has the patient had any new symptoms since device placement?", "yes_no"),
    ),
    "Other Abnormality": DEFAULT_QUESTIONS,
}

# Validated against the real taxonomy (not just hand-typed strings assumed
# to match): every QUESTION_TEMPLATES key must be a real class name from
# label_mapping.yaml, loaded via the same function response_validator.py
# uses -- catches a typo'd/drifted key at import time rather than silently
# falling through to DEFAULT_QUESTIONS for a class that was actually meant
# to have its own template.
_TAXONOMY_CLASSES = _load_taxonomy_classes()
_unknown_keys = set(QUESTION_TEMPLATES) - set(_TAXONOMY_CLASSES)
if _unknown_keys:
    raise ValueError(
        f"QUESTION_TEMPLATES has keys not present in {DEFAULT_LABEL_MAPPING_PATH}: "
        f"{sorted(_unknown_keys)}"
    )


class QuestionnaireTemplateProvider:
    """Satisfies domain.interfaces.IQuestionnaireProvider."""

    def get_questions_for_label(self, label: str) -> tuple[QuestionnaireQuestion, ...]:
        return QUESTION_TEMPLATES.get(label, DEFAULT_QUESTIONS)
