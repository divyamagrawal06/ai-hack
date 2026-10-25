"""Local adapter and receipt contracts. Transport doubles are explicit, not live results."""
import copy
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error

from clinic import assessors as a
from clinic.config import DEFAULT_LOCAL_MODEL, public_config
from clinic.policy import decide
from clinic.server import make_server, validate_submission
from clinic.storage import Store


INPUTS = json.loads((Path(__file__).resolve().parents[1] / "fixtures/synthetic-cases.json").read_text(encoding="utf-8"))["cases"][0]["inputs"]
MODEL = DEFAULT_LOCAL_MODEL
TAGS = {"models": [{"name": MODEL, "digest": "test-digest", "details": {"format": "gguf", "parameter_size": "4B", "quantization_level": "Q4_K_M"}}]}


def response(**changes):
    parsed = {"warning": "absent", "intent": "appointment_request", "information_sufficiency": "sufficient",
              "contradiction": "no", "scope": "supported", "human_review_indication": "no",
              "evidence_source_ids": ["S001"]}
    parsed.update(changes)
    return {"model": MODEL, "done": True, "done_reason": "stop", "message": {"role": "assistant", "content": json.dumps(parsed)},
            "prompt_eval_count": 345, "eval_count": 87}


def verification_response(**changes):
    parsed = {"claims": [], "comparison": "One consistent timing statement.", "conflict": "no", "source_ids": []}
    parsed.update(changes)
    return {"model": MODEL, "done": True, "done_reason": "stop", "message": {"role": "assistant", "content": json.dumps(parsed)},
            "prompt_eval_count": 11, "eval_count": 7}


class LocalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"CLINIC_LOCAL_MODEL": MODEL, "CLINIC_OLLAMA_URL": "http://127.0.0.1:11434"})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def assess_response(self, raw):
        with patch.object(a, "_local_http", side_effect=[TAGS, raw, verification_response()]) as transport:
            result = a.assess(copy.deepcopy(INPUTS), "local_ai")
        return result, transport

    def test_local_is_selectable_default_without_keys(self):
        cfg = public_config()
        self.assertEqual(cfg["default_variant"], "local_ai")
        self.assertTrue(next(v for v in cfg["variants"] if v["id"] == "local_ai")["available"])
        self.assertEqual(validate_submission({"synthetic": True, "variant": "local_ai", "inputs": INPUTS})["variant"], "local_ai")
        self.assertEqual(validate_submission({"synthetic": True, "inputs": INPUTS})["variant"], "local_ai")

    def test_endpoint_rejects_remote_urls_and_ambiguous_addresses(self):
        for value in ["https://127.0.0.1:11434", "http://example.com", "http://127.0.0.1.evil.test",
                      "http://192.168.1.2:11434", "http://user:secret@127.0.0.1:11434", "http://127.0.0.1/api", "http://127.0.0.1?remote=yes",
                      "http://127.0.0.1:0", "http://127.0.0.1:65536"]:
            with self.subTest(value=value), patch.dict(os.environ, {"CLINIC_OLLAMA_URL": value}), patch.object(a, "_local_http") as transport:
                result = a.local_status()
                self.assertEqual(result["status"], "invalid_config")
                transport.assert_not_called()
        with patch.dict(os.environ, {"CLINIC_OLLAMA_URL": "http://localhost:11434/"}):
            self.assertEqual(a._local_endpoint(), "http://127.0.0.1:11434")

    def test_status_requires_actual_installed_local_model(self):
        with patch.object(a, "_local_http", return_value=TAGS):
            self.assertTrue(a.local_status()["available"])
        with patch.object(a, "_local_http", return_value={"models": []}):
            self.assertEqual(a.local_status()["status"], "model_missing")
        cloud = copy.deepcopy(TAGS)
        cloud["models"][0]["remote_host"] = "https://cloud.example"
        with patch.object(a, "_local_http", return_value=cloud):
            self.assertEqual(a.local_status()["status"], "invalid_config")

    def test_offline_falls_back_without_claiming_inference(self):
        with patch.object(a, "_local_http", side_effect=urllib.error.URLError("offline")) as transport:
            result = a.assess(INPUTS, "local_ai")
        self.assertEqual(result["model_status"], "unavailable")
        self.assertEqual(result["mode"], "degraded")
        self.assertIsNone(result["assessment"])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(decide(INPUTS, model_status=result["model_status"], variant="local_ai")["route"], "same_day_human_review")

    def test_structured_response_retains_prompt_model_usage_and_grounded_evidence(self):
        result, transport = self.assess_response(response())
        self.assertEqual(result["model_status"], "valid")
        self.assertEqual(result["mode"], "live_model")
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["model_version"], MODEL)
        self.assertEqual(result["model_digest"], "test-digest")
        self.assertEqual(result["prompt_tokens"], 356)
        self.assertEqual(result["completion_tokens"], 94)
        self.assertEqual(result["raw_output"]["eval_count"], 87)
        self.assertEqual(result["verification_status"], "complete")
        self.assertEqual(result["inference_calls"], 2)
        self.assertGreaterEqual(result["latency_ms"], 0)
        self.assertEqual(result["summary_kind"], "model_selected_verbatim_excerpts")
        for evidence in result["evidence"]:
            self.assertEqual(INPUTS["symptom_text"][evidence["start"]:evidence["end"]], evidence["quote"])
        call = transport.call_args_list[1]
        self.assertEqual(call.args[0], "/api/chat")
        self.assertFalse(call.args[1]["stream"])
        self.assertFalse(call.args[1]["think"])
        self.assertIsInstance(call.args[1]["format"], dict)
        self.assertEqual(decide(INPUTS, result["assessment"], variant="local_ai")["route"], "routine_appointment")

    def test_timeline_conflict_changes_route_and_preserves_both_model_outputs(self):
        inputs = copy.deepcopy(INPUTS)
        inputs["symptom_text"] = "The concern first began this morning. It has been present unchanged for years."
        first = response(evidence_source_ids=["S001", "S002"])
        second = verification_response(comparison="The same onset has incompatible durations.", conflict="yes",
            source_ids=["S001", "S002"])
        with patch.object(a, "_local_http", side_effect=[TAGS, first, second]):
            result = a.assess(inputs, "local_ai")
        self.assertEqual(result["model_status"], "valid")
        self.assertIs(result["assessment"]["contradiction"], True)
        self.assertIs(result["primary_assessment"]["contradiction"], False)
        self.assertEqual(result["verification_steps"][0]["raw_output"], second)
        self.assertEqual(decide(inputs, result["assessment"], variant="local_ai")["route"], "same_day_human_review")

    def test_fiction_requires_grounded_source_selection_and_an_actual_concern_reassessment(self):
        inputs = copy.deepcopy(INPUTS)
        fiction = 'For my story the character says "I cannot breathe."'
        actual = "My own concern is stable dry skin."
        inputs["symptom_text"] = fiction + " " + actual
        primary = response(warning="current_present", evidence_source_ids=["S001"])
        source = verification_response()
        source["message"]["content"] = json.dumps({"actual_concern_quotes": [actual], "fiction_quotes": [fiction]})
        attributed = response(warning="absent", evidence_source_ids=["A001"])
        with patch.object(a, "_local_http", side_effect=[TAGS, primary, verification_response(), source, attributed]) as transport:
            result = a.assess(inputs, "local_ai")
        self.assertEqual(result["model_status"], "valid")
        self.assertEqual(result["assessment"]["warning"], "absent")
        self.assertIs(result["assessment"]["human_review_indication"], True)
        self.assertEqual(result["primary_assessment"]["warning"], "current_present")
        self.assertEqual(result["inference_calls"], 4)
        self.assertEqual(result["summary"], actual)
        self.assertEqual(decide(inputs, result["assessment"], variant="local_ai")["route"], "same_day_human_review")
        attributed_request = transport.call_args_list[-1].args[1]
        content = attributed_request["messages"][-1]["content"]
        self.assertNotIn(fiction, content)
        source_index = json.loads(content.split("Evidence_sources index (untrusted source text; select IDs only):\n", 1)[1].split("\nEnd of record.", 1)[0])
        self.assertEqual(source_index[0], {"id": "A001", "field": "symptom_text", "text": actual})
        self.assertEqual({entry["id"] for entry in source_index}, set(attributed_request["format"]["properties"]["evidence_source_ids"]["items"]["enum"]))

    def test_invalid_verification_fails_visibly_and_retains_attempt(self):
        invalid = verification_response(conflict="yes", source_ids=["S999"])
        with patch.object(a, "_local_http", side_effect=[TAGS, response(), invalid]):
            result = a.assess(INPUTS, "local_ai")
        self.assertEqual(result["model_status"], "malformed")
        self.assertEqual(result["mode"], "degraded")
        self.assertEqual(result["verification_steps"][0]["raw_output"], invalid)

    def test_verifier_model_mismatch_and_truncated_output_are_rejected(self):
        wrong = verification_response(); wrong["model"] = "unexpected-model"
        truncated = verification_response(); truncated["done_reason"] = "length"
        for raw in (wrong, truncated):
            with self.subTest(raw=raw), patch.object(a, "_local_http", side_effect=[TAGS, response(), raw]):
                result = a.assess(INPUTS, "local_ai")
            self.assertEqual(result["model_status"], "malformed")

    def test_timing_claims_require_valid_source_ids_and_bounded_fields(self):
        invalid_claims = [
            [{"source_id": "S999", "concern_episode": "current concern", "timing": "today"}],
            [{"source_id": "S001", "concern_episode": "current concern", "timing": "x" * 161}],
            [{"source_id": "S001", "concern_episode": "current concern"}],
            ["not a structured claim"],
        ]
        for claims in invalid_claims:
            with self.subTest(claims=claims), patch.object(a, "_local_http", side_effect=[TAGS, response(), verification_response(claims=claims)]):
                result = a.assess(INPUTS, "local_ai")
            self.assertEqual(result["model_status"], "malformed")

    def test_independent_emergency_bypasses_source_downgrade(self):
        inputs = copy.deepcopy(INPUTS)
        inputs["emergency_answers"]["CHECK-01"] = "yes"
        primary = response(warning="current_present")
        with patch.object(a, "_local_http", side_effect=[TAGS, primary, verification_response()]) as transport:
            result = a.assess(inputs, "local_ai")
        self.assertEqual(result["model_status"], "valid")
        self.assertEqual(result["assessment"]["warning"], "current_present")
        self.assertEqual(transport.call_count, 3)
        self.assertEqual([step["name"] for step in result["verification_steps"]], ["timeline"])
        self.assertEqual(decide(inputs, result["assessment"], variant="local_ai")["route"], "emergency_guidance")

    def test_fabricated_source_quote_is_not_used_to_downgrade_warning(self):
        primary = response(warning="current_present")
        source = verification_response()
        source["message"]["content"] = json.dumps({"actual_concern_quotes": ["Fabricated source"], "fiction_quotes": []})
        with patch.object(a, "_local_http", side_effect=[TAGS, primary, verification_response(), source]):
            result = a.assess(INPUTS, "local_ai")
        self.assertEqual(result["model_status"], "partial")
        self.assertEqual(len(result["verification_steps"]), 2)
        self.assertEqual(result["assessment"]["warning"], "current_present")
        decision = decide(INPUTS, result["assessment"], result["model_status"], "local_ai")
        self.assertEqual(decision["route"], "emergency_guidance")
        self.assertIn("H04", decision["matched_rules"])
        self.assertEqual(result["mode"], "degraded")

    def test_invalid_source_ids_extra_fields_and_truncation_are_rejected(self):
        incomplete = response(); incomplete["done_reason"] = "length"
        wrong_model = response(); wrong_model["model"] = "different-model"
        for raw in [response(evidence_source_ids=["S999"]),
                    response(diagnosis="not allowed"), response(warning="safe"),
                    response(evidence_source_ids="not an array"), response(evidence_source_ids=["S001", "S001"]),
                    response(evidence_source_ids=[{}]), incomplete, wrong_model]:
            with self.subTest(raw=raw):
                result, _ = self.assess_response(raw)
                self.assertEqual(result["model_status"], "malformed")
                self.assertIsNone(result["assessment"])

    def test_structured_emergency_guard_overrules_model_routine(self):
        result, _ = self.assess_response(response())
        inputs = copy.deepcopy(INPUTS)
        inputs["emergency_answers"]["CHECK-01"] = "yes"
        decision = decide(inputs, result["assessment"], variant="local_ai")
        self.assertEqual(decision["route"], "emergency_guidance")
        self.assertEqual(decision["primary_rule"], "E01")

    def test_busy_gpu_uses_human_fallback_without_second_transport(self):
        a.LOCAL_LOCK.acquire()
        try:
            with patch.object(a, "_local_http") as transport:
                result = a.assess(INPUTS, "local_ai")
                transport.assert_not_called()
            self.assertEqual(result["model_status"], "busy")
        finally:
            a.LOCAL_LOCK.release()

    def test_local_wall_deadline_retains_provenance(self):
        with patch.object(a, "LOCAL_DEADLINE_SECONDS", .01), patch.object(a, "_local", side_effect=lambda *args: time.sleep(.05)):
            result = a.assess(INPUTS, "local_ai")
        self.assertEqual(result["model_status"], "timeout")
        self.assertEqual(result["requested_model"], MODEL)
        self.assertTrue(result["local"])

    def test_wall_deadline_retains_only_a_completed_valid_primary_warning(self):
        def slow_verifier(inputs, progress):
            progress.update(assessment={"warning": "current_possible", "intent": "appointment_request",
                "information_sufficiency": "sufficient", "scope": "supported", "contradiction": False,
                "human_review_indication": False}, model_version=MODEL, raw_output=response(), raw_request={"model": MODEL}, metadata={})
            time.sleep(.05)
        with patch.object(a, "LOCAL_DEADLINE_SECONDS", .01), patch.object(a, "_local", side_effect=slow_verifier):
            result = a.assess(INPUTS, "local_ai")
        self.assertEqual(result["model_status"], "partial")
        self.assertEqual(decide(INPUTS, result["assessment"], "partial", "local_ai")["route"], "emergency_guidance")
        ordinary = dict(result["assessment"], warning="absent")
        self.assertEqual(decide(INPUTS, ordinary, "partial", "local_ai")["route"], "same_day_human_review")

    def test_actual_local_pipeline_preserves_primary_at_outer_deadline(self):
        calls = []
        def transport(path, payload=None, **kwargs):
            calls.append(path)
            if path == "/api/tags":
                return TAGS
            if len(calls) == 2:
                return response(warning="current_possible")
            time.sleep(.12)
            return verification_response()
        try:
            with patch.object(a, "LOCAL_DEADLINE_SECONDS", .03), patch.object(a, "_local_http", side_effect=transport):
                result = a.assess(INPUTS, "local_ai")
                self.assertEqual(result["model_status"], "partial")
                self.assertEqual(result["assessment"]["warning"], "current_possible")
                self.assertEqual(decide(INPUTS, result["assessment"], "partial", "local_ai")["route"], "emergency_guidance")
                self.assertEqual(result["verification_status"], "failed")
                self.assertEqual(result["latency_ms"], 30)
                time.sleep(.16)  # Let the discarded worker release its semaphore.
        finally:
            # An unsuccessful assertion must not contaminate subsequent tests.
            time.sleep(.15)

    def test_timeline_ids_map_to_exact_narrative_and_structured_onset(self):
        inputs = copy.deepcopy(INPUTS)
        inputs["onset"] = "This began one hour ago."
        timeline = verification_response(comparison="The onset differs from the narrative duration.", conflict="yes", source_ids=["S001", "onset"])
        with patch.object(a, "_local_http", side_effect=[TAGS, response(), timeline]):
            result = a.assess(inputs, "local_ai")
        self.assertEqual(result["model_status"], "valid")
        self.assertIs(result["assessment"]["contradiction"], True)
        self.assertEqual({span["field"] for span in result["evidence"]}, {"symptom_text", "onset"})
        for span in result["evidence"]:
            self.assertEqual(inputs[span["field"]][span["start"]:span["end"]], span["quote"])

    def test_primary_source_ids_preserve_original_case_and_structured_field(self):
        inputs = copy.deepcopy(INPUTS)
        inputs["symptom_text"] = "A Capitalized concern is described here. A second source retains its own punctuation!"
        inputs["onset"] = "The current episode began yesterday."
        with patch.object(a, "_local_http", side_effect=[TAGS,
                response(evidence_source_ids=["S001", "onset"]), verification_response()]):
            result = a.assess(inputs, "local_ai")
        self.assertEqual(result["model_status"], "valid")
        self.assertEqual(result["evidence"][0]["quote"], "A Capitalized concern is described here.")
        self.assertEqual(result["evidence"][1]["quote"], inputs["onset"])
        self.assertEqual(result["evidence"][1]["field"], "onset")
        for span in result["evidence"]:
            self.assertEqual(inputs[span["field"]][span["start"]:span["end"]], span["quote"])
        payload = result["raw_request"]
        self.assertNotIn("evidence_quotes", payload["format"]["properties"])
        self.assertIn("onset", payload["format"]["properties"]["evidence_source_ids"]["items"]["enum"])
        self.assertEqual(json.loads(result["raw_output"]["message"]["content"])["evidence_source_ids"], ["S001", "onset"])

    def test_trusted_scope_and_missing_fields_reconcile_without_overwriting_raw_model(self):
        inputs = copy.deepcopy(INPUTS)
        inputs["requester"] = "other"
        inputs["emergency_answers"]["CHECK-04"] = "unanswered"
        with patch.object(a, "_local_http", side_effect=[TAGS, response(), verification_response()]):
            result = a.assess(inputs, "local_ai")
        self.assertEqual(result["assessment"]["scope"], "unsupported")
        self.assertEqual(result["assessment"]["information_sufficiency"], "insufficient")
        self.assertIs(result["assessment"]["human_review_indication"], True)
        self.assertEqual(result["primary_assessment"]["scope"], "supported")
        self.assertEqual(result["primary_assessment"]["information_sufficiency"], "sufficient")

    def test_scope_reconciliation_supports_both_inclusive_age_bounds(self):
        for age in (18, 64):
            inputs = copy.deepcopy(INPUTS)
            inputs["age_years"] = age
            with self.subTest(age=age), patch.object(a, "_local_http", side_effect=[TAGS,
                    response(scope="unsupported"), verification_response()]):
                result = a.assess(inputs, "local_ai")
            self.assertEqual(result["model_status"], "valid")
            self.assertEqual(result["assessment"]["scope"], "supported")
            self.assertIs(result["assessment"]["human_review_indication"], False)
            self.assertEqual(result["primary_assessment"]["scope"], "unsupported")
            self.assertEqual(json.loads(result["raw_output"]["message"]["content"])["scope"], "unsupported")
            self.assertIn({"field": "scope", "before": "unsupported", "after": "supported",
                           "basis": "structured_policy_scope"}, result["reconciliation"])
            self.assertEqual(decide(inputs, result["assessment"], "valid", "local_ai")["route"], "routine_appointment")

    def test_scope_reconciliation_keeps_unsupported_and_unknown_facts_nonroutine(self):
        facts = [("age_years", 17, "unsupported"), ("age_years", 65, "unsupported"),
                 ("language", "fr", "unsupported"), ("requester", "other", "unsupported"),
                 ("pregnancy_postpartum", True, "unsupported"),
                 ("age_years", None, "unclear"), ("language", None, "unclear"),
                 ("requester", None, "unclear"), ("pregnancy_postpartum", None, "unclear")]
        for field, value, expected_scope in facts:
            inputs = copy.deepcopy(INPUTS)
            inputs[field] = value
            with self.subTest(field=field, value=value), patch.object(a, "_local_http", side_effect=[TAGS,
                    response(scope="supported"), verification_response()]):
                result = a.assess(inputs, "local_ai")
            self.assertEqual(result["model_status"], "valid")
            self.assertEqual(result["assessment"]["scope"], expected_scope)
            self.assertEqual(result["primary_assessment"]["scope"], "supported")
            self.assertEqual(decide(inputs, result["assessment"], "valid", "local_ai")["route"], "same_day_human_review")

    def test_scope_reconciliation_preserves_actual_model_warning(self):
        source = verification_response()
        source["message"]["content"] = json.dumps({"actual_concern_quotes": [INPUTS["symptom_text"]], "fiction_quotes": []})
        for warning in ("current_present", "current_possible"):
            with self.subTest(warning=warning), patch.object(a, "_local_http", side_effect=[TAGS,
                    response(scope="unsupported", warning=warning), verification_response(), source]):
                result = a.assess(INPUTS, "local_ai")
            self.assertEqual(result["model_status"], "valid")
            self.assertEqual(result["assessment"]["scope"], "supported")
            self.assertEqual(result["assessment"]["warning"], warning)
            self.assertEqual(decide(INPUTS, result["assessment"], "valid", "local_ai")["route"], "emergency_guidance")

    def test_scope_reconciliation_preserves_model_review_and_ambiguity_flags(self):
        with patch.object(a, "_local_http", side_effect=[TAGS,
                response(scope="unsupported", warning="unclear_non_emergency", intent="unclear",
                         information_sufficiency="unclear", contradiction="unclear", human_review_indication="yes"),
                verification_response()]):
            result = a.assess(INPUTS, "local_ai")
        self.assertEqual(result["model_status"], "valid")
        self.assertEqual(result["assessment"], {"scope": "supported", "warning": "unclear_non_emergency",
            "intent": "unclear", "information_sufficiency": "unclear", "contradiction": "unclear", "human_review_indication": True})
        self.assertEqual(decide(INPUTS, result["assessment"], "valid", "local_ai")["route"], "same_day_human_review")

    def test_receipt_has_compact_ai_result_without_transport_payload(self):
        result, _ = self.assess_response(response())
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "test.sqlite")
            item, receipt, _ = store.create({"synthetic": True, "inputs": INPUTS, "variant": "local_ai"}, "one")
            store.apply_assessment(item["id"], 1, item["input_hash"], result, decide(INPUTS, result["assessment"], variant="local_ai"))
            public = store.get(item["id"], receipt)
            self.assertEqual(public["ai"]["model"], MODEL)
            self.assertEqual(public["ai"]["summary"], result["summary"])
            self.assertNotIn("assessment", public)
            self.assertNotIn("raw_request", public["ai"])
            self.assertEqual(store.get(item["id"], staff=True)["assessment"]["raw_request"], result["raw_request"])

    def test_status_http_endpoint_and_pending_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = make_server(0, Path(tmp) / "test.sqlite")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(a, "_local_http", return_value=TAGS):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    connection.request("GET", "/api/ai/status")
                    reply = connection.getresponse()
                    data = json.loads(reply.read())
                    connection.close()
                    self.assertEqual(reply.status, 200)
                    self.assertTrue(data["available"])
                item, _, _ = server.store.create({"synthetic": True, "inputs": INPUTS, "variant": "local_ai"}, "pending")
                self.assertEqual(Store.present(item, False)["ai"]["status"], "pending")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_second_server_cannot_hijack_running_listener(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = make_server(0, Path(tmp) / "first.sqlite")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(OSError):
                    duplicate = make_server(server.server_port, Path(tmp) / "second.sqlite")
                    duplicate.server_close()  # Cleanup if exclusivity regresses.
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/api/health")
                reply = connection.getresponse()
                self.assertEqual(reply.status, 200)
                self.assertEqual(json.loads(reply.read())["status"], "ok")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
