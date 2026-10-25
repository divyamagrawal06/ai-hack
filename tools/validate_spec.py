#!/usr/bin/env python3
"""Check specification declarations, not application behavior or model performance.

No network calls, symptom interpretation, model execution or clinical validation.
Run from any directory: python /workspace/clinic-intake-spec/tools/validate_spec.py
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def reject_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


manifest = json.loads(
    (ROOT / "fixtures/synthetic-cases.json").read_text(encoding="utf-8"),
    object_pairs_hook=reject_duplicates,
    parse_constant=reject_constant,
)
cases = manifest["cases"]
require(manifest["policy_version"] == "demo-policy-0.1", "Policy version mismatch")
require(manifest["contains_real_patient_data"] is False, "Synthetic metadata missing")
require(manifest["clinical_approval"] is False, "Unapproved policy must be labelled")
require(len(cases) == 44, "Expected the documented 44 cases")
require({c["id"] for c in cases} == {f"FX-{i:02d}" for i in range(1, 45)},
        "Case IDs must be unique and complete")
requirements = {f"REQ-{i:02d}" for i in range(1, 19)}
route_for_rule = {
    "E01": "emergency_guidance", "E02": "emergency_guidance",
    **{f"H0{i}": "same_day_human_review" for i in range(1, 6)},
    "R01": "routine_appointment",
}
timing_gaps = []
for case in cases:
    cid = case["id"]
    inp, exp, ops = case["inputs"], case["expected"], case["operations"]
    stub = case["assessment_stub"]
    require(case["synthetic"] is True and bool(case["provenance"]), f"{cid}: provenance")
    require(case["test_status"] == "not_executed", f"{cid}: must remain unexecuted")
    require(set(case["requirements"]) <= requirements, f"{cid}: unknown requirement")
    require(case["variant"] in {"direct_replay", "decomposed_replay"}, f"{cid}: variant")
    answers = inp["emergency_answers"]
    require(set(answers) == {f"CHECK-{i:02d}" for i in range(1, 7)}, f"{cid}: check IDs")
    require(set(answers.values()) <= {"yes", "no", "unsure", "unanswered"}, f"{cid}: check enum")
    require(exp["staff_notification_claim"] is False, f"{cid}: no delivery evidence")
    require(exp["appointment_booked"] is False, f"{cid}: no booking evidence")
    expected_receipt = "request_received" if ops["save"] == "succeeded" else "not_received"
    require(exp["display_status"] == expected_receipt, f"{cid}: receipt truth")
    if exp["route"] is None:
        require(cid == "FX-31" and exp["primary_rule"] is None
                and ops["save"] == "failed" and ops["model_status"] == "not_called"
                and stub is None, f"{cid}: no-decision prerequisites")
    else:
        require(route_for_rule.get(exp["primary_rule"]) == exp["route"], f"{cid}: rule-route mapping")
    structured = any(value in {"yes", "unsure"} for value in answers.values())
    local = case["local_signal"] != "none"
    if structured:
        require(exp["primary_rule"] == "E01" and exp["route"] == "emergency_guidance",
                f"{cid}: structured emergency precedence")
    if local and not structured:
        require(exp["primary_rule"] == "E02", f"{cid}: local warning precedence")
    require(exp["guidance_without_submission_or_model"] == (structured or local),
            f"{cid}: independent guidance declaration")
    if exp["route"] == "emergency_guidance":
        timing = "independent_trigger_required" if structured or local else "known_gap_model_dependent"
        require(exp["emergency_timing_requirement"] == timing, f"{cid}: emergency timing label")
        if timing == "known_gap_model_dependent":
            timing_gaps.append(cid)
    else:
        require(exp["emergency_timing_requirement"] == "not_applicable", f"{cid}: timing applicability")
    if exp["route"] == "routine_appointment":
        require(stub is not None and ops["model_status"] == "valid", f"{cid}: routine assessment")
        require(all(value == "no" for value in answers.values()), f"{cid}: routine emergency answers")
        require(inp["self_reported_urgency"] == "routine", f"{cid}: routine self report")
        require(bool(inp["symptom_text"].strip()) and bool(inp["onset_currentness"]), f"{cid}: completeness")
        require(bool(inp["preferred_times"]) or inp["no_time_preference"], f"{cid}: scheduling answer")
        require(18 <= inp["age_years"] <= 64 and inp["language"] == "en"
                and inp["requester"] == "self" and inp["pregnancy_postpartum"] is False,
                f"{cid}: structured demo scope")
        require(stub["warning"] == "absent" and stub["information_sufficiency"] == "sufficient"
                and stub["contradiction"] is False and stub["scope"] == "supported"
                and stub["intent"] == "appointment_request"
                and stub["human_review_indication"] is False, f"{cid}: routine reference prerequisites")
    if ops["model_status"] in {"timeout", "malformed", "error"} and not (structured or local):
        require(exp["route"] == "same_day_human_review", f"{cid}: unusable model fallback")
require(set(timing_gaps) == {"FX-08", "FX-09", "FX-38"}, "Model-dependent timing gaps must stay explicit")

docs = sorted((ROOT / "docs").glob("0[1-7]-*.md"))
require(len(docs) == 7, "Expected seven specification documents")
req_text = (ROOT / "docs/01-requirements.md").read_text(encoding="utf-8")
plan_text = (ROOT / "docs/06-evaluation-test-plan.md").read_text(encoding="utf-8")
require(set(re.findall(r"^\| (REQ-\d+) \|", req_text, re.M)) == requirements, "Requirement definitions")
require(set(re.findall(r"^\| (REQ-\d+) \|", plan_text, re.M)) == requirements, "Requirement traceability")
test_ids = set(re.findall(r"^\| (T-\d+) \|", plan_text, re.M))
require(test_ids == {f"T-{i:02d}" for i in range(1, 23)}, "Expected 22 planned tests")
require(set(re.findall(r"\bT-\d+\b", plan_text)) <= test_ids, "Unknown test reference")

local_links = 0
for path in ROOT.rglob("*.md"):
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("#"):
            continue
        target = target.split("#", 1)[0]
        if target:
            local_links += 1
            require((path.parent / target).is_file(), f"Broken local link: {path.relative_to(ROOT)} -> {target}")

if errors:
    for error in errors:
        print("ERROR:", error)
    raise SystemExit(1)
print(f"Specification checks passed: {len(docs)} documents, {len(cases)} fixtures, "
      f"{len(requirements)} traced requirements, {len(test_ids)} planned tests, {local_links} local links.")
print("Expected route counts:", dict(Counter(c["expected"]["route"] for c in cases)))
print("Explicit model-dependent emergency timing gaps:", ", ".join(timing_gaps))
print("No application tests, model calls, external-link checks or clinical validation performed.")
