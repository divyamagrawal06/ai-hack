"""Deterministic, illustrative administrative rules. Not a clinical triage tool.

The text guard is a bounded demonstration, not universal medical understanding.
The independent client guard is mirrored and tested against these same examples.
"""
import re
from .config import POLICY_VERSION, QUESTIONS

ROUTES = {"routine_appointment", "same_day_human_review", "emergency_guidance"}
DIRECT_VARIANTS = {"direct", "direct_replay", "jev_direct"}

# Specific present-tense examples, deliberately narrow. No generic disease terms.
PATTERNS = [
    r"(?:hard|difficult|trouble|struggling|unable)\s+(?:time\s+)?(?:to\s+)?breath(?:e|ing)",
    r"(?:cannot|can't|can’t)\s+(?:catch\s+my\s+breath|breathe)",
    r"taking\s+a\s+breath\s+is\s+getting\s+harder",
    r"(?:badly\s+wrong|wrong)\s+with\s+my\s+breathing",
    r"(?:severe|crushing|heavy)\s+(?:chest\s+(?:pain|discomfort|pressure)|pressure\s+(?:on|in)\s+my\s+chest)",
    r"(?:bleeding\s+(?:heavily|won't\s+stop|will\s+not\s+stop)|(?:cannot|can't)\s+stop\s+(?:the\s+)?bleeding)",
    r"(?:took|taken|swallowed)\s+(?:far\s+)?too\s+many\s+(?:pills|tablets)",
    r"(?:overdos(?:e|ed|ing)|poisoned)",
    r"(?:sudden(?:ly)?\s+(?:trouble\s+speaking|weakness)|one[- ]sided\s+weakness)",
    r"(?:going\s+to|about\s+to|might)\s+(?:kill|hurt)\s+myself",
]


def detect_local_warning(text):
    """Return a bounded contextual warning flag. Unknown phrases stay unassessed."""
    if not isinstance(text, str):
        return "none"
    text = text.lower().replace("\u2019", "'")
    for sentence in re.split(r"[.!?\n]+|\bbut\b|\b(?:and\s+)?(?:now|today)\b", text):
        if not sentence.strip():
            continue
        # Known historical/quoted examples are not current assertions. This is
        # intentionally a limited demo context filter, with documented residual risk.
        if re.search(r"\b(years? ago|last year|in the past|used to|quoted|quotation|(?:a|my|the) story|character says|example sentence)\b", sentence):
            continue
        for pattern in PATTERNS:
            match = re.search(pattern, sentence)
            if not match:
                continue
            prefix = sentence[max(0, match.start() - 42):match.start()]
            # Do not negate a later independent affirmative clause.
            prefix = re.split(r"\bbut\b|\band now\b|[,;]", prefix)[-1]
            if re.search(r"\b(?:no|not|never|deny|denies|without|don't|doesn't|isn't|aren't|hasn't)\s+(?:(?:any|having|have|has|had|currently|experiencing|experience|severe|a|very|now)\s+){0,3}$", prefix):
                continue
            uncertain = bool(re.search(r"\b(?:might|may have|maybe|possibly|possible|not sure|cannot tell|can't tell)\b", sentence))
            return "current_possible_demo_warning" if uncertain else "current_explicit_demo_warning"
    return "none"


def _missing(inputs):
    missing = []
    if not str(inputs.get("symptom_text") or "").strip():
        missing.append("symptom_text")
    if inputs.get("self_reported_urgency") not in {"routine", "urgent", "unsure"}:
        missing.append("self_reported_urgency")
    if not inputs.get("preferred_times") and inputs.get("no_time_preference") is not True:
        missing.append("preferred_times_or_no_preference")
    if not inputs.get("onset_currentness") or inputs.get("onset_currentness") in {"unsure", "unknown"}:
        missing.append("onset_currentness")
    if inputs.get("age_years") is None:
        missing.append("age_years")
    if not inputs.get("language"):
        missing.append("language")
    answers = inputs.get("emergency_answers") or {}
    for question in QUESTIONS:
        if answers.get(question["id"]) not in {"yes", "no", "unsure"}:
            missing.append(question["id"])
    return missing


def segment_text(text):
    """Application-generated IDs/Unicode offsets; not model-selected evidence."""
    if not isinstance(text, str):
        return []
    return [{"id": f"S{i:03d}", "start": match.start(), "end": match.end(), "text": match.group()}
            for i, match in enumerate(re.finditer(r"[^.!?\n]+(?:[.!?]+|\n|$)", text), 1)]


def _supported(inputs):
    return structured_scope(inputs) == "supported"


def structured_scope(inputs):
    """Authoritative form facts, independent of the narrative's model assessment."""
    age = inputs.get("age_years")
    known_age = isinstance(age, (int, float)) and not isinstance(age, bool)
    if ((known_age and not 18 <= age <= 64)
            or inputs.get("language") not in (None, "", "en")
            or inputs.get("requester") not in (None, "", "self")
            or inputs.get("pregnancy_postpartum") is True):
        return "unsupported"
    if (not known_age or not inputs.get("language") or not inputs.get("requester")
            or inputs.get("pregnancy_postpartum") is not False):
        return "unclear"
    return "supported"


def validate_assessment(assessment, direct=False):
    if not isinstance(assessment, dict):
        return False
    allowed = {"warning", "intent", "information_sufficiency", "contradiction", "scope", "human_review_indication", "direct_route"}
    if set(assessment) - allowed:
        return False
    if direct:
        return isinstance(assessment.get("direct_route"), str) and assessment["direct_route"] in ROUTES | {"defer"}
    enums = {
        "warning": {"current_present", "current_possible", "absent", "unclear_non_emergency"},
        "intent": {"appointment_request", "other", "unclear"},
        "information_sufficiency": {"sufficient", "insufficient", "unclear"},
        "scope": {"supported", "unsupported", "unclear"},
    }
    try:
        def strict_bool(value):
            return type(value) is bool or (isinstance(value, str) and value == "unclear")
        return (all(isinstance(assessment.get(k), str) and assessment[k] in values for k, values in enums.items())
                and strict_bool(assessment.get("contradiction"))
                and strict_bool(assessment.get("human_review_indication")))
    except TypeError:
        return False


def decide(inputs, assessment=None, model_status="valid", variant="no_ai", local_signal=None):
    """Return all actual rule matches in fixed priority, with truthful reasons.

    local_signal is only supplied by the explicit fixture replay test harness;
    production calls always independently inspect current text.
    """
    if not isinstance(inputs, dict):
        inputs = {}
    signal = detect_local_warning(inputs.get("symptom_text", "")) if local_signal is None else local_signal
    direct = variant in DIRECT_VARIANTS
    no_ai = variant == "no_ai"
    valid = no_ai or (model_status == "valid" and validate_assessment(assessment, direct))
    a = assessment if valid and not no_ai else {}
    answers = inputs.get("emergency_answers") or {}
    emergency_answers = {q["id"]: answers.get(q["id"]) for q in QUESTIONS if answers.get(q["id"]) in {"yes", "unsure"}}
    missing = _missing(inputs)
    info = "insufficient" if missing else "sufficient"
    if not no_ai and not direct:
        if not valid:
            info = "unclear" if not missing else "insufficient"
        elif a["information_sufficiency"] != "sufficient":
            info = a["information_sufficiency"] if not missing else "insufficient"
    # In direct mode, this tracks supplied form information, not an invented
    # component judgment. The raw direct decision/defer is retained separately.
    matches, explanations = [], []

    def add(rule, text, evidence):
        matches.append(rule)
        explanations.append({"rule": rule, "text": text, "evidence": evidence})

    if emergency_answers:
        add("E01", "A current emergency check was answered Yes or Unsure. Contact local emergency services now; do not wait for this form.", emergency_answers)
    model_warning = valid and not no_ai and ((direct and a.get("direct_route") == "emergency_guidance") or (not direct and a.get("warning") in {"current_present", "current_possible"}))
    # A completed, valid primary warning must not disappear merely because a
    # later verifier failed. No other partial fields can establish eligibility.
    retained_warning = (model_status == "partial" and not no_ai and not direct and validate_assessment(assessment)
                        and assessment.get("warning") in {"current_present", "current_possible"})
    model_warning = model_warning or retained_warning
    if signal != "none" or model_warning:
        add("E02", "A potential current warning triggered the demonstration emergency rule. Contact local emergency services now; no diagnosis is being made.",
            {"local_signal": signal, "original_text": inputs.get("symptom_text", ""), "assessment_warning": assessment.get("warning") if retained_warning else a.get("warning") if not direct else None,
             "primary_warning_retained_after_verification_failure": retained_warning,
             "direct_route": a.get("direct_route") if direct else None})
    if missing or (valid and not no_ai and not direct and a.get("information_sufficiency") != "sufficient"):
        add("H01", "Required request information is missing or unclear; human review is needed.", {"missing_fields": missing, "information_sufficiency": info})
    if inputs.get("self_reported_urgency") in {"urgent", "unsure"}:
        add("H02", "Your self-reported urgency calls for human review under the demonstration policy.", {"self_reported_urgency": inputs.get("self_reported_urgency")})
    if not _supported(inputs) or (valid and not no_ai and not direct and (
            a.get("scope") != "supported" or a.get("contradiction") is not False
            or a.get("warning") == "unclear_non_emergency" or a.get("intent") != "appointment_request")):
        add("H03", "The request is outside supported demo scope, contradictory, or unclear; human review is needed.",
            {"structured_scope_supported": _supported(inputs), "assessment_scope": a.get("scope"),
             "contradiction": a.get("contradiction"), "intent": a.get("intent")})
    if not valid:
        add("H04", "Automated assessment is unavailable or unusable. Human review is needed.", {"model_status": model_status})
    if valid and not no_ai and ((direct and a.get("direct_route") in {"same_day_human_review", "defer"}) or (not direct and a.get("human_review_indication") is not False)):
        add("H05", "The recorded assessment requests human review or defers a decision.", {"direct_route": a.get("direct_route") if direct else None, "human_review_indication": a.get("human_review_indication") if not direct else None})
    if no_ai:
        if not missing:
            info = "unclear"
        add("H05", "No AI assessment was requested. A staff member must interpret the original description before routine eligibility can be confirmed.",
            {"mode": "no_ai", "structured_information_complete": not missing, "narrative_review": "pending"})
    if not matches:
        add("R01", "The supplied fields meet the demonstration routine conditions. Staff must review the original text and arrange any appointment.",
            {"self_reported_urgency": inputs.get("self_reported_urgency"), "information_sufficiency": info, "narrative_human_review": "pending"})
    first = matches[0]
    route = "emergency_guidance" if first.startswith("E") else "same_day_human_review" if first.startswith("H") else "routine_appointment"
    return {"route": route, "primary_rule": first, "matched_rules": matches,
            "information_sufficiency": info, "information_basis": "structured_fields" if direct or no_ai else "fields_and_assessment",
            "explanations": explanations, "policy_version": POLICY_VERSION,
            "local_signal": signal, "missing_fields": missing,
            "input_segments": segment_text(inputs.get("symptom_text", "")),
            "segmenter_version": "unicode-sentence-v1", "selected_evidence_ids": [],
            "narrative_review": "pending", "is_diagnosis": False,
            "guidance_immediate": bool(emergency_answers or signal != "none")}
