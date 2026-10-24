"""Executable policy conformance and bounded local-detector tests.

Authored replay fixtures test rule composition, never live-model accuracy.
FX-31 is intentionally left to persistence/API tests: no decision exists before
its failed initial save, so invoking decide would violate the application flow.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from clinic.policy import decide, detect_local_warning
from clinic.config import POLICY_VERSION

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "fixtures" / "synthetic-cases.json").read_text())
CASES = {case["id"]: case for case in FIXTURES["cases"]}


def base_inputs():
    return copy.deepcopy(CASES["FX-01"]["inputs"])


class ReplayPolicyConformanceTests(unittest.TestCase):
    """One separately reported test per authored decision-bearing fixture."""


def _fixture_test(case):
    def test(self):
        result = decide(
            copy.deepcopy(case["inputs"]),
            assessment=copy.deepcopy(case["assessment_stub"]),
            model_status=case["operations"]["model_status"],
            variant=case["variant"],
            local_signal=case["local_signal"],
        )
        self.assertEqual(result["route"], case["expected"]["route"])
        self.assertEqual(result["primary_rule"], case["expected"]["primary_rule"])
        self.assertIn(result["primary_rule"], result["matched_rules"])
        self.assertEqual(result["policy_version"], POLICY_VERSION)
        # Historical authored signals deliberately replay demo-policy-0.1;
        # the current policy version must be reported rather than forged.
        self.assertTrue(result["explanations"], "A selected rule needs an input/rule explanation")
    test.__doc__ = f"{case['id']}: {case['title']} (authored replay, not model evaluation)."
    return test


for _case in FIXTURES["cases"]:
    if _case["expected"]["route"] is not None:
        setattr(ReplayPolicyConformanceTests, "test_" + _case["id"].replace("-", "_"), _fixture_test(_case))


class LocalEmergencyDetectorTests(unittest.TestCase):
    def _check_actual_local_trigger(self, case_id):
        case = CASES[case_id]
        signal = detect_local_warning(case["inputs"]["symptom_text"])
        self.assertIn(signal, {"current_explicit_demo_warning", "current_possible_demo_warning"})
        # No authored local signal and no assessor: this exercises implemented
        # local behavior, including the three previously model-dependent gaps.
        result = decide(copy.deepcopy(case["inputs"]), assessment=None,
                        model_status="not_called", variant="no_ai")
        self.assertEqual(result["route"], "emergency_guidance")
        self.assertEqual(result["primary_rule"], "E02")

    def test_current_explicit_breathing_warning(self):
        self._check_actual_local_trigger("FX-06")

    def test_possible_current_overdose_warning(self):
        self._check_actual_local_trigger("FX-07")

    def test_swelling_and_worsening_breathing_without_model(self):
        self._check_actual_local_trigger("FX-08")

    def test_uncertain_breathing_warning_without_model(self):
        self._check_actual_local_trigger("FX-09")

    def test_third_person_current_warning(self):
        self._check_actual_local_trigger("FX-27")

    def test_local_warning_survives_assessor_timeout(self):
        self._check_actual_local_trigger("FX-29")

    def test_sudden_breathing_warning_without_model(self):
        self._check_actual_local_trigger("FX-38")

    def test_explicit_negation_does_not_trigger(self):
        self.assertEqual(detect_local_warning(CASES["FX-25"]["inputs"]["symptom_text"]), "none")

    def test_historical_resolved_warning_does_not_trigger(self):
        self.assertEqual(detect_local_warning(CASES["FX-26"]["inputs"]["symptom_text"]), "none")

    def test_quoted_fiction_is_not_current_emergency_evidence(self):
        self.assertEqual(detect_local_warning(CASES["FX-28"]["inputs"]["symptom_text"]), "none")

    def test_history_does_not_suppress_new_current_warning(self):
        text = "Last year I was healthy but now I cannot breathe."
        self.assertIn(detect_local_warning(text), {"current_explicit_demo_warning", "current_possible_demo_warning"})
        inputs = base_inputs()
        inputs["symptom_text"] = text
        self.assertEqual(decide(inputs, variant="no_ai")["route"], "emergency_guidance")

    def test_fictional_quote_does_not_suppress_separate_current_warning(self):
        text = 'In my story the character says "I cannot breathe." I cannot breathe right now.'
        self.assertIn(detect_local_warning(text), {"current_explicit_demo_warning", "current_possible_demo_warning"})
        inputs = base_inputs()
        inputs["symptom_text"] = text
        self.assertEqual(decide(inputs, variant="no_ai")["route"], "emergency_guidance")

    def test_plain_routine_description_does_not_trigger(self):
        self.assertEqual(detect_local_warning(base_inputs()["symptom_text"]), "none")


class PolicySafetyInvariantsTests(unittest.TestCase):
    def test_each_structured_yes_or_unsure_precedes_any_assessor(self):
        for check_id in base_inputs()["emergency_answers"]:
            for answer in ("yes", "unsure"):
                with self.subTest(check=check_id, answer=answer):
                    inputs = base_inputs()
                    inputs["emergency_answers"][check_id] = answer
                    inputs["symptom_text"] = ""
                    result = decide(inputs, assessment=None, model_status="error", variant="jev_decomposed")
                    self.assertEqual(result["route"], "emergency_guidance")
                    self.assertEqual(result["primary_rule"], "E01")

    def test_preferred_times_cannot_lower_route(self):
        for fixture_id in ("FX-01", "FX-02", "FX-05"):
            case = CASES[fixture_id]
            for preference in (["tomorrow"], ["three weeks from now"], ["weekday afternoon"]):
                with self.subTest(case=fixture_id, preference=preference):
                    inputs = copy.deepcopy(case["inputs"])
                    inputs["preferred_times"] = preference
                    result = decide(inputs, variant="no_ai")
                    self.assertEqual(result["route"], "emergency_guidance" if fixture_id == "FX-05" else "same_day_human_review")

    def test_information_missing_does_not_suppress_emergency(self):
        inputs = base_inputs()
        inputs["symptom_text"] = ""
        inputs["onset_currentness"] = None
        inputs["emergency_answers"]["CHECK-01"] = "yes"
        result = decide(inputs, variant="no_ai")
        self.assertEqual(result["route"], "emergency_guidance")
        self.assertIn(result["information_sufficiency"], {"insufficient", "unclear"})

    def test_unanswered_check_does_not_become_no(self):
        inputs = base_inputs()
        inputs["emergency_answers"]["CHECK-02"] = "unanswered"
        result = decide(inputs, variant="no_ai")
        self.assertEqual(result["route"], "same_day_human_review")
        self.assertEqual(result["primary_rule"], "H01")

    def test_missing_check_does_not_become_no(self):
        inputs = base_inputs()
        del inputs["emergency_answers"]["CHECK-02"]
        self.assertNotEqual(decide(inputs, variant="no_ai")["route"], "routine_appointment")

    def test_missing_preference_is_incomplete_but_explicit_no_preference_is_valid(self):
        inputs = base_inputs()
        inputs["preferred_times"] = []
        inputs["no_time_preference"] = False
        self.assertEqual(decide(inputs, variant="no_ai")["primary_rule"], "H01")
        inputs["no_time_preference"] = True
        self.assertEqual(decide(inputs, variant="no_ai")["route"], "same_day_human_review")
        self.assertEqual(decide(inputs, variant="no_ai")["primary_rule"], "H05")

    def test_unknown_scope_values_never_receive_routine(self):
        for field, value in (("age_years", None), ("language", "unknown"),
                             ("requester", "unsure"), ("pregnancy_postpartum", None)):
            with self.subTest(field=field):
                inputs = base_inputs()
                inputs[field] = value
                self.assertEqual(decide(inputs, variant="no_ai")["route"], "same_day_human_review")

    def test_invalid_or_missing_assessment_never_receives_routine(self):
        for status in ("timeout", "malformed", "error"):
            with self.subTest(status=status):
                result = decide(base_inputs(), assessment=None, model_status=status, variant="jev_decomposed")
                self.assertEqual(result["route"], "same_day_human_review")
                self.assertIn("H04", result["matched_rules"])
        self.assertNotEqual(decide(base_inputs(), assessment=None, variant="jev_decomposed")["route"], "routine_appointment")

    def test_invalid_response_does_not_partly_support_routine(self):
        result = decide(base_inputs(), assessment={"information_sufficiency": "sufficient", "direct_route": "routine_appointment"},
                        model_status="malformed", variant="jev_decomposed")
        self.assertEqual(result["route"], "same_day_human_review")
        self.assertIn("H04", result["matched_rules"])

    def test_no_ai_is_an_operating_mode_not_a_model_outage(self):
        result = decide(base_inputs(), assessment=None, model_status="not_called", variant="no_ai")
        self.assertEqual(result["route"], "same_day_human_review")
        self.assertEqual(result["primary_rule"], "H05")
        self.assertEqual(result["information_sufficiency"], "unclear")
        self.assertEqual(result["narrative_review"], "pending")
        self.assertNotIn("H04", result["matched_rules"])

    def test_unreviewed_vague_or_conflicting_baseline_narratives_never_receive_routine(self):
        for case_id in ("FX-11", "FX-14", "FX-24", "FX-28", "FX-39"):
            with self.subTest(case=case_id):
                result = decide(copy.deepcopy(CASES[case_id]["inputs"]), variant="no_ai")
                self.assertEqual(result["route"], "same_day_human_review")
                self.assertIn("H05", result["matched_rules"])
                self.assertEqual(result["information_sufficiency"], "unclear")
                self.assertEqual(result["narrative_review"], "pending")

    def test_direct_choice_does_not_require_hidden_decomposed_fields(self):
        result = decide(base_inputs(), assessment={"direct_route": "routine_appointment"}, variant="direct")
        self.assertEqual(result["route"], "routine_appointment")
        self.assertEqual(result["primary_rule"], "R01")

    def test_direct_defer_maps_to_review(self):
        result = decide(base_inputs(), assessment={"direct_route": "defer"}, variant="direct")
        self.assertEqual(result["route"], "same_day_human_review")
        self.assertEqual(result["primary_rule"], "H05")

    def test_direct_emergency_is_preserved(self):
        result = decide(base_inputs(), assessment={"direct_route": "emergency_guidance"}, variant="direct")
        self.assertEqual(result["route"], "emergency_guidance")
        self.assertEqual(result["primary_rule"], "E02")

    def test_direct_unknown_class_is_rejected(self):
        result = decide(base_inputs(), assessment={"direct_route": "clinically_safe"}, variant="direct")
        self.assertEqual(result["route"], "same_day_human_review")
        self.assertIn("H04", result["matched_rules"])

    def test_direct_malformed_label_types_fail_into_review(self):
        for value in ([], {}, 0, True, None):
            with self.subTest(value=value):
                result = decide(base_inputs(), assessment={"direct_route": value}, variant="direct")
                self.assertEqual(result["route"], "same_day_human_review")
                self.assertIn("H04", result["matched_rules"])

    def test_decomposed_numeric_booleans_are_invalid(self):
        for field in ("contradiction", "human_review_indication"):
            for value in (0, 1):
                with self.subTest(field=field, value=value):
                    assessment = copy.deepcopy(CASES["FX-01"]["assessment_stub"])
                    assessment[field] = value
                    result = decide(base_inputs(), assessment=assessment, variant="jev_decomposed")
                    self.assertIn("H04", result["matched_rules"])
                    self.assertEqual(result["route"], "same_day_human_review")

    def test_direct_routine_cannot_fill_missing_input_by_inference(self):
        inputs = base_inputs()
        inputs["onset_currentness"] = None
        result = decide(inputs, assessment={"direct_route": "routine_appointment"}, variant="direct")
        self.assertEqual(result["route"], "same_day_human_review")
        self.assertEqual(result["primary_rule"], "H01")

    def test_structured_emergency_overrides_direct_routine(self):
        inputs = base_inputs()
        inputs["emergency_answers"]["CHECK-01"] = "yes"
        result = decide(inputs, assessment={"direct_route": "routine_appointment"}, variant="direct")
        self.assertEqual(result["route"], "emergency_guidance")
        self.assertEqual(result["primary_rule"], "E01")


if __name__ == "__main__":
    unittest.main()
