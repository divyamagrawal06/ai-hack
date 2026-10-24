"""HTTP integration and persistence tests with newly invented synthetic records."""
import copy
import http.client
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from clinic.server import make_server
from clinic.storage import Store, StoreError, digest, iso, now

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "fixtures/synthetic-cases.json").read_text())["cases"][0]["inputs"]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(0, Path(self.temp.name)/"test.sqlite")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None
        self.counter = 0

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        combined = {"Content-Type": "application/json"}
        if self.cookie:
            combined["Cookie"] = self.cookie
        combined.update(headers or {})
        encoded = json.dumps(body) if body is not None and not isinstance(body, str) else body
        connection.request(method, path, encoded, combined)
        response = connection.getresponse()
        raw = response.read()
        result_headers = dict(response.getheaders())
        try:
            data = json.loads(raw)
        except ValueError:
            data = raw.decode()
        status = response.status
        connection.close()
        return status, data, result_headers

    def login(self, user="reviewer"):
        status, data, headers = self.request("POST", "/api/login", {"username": user, "password": "demo-"+user})
        self.assertEqual(status, 200, data)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        return headers

    def create(self, changes=None, key=None, variant="no_ai"):
        self.counter += 1
        inputs = copy.deepcopy(FIXTURE)
        inputs.update(changes or {})
        payload = {"synthetic": True, "inputs": inputs, "variant": variant}
        status, data, _ = self.request("POST", "/api/requests", payload, {"Idempotency-Key": key or str(self.counter)})
        self.assertIn(status, (200, 201), data)
        return data

    def detail(self, created):
        status, data, _ = self.request("GET", f'/api/requests/{created["request"]["id"]}?receipt={created["receipt_token"]}')
        self.assertEqual(status, 200, data)
        return data["request"]

    def settled(self, created):
        limit = time.monotonic() + 4
        while time.monotonic() < limit:
            item = self.detail(created)
            if item["assessment_state"] != "pending":
                return item
            time.sleep(.01)
        self.fail("Assessment did not finish")

    def mutate(self, item, action, **fields):
        return self.request("POST", f'/api/requests/{item["id"]}/{action}', {"expected_version": item["version"], **fields})

    def test_spa_entrypoints_serve_static_emergency_notice(self):
        for path in ("/", "/intake", "/staff"):
            status, html, headers = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn("local emergency services", html.lower())
            self.assertIn("text/html", headers["Content-Type"])
            self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_health_and_synthetic_required(self):
        status, body, _ = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["synthetic_only"])
        status, _, _ = self.request("POST", "/api/requests", {"inputs": FIXTURE, "synthetic": False}, {"Idempotency-Key": "x"})
        self.assertEqual(status, 422)
        self.assertEqual(self.server.store.queue(), [])

    def test_receipt_is_distinct_from_review_booking_notification(self):
        created = self.create()
        self.assertEqual(created["request"]["persistence"], "received")
        item = self.settled(created)
        self.assertNotEqual(item["review_state"], "reviewed")
        self.assertFalse(item["appointment_booked"])
        self.assertFalse(item["staff_notified"])
        self.assertEqual(item["notification_status"], "simulated")
        self.assertEqual(item["route"], "same_day_human_review")
        self.assertEqual(item["mode"], "no_ai")

    def test_no_ai_requires_human_narrative_review_before_routine_route(self):
        item = self.settled(self.create())
        self.assertEqual(item["mode"], "no_ai")
        self.assertEqual(item["assessment_state"], "complete")
        self.assertEqual(item["route"], "same_day_human_review")
        self.assertEqual(item["decision"]["primary_rule"], "H05")
        self.assertEqual(item["decision"]["information_sufficiency"], "unclear")
        self.assertNotIn("H04", item["decision"]["matched_rules"])
        self.login()
        status, body, _ = self.mutate(item, "review", route="routine_appointment", reason="other", comment="Human reviewed the original invented narrative and scope")
        self.assertEqual(status, 200)
        self.assertEqual(body["request"]["route"], "routine_appointment")
        self.assertEqual(body["request"]["review_state"], "reviewed")
        self.assertEqual(body["request"]["decision"]["primary_rule"], "H05")
        self.assertFalse(body["request"]["appointment_booked"])

    def test_idempotent_retry_returns_same_receipt_and_single_request(self):
        a, b = self.create(key="same"), self.create(key="same")
        self.assertEqual(a["request"]["id"], b["request"]["id"])
        self.assertEqual(a["receipt_token"], b["receipt_token"])
        self.assertFalse(b["created"])
        self.assertEqual(len(self.server.store.queue()), 1)

    def test_idempotency_key_payload_conflict(self):
        self.create(key="conflict")
        payload = {"synthetic": True, "inputs": {**FIXTURE, "symptom_text": "Entirely different invented text"}, "variant": "no_ai"}
        status, _, _ = self.request("POST", "/api/requests", payload, {"Idempotency-Key": "conflict"})
        self.assertEqual(status, 409)
        self.assertEqual(len(self.server.store.queue()), 1)

    def test_receipt_and_staff_access_boundaries(self):
        created = self.create()
        rid = created["request"]["id"]
        for path in (f"/api/requests/{rid}", f"/api/requests/{rid}?receipt=wrong"):
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("GET", "/api/queue")[0], 401)
        self.assertEqual(self.request("GET", f"/api/requests/{rid}/audit")[0], 401)
        self.assertNotIn("assessment", self.detail(created))
        self.login()
        status, data, _ = self.request("GET", f"/api/requests/{rid}")
        self.assertEqual(status, 200)
        self.assertIn("input_revisions", data["request"])

    def test_login_cookie_logout_and_invalid_password(self):
        self.assertEqual(self.request("POST", "/api/login", {"username": "reviewer", "password": "wrong"})[0], 401)
        headers = self.login()
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(self.request("GET", "/api/session")[1]["user"]["role"], "reviewer")
        self.assertEqual(self.request("POST", "/api/logout", {})[0], 200)
        self.assertEqual(self.request("GET", "/api/queue")[0], 401)

    def test_cross_origin_host_and_content_type_rejected(self):
        self.assertEqual(self.request("POST", "/api/login", {}, {"Origin": "https://elsewhere.test"})[0], 403)
        self.assertEqual(self.request("GET", "/api/health", headers={"Host": "elsewhere.test"})[0], 403)
        self.assertEqual(self.request("POST", "/api/login", "x", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("GET", "/../docs/01-requirements.md")[0], 404)

    def test_duplicate_json_and_nonfinite_rejected(self):
        self.assertEqual(self.request("POST", "/api/login", '{"username":"a","username":"b"}')[0], 400)
        self.assertEqual(self.request("POST", "/api/login", '{"x":NaN}')[0], 400)

    def test_oversized_text_and_unknown_check_rejected_without_truncation(self):
        for inputs in ({**FIXTURE, "symptom_text": "x"*4001}, {**FIXTURE, "emergency_answers": {"CHECK-99": "no"}}):
            status, _, _ = self.request("POST", "/api/requests", {"synthetic": True, "inputs": inputs}, {"Idempotency-Key": "invalid"})
            self.assertEqual(status, 422)
        self.assertEqual(len(self.server.store.queue()), 0)

    def test_emergency_receipt_precedes_slow_assessment(self):
        release = threading.Event()
        original = __import__("clinic.assessors", fromlist=["assess"]).assess
        def slow(*args, **kwargs):
            release.wait(2)
            return original(*args, **kwargs)
        with patch("clinic.server.assessors.assess", slow):
            try:
                created = self.create({"emergency_answers": {**FIXTURE["emergency_answers"], "CHECK-01": "yes"}})
                item = created["request"]
                self.assertEqual(item["assessment_state"], "pending")
                self.assertEqual(item["route"], "emergency_guidance")
                self.assertTrue(item["emergency_guidance_ever"])
                self.assertEqual(item["owner"], "demo-triage-team")
            finally:
                release.set()
            self.settled(created)

    def test_save_failure_never_starts_assessment_or_claims_receipt(self):
        self.server.store.fail_saves = True
        with patch("clinic.server.assessors.assess") as model:
            status, body, _ = self.request("POST", "/api/requests", {"synthetic": True, "inputs": FIXTURE}, {"Idempotency-Key": "save-fail"})
            self.assertEqual(status, 503)
            self.assertIn("not received", body["error"])
            model.assert_not_called()
        self.assertEqual(len(self.server.store.queue()), 0)

    def test_failed_assessor_preserves_received_and_falls_back(self):
        with patch("clinic.server.assessors.assess", side_effect=TimeoutError):
            created = self.create(variant="jev_direct")
            item = self.settled(created)
        self.assertEqual(item["persistence"], "received")
        self.assertEqual(item["assessment_state"], "degraded")
        self.assertEqual(item["mode"], "degraded")
        self.assertEqual(item["route"], "same_day_human_review")
        self.assertFalse(item["staff_notified"])

    def test_claim_and_concurrent_override_conflict_are_audited(self):
        item = self.settled(self.create())
        self.login()
        status, result, _ = self.mutate(item, "claim")
        self.assertEqual(status, 200)
        claimed = result["request"]
        self.assertEqual(claimed["owner"], "reviewer")
        status, result, _ = self.mutate(claimed, "review", route="same_day_human_review", reason="new_information", comment="Invented clarification")
        self.assertEqual(status, 200)
        self.assertEqual(result["request"]["review_state"], "reviewed")
        self.assertEqual(self.mutate(claimed, "review", route="routine_appointment", reason="other", comment="Stale")[0], 409)
        events = self.request("GET", f'/api/requests/{item["id"]}/audit')[1]["events"]
        self.assertIn("concurrent_change_rejected", [event["event_type"] for event in events])
        self.assertIn("staff_reviewed", [event["event_type"] for event in events])

    def test_emergency_downgrade_requires_different_supervisor(self):
        item = self.settled(self.create({"emergency_answers": {**FIXTURE["emergency_answers"], "CHECK-02": "yes"}}))
        self.login()
        status, body, _ = self.mutate(item, "review", route="routine_appointment", reason="incorrect_input_interpretation", comment="Synthetic checkbox correction")
        self.assertEqual(status, 200)
        pending = body["request"]
        self.assertEqual(pending["route"], "emergency_guidance")
        self.assertTrue(pending["pending_override"])
        self.assertEqual(self.mutate(pending, "approve-override")[0], 403)
        self.login("supervisor")
        status, body, _ = self.mutate(pending, "approve-override")
        self.assertEqual(status, 200)
        self.assertEqual(body["request"]["route"], "routine_appointment")
        self.assertTrue(body["request"]["emergency_guidance_ever"])
        self.assertEqual(body["request"]["decision"]["route"], "emergency_guidance")

    def test_booking_requires_review_explicit_timezone_and_confirmation(self):
        item = self.settled(self.create())
        self.login()
        slot = iso(now()+timedelta(days=3))
        self.assertEqual(self.mutate(item, "book", slot=slot)[0], 409)
        status, body, _ = self.mutate(item, "review", route="routine_appointment", reason="other", comment="Synthetic staff review complete")
        self.assertEqual(status, 200)
        item = body["request"]
        self.assertEqual(self.mutate(item, "book", slot="2035-01-01T14:00")[0], 422)
        status, body, _ = self.mutate(item, "book", slot=slot)
        self.assertEqual(status, 200)
        self.assertTrue(body["request"]["appointment_booked"])
        self.assertEqual(body["request"]["booking"]["slot"], slot)
        self.assertFalse(body["request"]["staff_notified"])
        self.assertEqual(self.mutate(body["request"], "cancel-booking")[1]["request"]["booking"]["state"], "cancelled")

    def test_after_hours_preserves_route_and_truthful_unavailability(self):
        self.server.store.coverage = {"available": False, "reason": "Simulated after hours", "simulated": True}
        item = self.settled(self.create({"self_reported_urgency": "urgent"}))
        self.assertEqual(item["route"], "same_day_human_review")
        self.assertEqual(item["review_state"], "coverage_unavailable")
        self.assertFalse(item["coverage"]["available"])
        self.assertFalse(item["staff_notified"])

    def test_original_inputs_revisions_and_stale_assessment_are_preserved(self):
        created = self.create()
        original = self.settled(created)
        self.login()
        inputs = {**FIXTURE, "symptom_text": "A newly invented correction", "self_reported_urgency": "urgent"}
        status, body, _ = self.mutate(original, "revisions", inputs=inputs)
        self.assertEqual(status, 200)
        latest = self.settled(created)
        self.assertEqual(latest["input_revision"], 2)
        self.assertEqual(latest["input_revisions"][0]["inputs"]["symptom_text"], FIXTURE["symptom_text"])
        self.assertEqual(latest["route"], "same_day_human_review")
        stale_result = {"assessment": None, "model_status": "valid", "mode": "no_ai"}
        self.server.store.apply_assessment(original["id"], 1, digest(FIXTURE), stale_result, {"route": "routine_appointment"})
        latest = self.detail(created)
        self.assertEqual(latest["route"], "same_day_human_review")
        kinds = [e["event_type"] for e in self.server.store.audit(original["id"])]
        self.assertIn("stale_assessment_rejected", kinds)
        self.assertIn("input_corrected", kinds)

    def test_audit_cannot_be_updated_or_deleted(self):
        created = self.create()
        self.settled(created)
        with self.server.store.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM audit")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE audit SET actor='changed'")

    def test_overdue_and_expired_claims_escalate_without_delivery_claim(self):
        item = self.settled(self.create({"self_reported_urgency": "urgent"}))
        self.login()
        item = self.mutate(item, "claim")[1]["request"]
        with self.server.store.transaction() as db:
            _, stored = self.server.store.row(db, item["id"])
            stored["due_at"] = iso(now()-timedelta(minutes=2))
            stored["claim_expires_at"] = iso(now()-timedelta(minutes=1))
            self.server.store.write(db, stored)
        self.server.store.sweep()
        item = self.server.store.get(item["id"], staff=True)
        self.assertEqual(item["review_state"], "overdue")
        self.assertEqual(item["owner"], "demo-supervisor-team")
        self.assertIsNone(item["claimed_by"])
        self.assertFalse(item["staff_notified"])
        self.assertEqual(item["route"], "same_day_human_review")

    def test_invalid_enum_types_return_422_not_server_error(self):
        for changes in ({"self_reported_urgency": []}, {"emergency_answers": {"CHECK-01": {}}}):
            status, _, _ = self.request("POST", "/api/requests", {"synthetic": True, "inputs": {**FIXTURE, **changes}}, {"Idempotency-Key": "bad-type"})
            self.assertEqual(status, 422)
        status, _, _ = self.request("POST", "/api/requests", {"synthetic": True, "inputs": FIXTURE, "variant": []}, {"Idempotency-Key": "bad-variant"})
        self.assertEqual(status, 422)
        item = self.settled(self.create())
        self.login()
        self.assertEqual(self.mutate(item, "review", route=[], reason="other", comment="")[0], 422)

    def test_emergency_revision_is_immediate_and_invalidates_old_booking(self):
        item = self.settled(self.create())
        self.login()
        item = self.mutate(item, "review", route="routine_appointment", reason="other", comment="Synthetic reviewed")[1]["request"]
        item = self.mutate(item, "book", slot=iso(now()+timedelta(days=3)))[1]["request"]
        release = threading.Event()
        original = __import__("clinic.assessors", fromlist=["assess"]).assess
        def slow(*args, **kwargs):
            release.wait(2)
            return original(*args, **kwargs)
        emergency_inputs = {**FIXTURE, "emergency_answers": {**FIXTURE["emergency_answers"], "CHECK-01": "yes"}}
        with patch("clinic.server.assessors.assess", slow):
            try:
                status, body, _ = self.mutate(item, "revisions", inputs=emergency_inputs)
                self.assertEqual(status, 200)
                changed = body["request"]
                self.assertEqual(changed["route"], "emergency_guidance")
                self.assertEqual(changed["assessment_state"], "pending")
                self.assertEqual(changed["booking"]["state"], "cancelled")
                self.assertEqual(changed["input_revisions"][0]["inputs"], FIXTURE)
            finally:
                release.set()
        kinds = [x["event_type"] for x in self.server.store.audit(item["id"])]
        self.assertIn("booking_invalidated_by_revision", kinds)

    def test_staff_can_take_over_pending_model_and_late_output_does_not_apply(self):
        release = threading.Event()
        original = __import__("clinic.assessors", fromlist=["assess"]).assess
        def slow(*args, **kwargs):
            release.wait(2)
            return original(*args, **kwargs)
        with patch("clinic.server.assessors.assess", slow):
            try:
                created = self.create()
                self.login()
                pending = self.detail(created)
                self.assertEqual(pending["assessment_state"], "pending")
                status, body, _ = self.mutate(pending, "review", route="same_day_human_review", reason="new_information", comment="Human review proceeds despite slow model")
                self.assertEqual(status, 200)
                self.assertEqual(body["request"]["assessment_state"], "degraded")
                self.assertEqual(body["request"]["review_state"], "reviewed")
            finally:
                release.set()
            limit = time.monotonic()+3
            while time.monotonic() < limit:
                kinds = [x["event_type"] for x in self.server.store.audit(pending["id"])]
                if "late_assessment_after_human_takeover" in kinds:
                    break
                time.sleep(.01)
            self.assertIn("late_assessment_after_human_takeover", kinds)
            item = self.detail(created)
            self.assertEqual(item["route"], "same_day_human_review")
            self.assertEqual(item["mode"], "degraded")

    def test_corrected_input_retains_reported_prior_emergency_guidance(self):
        event = {"kind": "emergency_guidance_displayed", "source": "structured", "rule": "E01", "timestamp": iso(), "detail": {"question": "CHECK-01", "answer": "yes"}}
        payload = {"synthetic": True, "inputs": FIXTURE, "variant": "no_ai", "client_events": [event]}
        status, created, _ = self.request("POST", "/api/requests", payload, {"Idempotency-Key": "history"})
        self.assertEqual(status, 201)
        item = self.settled(created)
        self.assertEqual(item["route"], "emergency_guidance")
        self.assertTrue(item["emergency_guidance_ever"])
        self.assertEqual(item["decision"]["explanations"][0]["evidence"]["source"], "client_reported_prior_guidance")
        self.assertTrue(item["decision"]["explanations"][0]["evidence"]["client_report_unverified"])

    def test_malformed_client_history_is_not_trusted_or_retained(self):
        payload = {"synthetic": True, "inputs": FIXTURE, "variant": "no_ai", "client_events": [{"rule": "E01", "source": "invented", "arbitrary": "not retained"}]}
        status, created, _ = self.request("POST", "/api/requests", payload, {"Idempotency-Key": "bad-history"})
        self.assertEqual(status, 201)
        item = self.settled(created)
        self.assertEqual(item["route"], "same_day_human_review")
        staff_item = self.server.store.get(item["id"], staff=True)
        self.assertEqual(staff_item["client_events"], [])

    def test_pending_durable_assessment_resumes_on_server_restart(self):
        path = Path(self.temp.name)/"recovery.sqlite"
        store = Store(path)
        pending, receipt, _ = store.create({"synthetic": True, "inputs": FIXTURE, "variant": "no_ai"}, "recover")
        recovered = make_server(0, path)
        try:
            limit = time.monotonic()+3
            while time.monotonic() < limit:
                item = recovered.store.get(pending["id"], receipt)
                if item["assessment_state"] != "pending":
                    break
                time.sleep(.01)
            self.assertEqual(item["assessment_state"], "complete")
            self.assertEqual(item["route"], "same_day_human_review")
            self.assertIn("assessment_resumed_after_restart", [x["event_type"] for x in recovered.store.audit(item["id"])])
        finally:
            recovered.server_close()

    def test_restart_retains_records_and_audit(self):
        created = self.create()
        self.settled(created)
        reopened = Store(self.server.store.path)
        item = reopened.get(created["request"]["id"], created["receipt_token"])
        self.assertEqual(item["persistence"], "received")
        self.assertEqual(item["inputs"], FIXTURE)
        self.assertGreater(len(reopened.audit(item["id"])), 2)


if __name__ == "__main__":
    unittest.main()
