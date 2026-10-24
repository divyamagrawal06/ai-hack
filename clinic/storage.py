"""Transactional synthetic-request storage. No external delivery is performed."""
from __future__ import annotations
import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROUTES = {"routine_appointment", "same_day_human_review", "emergency_guidance"}
REASONS = {"incorrect_input_interpretation", "new_information", "policy_exception", "coverage_issue", "other"}


def now():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or now()).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def deadline(created, route):
    start = datetime.fromisoformat(created)
    if route != "routine_appointment":
        return iso(start + timedelta(minutes=30))
    remaining = 2
    while remaining:
        start += timedelta(days=1)
        if start.weekday() < 5:
            remaining -= 1
    return iso(start)


class StoreError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Store:
    def __init__(self, path, fail_saves=False, coverage=None):
        self.path = str(path)
        self.fail_saves = fail_saves
        self.coverage = coverage or {"available": True, "reason": "Simulated staffed demonstration", "simulated": True}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                    input_hash TEXT NOT NULL, receipt_hash TEXT NOT NULL, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, request_id TEXT NOT NULL,
                    receipt_token TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                    request_id TEXT NOT NULL, timestamp TEXT NOT NULL, actor TEXT NOT NULL,
                    event_type TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
                    BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
                    BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, role TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def event(db, request_id, actor, kind, payload):
        db.execute("INSERT INTO audit(event_id,request_id,timestamp,actor,event_type,payload) VALUES(?,?,?,?,?,?)",
                   (secrets.token_hex(12), request_id, iso(), actor, kind,
                    json.dumps(payload, ensure_ascii=False, allow_nan=False)))

    @staticmethod
    def row(db, request_id):
        row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if not row:
            raise StoreError(404, "Request not found")
        return row, json.loads(row["data"])

    @staticmethod
    def write(db, item):
        item["version"] += 1
        item["updated_at"] = iso()
        db.execute("UPDATE requests SET version=?,input_hash=?,data=? WHERE id=?",
                   (item["version"], item["input_hash"], json.dumps(item, ensure_ascii=False, allow_nan=False), item["id"]))

    def create(self, payload, key, initial_decision=None):
        payload_hash = digest(payload)
        with self.transaction() as db:
            existing = db.execute("SELECT * FROM idempotency WHERE key=?", (key,)).fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise StoreError(409, "Idempotency key was already used with different content")
                _, item = self.row(db, existing["request_id"])
                return item, existing["receipt_token"], False
            if self.fail_saves:
                raise StoreError(503, "Request was not received: simulated persistence outage. No staff were notified.")
            rid, receipt = secrets.token_hex(12), secrets.token_urlsafe(32)
            created = iso()
            initial_route = initial_decision.get("route") if initial_decision else None
            item = {
                "id": rid, "synthetic": True, "version": 1, "input_revision": 1,
                "input_hash": digest(payload["inputs"]), "inputs": payload["inputs"],
                "input_revisions": [{"revision": 1, "inputs": payload["inputs"], "created_at": created}],
                "variant": payload["variant"], "fixture_id": payload.get("fixture_id"),
                "mode": "no_ai" if payload["variant"] == "no_ai" else "pending",
                "assessment_state": "pending", "assessment": None, "assessment_attempts": [],
                "decision": initial_decision, "original_suggestion": None,
                "route": initial_route, "persistence": "received",
                "review_state": "assigned" if self.coverage["available"] else "coverage_unavailable",
                "owner": "demo-triage-team", "claimed_by": None, "claim_expires_at": None,
                "due_at": deadline(created, initial_route), "created_at": created, "updated_at": created,
                "notification_status": "simulated", "coverage": dict(self.coverage),
                "booking": {"state": "not_booked"}, "pending_override": None,
                "emergency_guidance_ever": initial_route == "emergency_guidance",
                "client_events": payload.get("client_events", []), "staff_reviews": [],
            }
            db.execute("INSERT INTO requests(id,version,input_hash,receipt_hash,data) VALUES(?,?,?,?,?)",
                       (rid, 1, item["input_hash"], token_hash(receipt), json.dumps(item, ensure_ascii=False)))
            db.execute("INSERT INTO idempotency(key,payload_hash,request_id,receipt_token) VALUES(?,?,?,?)",
                       (key, payload_hash, rid, receipt))
            self.event(db, rid, "synthetic_requester", "request_received", {
                "inputs": payload["inputs"], "input_revision": 1, "input_hash": item["input_hash"],
                "variant": item["variant"], "fixture_id": item["fixture_id"],
                "client_events": item["client_events"], "client_events_authoritative": False,
            })
            self.event(db, rid, "system", "queue_assigned", {"owner": item["owner"], "due_at": item["due_at"], "coverage": item["coverage"]})
            self.event(db, rid, "system", "notification_simulated", {"delivered": False, "message": "No message was sent to staff or emergency services."})
            if initial_decision:
                self.event(db, rid, "local_policy", "emergency_guidance", initial_decision)
            return item, receipt, True

    def get(self, request_id, receipt=None, staff=False):
        with self.connect() as db:
            row, item = self.row(db, request_id)
            if not staff and (not receipt or not secrets.compare_digest(row["receipt_hash"], token_hash(receipt))):
                raise StoreError(404, "Request not found")
        return self.present(item, staff)

    @staticmethod
    def present(item, staff=True):
        result = dict(item)
        result["assessment_status"] = item["assessment_state"]
        result["review_status"] = item["review_state"]
        result["overdue"] = item["review_state"] != "reviewed" and datetime.fromisoformat(item["due_at"]) < now()
        result["staff_notified"] = False
        result["appointment_booked"] = item["booking"]["state"] == "booked"
        if not staff:
            for field in ("input_revisions", "assessment", "assessment_attempts", "client_events", "staff_reviews", "input_hash"):
                result.pop(field, None)
        return result

    def queue(self):
        with self.connect() as db:
            items = [self.present(json.loads(row[0])) for row in db.execute("SELECT data FROM requests")]
        priority = {"emergency_guidance": 0, "same_day_human_review": 1, None: 1, "routine_appointment": 2}
        return sorted(items, key=lambda x: (x["review_state"] == "reviewed", priority[x["route"]], x["due_at"], x["id"]))

    def audit(self, request_id):
        with self.connect() as db:
            self.row(db, request_id)
            result = []
            for row in db.execute("SELECT * FROM audit WHERE request_id=? ORDER BY sequence", (request_id,)):
                event = dict(row)
                event["payload"] = json.loads(event["payload"])
                result.append(event)
            return result

    def apply_assessment(self, request_id, revision, input_hash, result, decision):
        with self.transaction() as db:
            _, item = self.row(db, request_id)
            attempt = {"input_revision": revision, "input_hash": input_hash, "completed_at": iso(), **result}
            item["assessment_attempts"].append(attempt)
            if item.get("manual_takeover"):
                self.event(db, request_id, "assessor", "late_assessment_after_human_takeover", attempt)
                self.write(db, item)
                return
            if item["input_revision"] != revision or item["input_hash"] != input_hash:
                self.event(db, request_id, "assessor", "stale_assessment_rejected", attempt)
                self.write(db, item)
                return
            item["assessment"] = result
            item["assessment_state"] = "complete" if result.get("model_status") == "valid" else "degraded"
            item["mode"] = result.get("mode", "degraded")
            item["original_suggestion"] = decision
            if item["review_state"] != "reviewed":
                if item["emergency_guidance_ever"] and decision["route"] != "emergency_guidance":
                    self.event(db, request_id, "system", "emergency_downgrade_blocked", {"proposed": decision})
                else:
                    item["decision"] = decision
                    item["route"] = decision["route"]
                item["due_at"] = deadline(item["created_at"], item["route"])
            item["emergency_guidance_ever"] |= decision["route"] == "emergency_guidance"
            self.event(db, request_id, "assessor", "assessment_completed", attempt)
            self.event(db, request_id, "policy", "policy_decision", decision)
            self.write(db, item)

    def mutate(self, request_id, action, payload, user):
        with self.transaction() as db:
            _, item = self.row(db, request_id)
            expected = payload.get("expected_version")
            if type(expected) is not int or expected != item["version"]:
                self.event(db, request_id, user["username"], "concurrent_change_rejected", {"expected_version": expected, "actual_version": item["version"], "action": action})
                db.commit()
                raise StoreError(409, "This request changed. Reload and reconcile before resubmitting.")
            actor = user["username"]
            if action in {"review", "book", "cancel-booking"} and item["claimed_by"] and item["claimed_by"] != actor and item["claim_expires_at"] and datetime.fromisoformat(item["claim_expires_at"]) > now():
                raise StoreError(409, "Another reviewer holds an active claim; arrange an explicit handoff")
            before_route = item["route"]
            if action == "claim":
                if item["claimed_by"] and item["claimed_by"] != actor and item["claim_expires_at"] and datetime.fromisoformat(item["claim_expires_at"]) > now():
                    raise StoreError(409, "Another reviewer holds an active claim")
                item.update(owner=actor, claimed_by=actor, claim_expires_at=iso(now() + timedelta(minutes=15)))
                if item["review_state"] != "reviewed":
                    item["review_state"] = "acknowledged"
            elif action == "review":
                route, reason, comment = payload.get("route"), payload.get("reason"), payload.get("comment", "")
                if not isinstance(route, str) or route not in ROUTES or not isinstance(reason, str) or reason not in REASONS or not isinstance(comment, str) or not comment.strip() or len(comment) > 2000:
                    raise StoreError(422, "A supported route, override reason and nonempty comment of at most 2000 characters are required")
                if item["assessment_state"] == "pending":
                    item["manual_takeover"] = True
                    item["assessment_state"] = "degraded"
                    item["mode"] = "degraded"
                    self.event(db, request_id, actor, "human_review_took_over_pending_assessment", {"late_outputs_will_not_apply": True})
                review = {"actor": actor, "timestamp": iso(), "route": route, "reason": reason, "comment": comment, "previous_route": before_route}
                if before_route == "emergency_guidance" and route != "emergency_guidance":
                    item["pending_override"] = review
                    self.event(db, request_id, actor, "emergency_override_pending_second_review", review)
                else:
                    item["route"] = route
                    item["review_state"] = "reviewed"
                    item["owner"] = actor
                    item["reviewed_at"] = iso()
                    item["pending_override"] = None
                    item["staff_reviews"].append(review)
                    item["due_at"] = deadline(item["created_at"], route)
                    item["emergency_guidance_ever"] |= route == "emergency_guidance"
                    self.event(db, request_id, actor, "staff_reviewed", review)
            elif action == "approve-override":
                pending = item["pending_override"]
                if user["role"] != "supervisor" or not pending or pending["actor"] == actor:
                    raise StoreError(403, "A different authorized supervisor must approve the pending emergency downgrade")
                review = {**pending, "approved_by": actor, "approved_at": iso()}
                item["staff_reviews"].append(review)
                item.update(route=pending["route"], review_state="reviewed", reviewed_at=iso(), pending_override=None)
                item["due_at"] = deadline(item["created_at"], item["route"])
                self.event(db, request_id, actor, "emergency_override_approved", review)
            elif action == "book":
                slot = payload.get("slot")
                if item["review_state"] != "reviewed" or item["pending_override"] or item["route"] == "emergency_guidance":
                    raise StoreError(409, "Booking requires completed staff review and a non-emergency action")
                if not isinstance(slot, str) or not slot.strip() or len(slot) > 200:
                    raise StoreError(422, "A confirmed synthetic appointment slot is required")
                try:
                    parsed_slot = datetime.fromisoformat(slot.replace("Z", "+00:00"))
                    if parsed_slot.tzinfo is None or parsed_slot <= now():
                        raise ValueError()
                except ValueError:
                    raise StoreError(422, "Use a future ISO appointment time with explicit timezone")
                item["booking"] = {"state": "booked", "id": secrets.token_hex(8), "slot": slot, "actor": actor, "confirmed_at": iso(), "synthetic": True}
                self.event(db, request_id, actor, "synthetic_booking_confirmed", item["booking"])
            elif action == "cancel-booking":
                if item["booking"]["state"] != "booked":
                    raise StoreError(409, "No confirmed booking to cancel")
                item["booking"] = {**item["booking"], "state": "cancelled", "cancelled_at": iso()}
                self.event(db, request_id, actor, "booking_cancelled", item["booking"])
            else:
                raise StoreError(404, "Unknown action")
            if action == "claim":
                self.event(db, request_id, actor, "queue_claimed", {"owner": actor, "claim_expires_at": item["claim_expires_at"]})
            self.write(db, item)
            return self.present(item)

    def revise(self, request_id, payload, user, initial_decision=None):
        with self.transaction() as db:
            _, item = self.row(db, request_id)
            if type(payload.get("expected_version")) is not int or payload.get("expected_version") != item["version"]:
                raise StoreError(409, "Request changed; reload before submitting correction")
            item["input_revision"] += 1
            item["inputs"] = payload["inputs"]
            item["input_hash"] = digest(payload["inputs"])
            item["input_revisions"].append({"revision": item["input_revision"], "inputs": item["inputs"], "actor": user["username"], "created_at": iso()})
            item["assessment_state"] = "pending"
            item["assessment"] = None
            item["manual_takeover"] = False
            item["mode"] = "no_ai" if item["variant"] == "no_ai" else "pending"
            item["review_state"] = "assigned" if item["coverage"]["available"] else "coverage_unavailable"
            item["owner"] = "demo-triage-team"
            item["claimed_by"] = None
            item["claim_expires_at"] = None
            item["pending_override"] = None
            if item["booking"]["state"] == "booked":
                item["booking"] = {**item["booking"], "state": "cancelled", "cancelled_at": iso(), "reason": "Input corrected; fresh staff review required"}
                self.event(db, request_id, user["username"], "booking_invalidated_by_revision", item["booking"])
            if initial_decision:
                item["decision"] = initial_decision
                item["route"] = "emergency_guidance"
                item["emergency_guidance_ever"] = True
                self.event(db, request_id, "local_policy", "emergency_guidance", initial_decision)
            elif not item["emergency_guidance_ever"]:
                item["decision"] = None
                item["route"] = None
            else:
                # Previously shown emergency advice remains until authorized human review.
                item["route"] = "emergency_guidance"
                if item["original_suggestion"] and item["original_suggestion"].get("route") == "emergency_guidance":
                    item["decision"] = item["original_suggestion"]
            item["due_at"] = deadline(item["created_at"], "same_day_human_review")
            self.event(db, request_id, user["username"], "input_corrected", {"input_revision": item["input_revision"], "inputs": item["inputs"], "input_hash": item["input_hash"]})
            self.write(db, item)
            return self.present(item)

    def session_create(self, username, role):
        token = secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (token_hash(token), username, role, iso(now()+timedelta(hours=4))))
        return token

    def session_get(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash(token),)).fetchone()
            if not row or datetime.fromisoformat(row["expires_at"]) <= now():
                return None
            return {"username": row["username"], "role": row["role"]}

    def session_delete(self, token):
        if token:
            with self.transaction() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))

    def sweep(self):
        """Expose expired claims and overdue ownership; never pretend to send an alert."""
        with self.transaction() as db:
            for row in db.execute("SELECT data FROM requests").fetchall():
                item = json.loads(row[0])
                changed = False
                if item["claimed_by"] and item["claim_expires_at"] and datetime.fromisoformat(item["claim_expires_at"]) <= now() and item["review_state"] != "reviewed":
                    item.update(claimed_by=None, claim_expires_at=None, owner="demo-triage-team")
                    self.event(db, item["id"], "system", "claim_expired", {"owner": item["owner"]})
                    changed = True
                if item["review_state"] not in {"reviewed", "overdue"} and datetime.fromisoformat(item["due_at"]) <= now():
                    item.update(review_state="overdue", owner="demo-supervisor-team")
                    self.event(db, item["id"], "system", "review_overdue", {"owner": item["owner"], "notification": "simulated_only", "due_at": item["due_at"]})
                    changed = True
                if changed:
                    self.write(db, item)
