"""Local, synthetic-only clinic demonstration HTTP service (standard library)."""
from __future__ import annotations
import argparse
import json
import mimetypes
import os
import secrets
import socket
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .storage import Store, StoreError
from . import policy, assessors, config, reports

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {"local_ai", "no_ai", "replay", "jev_direct", "jev_decomposed", "llm"}
USERS = {"reviewer": ("demo-reviewer", "reviewer"), "supervisor": ("demo-supervisor", "supervisor")}


def strict_json(data):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON keys are not accepted")
            result[key] = value
        return result
    def constant(_value):
        raise ValueError("Non-finite JSON numbers are not accepted")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def validate_inputs(inputs):
    if not isinstance(inputs, dict):
        raise StoreError(422, "inputs must be an object")
    allowed = {"symptom_text", "self_reported_urgency", "preferred_times", "no_time_preference", "age_years", "language", "requester", "pregnancy_postpartum", "onset_currentness", "emergency_answers", "onset", "clinic_timezone"}
    if set(inputs) - allowed:
        raise StoreError(422, "Unexpected input fields")
    text = inputs.get("symptom_text", "")
    if not isinstance(text, str) or len(text) > 4000:
        raise StoreError(422, "Symptom text must be at most 4000 characters; it is never silently truncated")
    if not isinstance(inputs.get("self_reported_urgency"), (str, type(None))) or inputs.get("self_reported_urgency") not in {None, "", "routine", "urgent", "unsure"}:
        raise StoreError(422, "Unknown self-reported status")
    age = inputs.get("age_years")
    if age is not None and (type(age) is not int or age < 0 or age > 125):
        raise StoreError(422, "Synthetic age must be a whole number from 0 to 125 or null")
    for field in ("no_time_preference", "pregnancy_postpartum"):
        if inputs.get(field) is not None and type(inputs[field]) is not bool:
            raise StoreError(422, f"{field} must be true, false or null")
    preferred = inputs.get("preferred_times", [])
    if not isinstance(preferred, list) or len(preferred) > 8 or any(not isinstance(x, str) or len(x) > 200 for x in preferred):
        raise StoreError(422, "Preferred times must be a list of up to eight short strings")
    for field in ("language", "requester", "onset_currentness", "onset", "clinic_timezone"):
        value = inputs.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 200):
            raise StoreError(422, f"Invalid {field}")
    answers = inputs.get("emergency_answers", {})
    if not isinstance(answers, dict) or set(answers) - {f"CHECK-{i:02d}" for i in range(1, 7)}:
        raise StoreError(422, "Invalid emergency question identifiers")
    if any(not isinstance(value, str) or value not in {"yes", "no", "unsure", "unanswered"} for value in answers.values()):
        raise StoreError(422, "Invalid emergency answer")
    # Missing answers are intentionally not converted into reassuring 'no' values.
    return inputs


def guidance_events(events):
    """Keep only bounded, recognizable browser reports; they remain untrusted claims."""
    accepted = []
    for event in events:
        if event.get("kind") != "emergency_guidance_displayed":
            continue
        detail = event.get("detail")
        if not isinstance(detail, dict):
            continue
        source, rule = event.get("source"), event.get("rule")
        valid = False
        clean_detail = {}
        if source == "structured" and rule == "E01":
            question, answer = detail.get("question"), detail.get("answer")
            valid = isinstance(question, str) and question in {f"CHECK-{i:02d}" for i in range(1, 7)} and isinstance(answer, str) and answer in {"yes", "unsure"}
            clean_detail = {"question": question, "answer": answer}
        elif source == "local_text" and rule == "E02":
            signal = detail.get("signal")
            valid = isinstance(signal, str) and signal in {"current_explicit_demo_warning", "current_possible_demo_warning"}
            clean_detail = {"signal": signal}
        stamp = event.get("timestamp")
        if valid and isinstance(stamp, str) and len(stamp) <= 64:
            accepted.append({"kind": "emergency_guidance_displayed", "source": source, "rule": rule, "timestamp": stamp, "detail": clean_detail, "client_report_unverified": True})
    return accepted


def retain_reported_guidance(decision, events):
    if not events or decision["route"] == "emergency_guidance":
        return decision
    explanation = {"rule": "E02", "text": "This browser reported emergency guidance earlier in this request; it remains flagged for staff review. Contact local emergency services now if this may be an emergency; do not wait for the form.",
                   "evidence": {"source": "client_reported_prior_guidance", "client_report_unverified": True, "events": events}}
    return {**decision, "route": "emergency_guidance", "primary_rule": "E02",
            "matched_rules": ["E02"] + [rule for rule in decision["matched_rules"] if rule.startswith("H")],
            "explanations": [explanation] + [entry for entry in decision["explanations"] if entry["rule"].startswith("H")],
            "client_reported_prior_guidance": True}


def validate_submission(payload):
    if payload.get("synthetic") is not True:
        raise StoreError(422, "Confirm that all entered information is newly invented synthetic data")
    variant = payload.get("variant", "local_ai")
    if not isinstance(variant, str) or variant not in VARIANTS:
        raise StoreError(422, "Unknown assessment variant")
    validate_inputs(payload.get("inputs"))
    fixture = payload.get("fixture_id")
    if fixture is not None and (not isinstance(fixture, str) or len(fixture) > 30):
        raise StoreError(422, "Invalid fixture identifier")
    events = payload.get("client_events", payload.get("client_alerts", []))
    if not isinstance(events, list) or len(events) > 30 or any(not isinstance(x, dict) or len(json.dumps(x)) > 1000 for x in events):
        raise StoreError(422, "Client guidance events exceed the bounded audit format")
    return {"synthetic": True, "inputs": payload["inputs"], "variant": variant,
            "fixture_id": fixture, "client_events": guidance_events(events)}


class ClinicServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR permits an unrelated second listener on the same port.
    # Unix keeps fast restart semantics; Windows instead claims the port exclusively.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, store):
        super().__init__(address, Handler)
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="clinic-assessment")
        self.stopping = threading.Event()
        self.sweeper = threading.Thread(target=self.sweep_loop, daemon=True)
        self.sweeper.start()
        # A snapshot/restart retains files, not live workers. Resume durable pending work.
        for item in self.store.queue():
            if item["assessment_state"] == "pending":
                with self.store.transaction() as db:
                    self.store.event(db, item["id"], "system", "assessment_resumed_after_restart", {"input_revision": item["input_revision"]})
                self.assess_request(item)

    def sweep_loop(self):
        while not self.stopping.wait(2):
            try:
                self.store.sweep()
            except sqlite3.Error:
                # A database outage must not be disguised as successful notification.
                pass

    def assess_request(self, item):
        def job():
            try:
                result = assessors.assess(item["inputs"], item["variant"], fixture_id=item.get("fixture_id"))
                decision = policy.decide(item["inputs"], assessment=result.get("assessment"),
                                         model_status=result.get("model_status", "error"), variant=result.get("policy_variant", item["variant"]))
            except Exception as error:
                result = {"assessment": None, "model_status": "error", "mode": "degraded", "raw_output": None,
                          "model_version": None, "error": f"Assessment failed ({type(error).__name__}); human review is required."}
                decision = policy.decide(item["inputs"], assessment=None, model_status="error", variant=item["variant"])
            try:
                self.store.apply_assessment(item["id"], item["input_revision"], item["input_hash"], result, decision)
            except sqlite3.Error:
                # Original durable pending task remains visible for operations review.
                pass
        self.pool.submit(job)

    def server_close(self):
        # TCPServer calls this on bind failure before our worker fields exist.
        if hasattr(self, "stopping"):
            self.stopping.set()
        if hasattr(self, "sweeper"):
            self.sweeper.join(timeout=3)
        if hasattr(self, "pool"):
            self.pool.shutdown(wait=True, cancel_futures=False)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = "SyntheticClinic/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, fmt, *args):
        # Do not put receipt tokens or request text into transport logs.
        return

    def json_response(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def common_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def check_request(self):
        host = self.headers.get("Host", "")
        try:
            parsed = urlsplit("http://" + host)
            host_ok = parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port == self.server.server_port
        except ValueError:
            host_ok = False
        if not host_ok:
            raise StoreError(403, "This synthetic demonstration only accepts its local host")
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + host:
            raise StoreError(403, "Cross-origin requests are not accepted")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise StoreError(403, "Cross-site requests are not accepted")

    def cookie_token(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        return cookies["clinic_session"].value if "clinic_session" in cookies else None

    def user(self, required=False):
        user = self.server.store.session_get(self.cookie_token())
        if required and not user:
            raise StoreError(401, "Staff sign-in required")
        return user

    def read_json(self, maximum=65536):
        if self.headers.get_content_type() != "application/json":
            raise StoreError(415, "Use application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise StoreError(400, "Invalid content length")
        if length <= 0 or length > maximum:
            raise StoreError(413, f"JSON request must be between 1 and {maximum} bytes")
        try:
            body = self.rfile.read(length)
            self._body_consumed = True
            payload = strict_json(body)
        except (ValueError, UnicodeDecodeError):
            raise StoreError(400, "Malformed JSON, duplicate keys or non-finite values")
        if not isinstance(payload, dict):
            raise StoreError(400, "JSON body must be an object")
        return payload

    def error_response(self, status, message):
        # Closing a Windows socket with an unread POST body can reset the
        # connection before the client receives its 4xx response. Drain only a
        # bounded, declared small body, without giving rejected requests a long wait.
        if self.command == "POST" and not getattr(self, "_body_consumed", False):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if 0 < length <= 65536 and not self.headers.get("Transfer-Encoding"):
                    deadline = time.monotonic() + .5
                    while length:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        self.connection.settimeout(remaining)
                        chunk = self.rfile.read1(min(length, 8192))
                        if not chunk:
                            break
                        length -= len(chunk)
            except (ValueError, OSError):
                pass
            finally:
                self.connection.settimeout(15)
        try:
            self.json_response(status, {"error": message})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def dispatch(self, method):
        self._body_consumed = False
        try:
            self.check_request()
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            if method == "GET":
                self.get(path, parse_qs(url.query))
            else:
                self.post(path, self.read_json(reports.MAX_BODY_BYTES if path == '/api/reports/extract' else 65536))
        except StoreError as error:
            self.error_response(error.status, error.message)
        except sqlite3.Error:
            self.error_response(503, "Storage is unavailable. Receipt or changes cannot be confirmed. Emergency guidance remains independent.")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            self.error_response(500, "The request could not be completed. No successful save or notification is implied.")

    def get(self, path, query):
        if path == '/api/reports/status':
            return self.json_response(200, reports.status())
        if path == "/api/health":
            with self.server.store.connect() as db:
                db.execute("SELECT 1").fetchone()
            return self.json_response(200, {"status": "ok", "synthetic_only": True})
        if path == "/api/config":
            return self.json_response(200, config.public_config())
        if path == "/api/ai/status":
            return self.json_response(200, assessors.local_status())
        if path == "/api/session":
            return self.json_response(200, {"user": self.user()})
        if path == "/api/fixtures":
            fixtures = json.loads((ROOT / "fixtures/synthetic-cases.json").read_text(encoding="utf-8"))
            return self.json_response(200, {"cases": fixtures["cases"]})
        if path == "/api/queue":
            self.user(required=True)
            self.server.store.sweep()
            return self.json_response(200, {"requests": self.server.store.queue()})
        parts = path.split("/")
        if len(parts) in {4, 5} and parts[1:3] == ["api", "requests"]:
            rid = parts[3]
            if len(parts) == 5 and parts[4] == "audit":
                self.user(required=True)
                return self.json_response(200, {"events": self.server.store.audit(rid)})
            if len(parts) == 4:
                staff = self.user()
                item = self.server.store.get(rid, query.get("receipt", [None])[0], staff=bool(staff))
                return self.json_response(200, {"request": item})
        if path.startswith("/api/"):
            raise StoreError(404, "Endpoint not found")
        self.static(path)

    def post(self, path, payload):
        if path == '/api/reports/extract':
            result = reports.extract(payload)
            token = self.server.store.save_report(result)
            return self.json_response(200, {'report_id': token, 'report': result})
        if path == "/api/login":
            username, password = payload.get("username"), payload.get("password")
            entry = USERS.get(username) if isinstance(username, str) else None
            if not entry or not isinstance(password, str) or not secrets.compare_digest(entry[0], password):
                raise StoreError(401, "Invalid demonstration credentials")
            token = self.server.store.session_create(username, entry[1])
            return self.json_response(200, {"user": {"username": username, "role": entry[1]}},
                                      f"clinic_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=14400")
        if path == "/api/logout":
            self.server.store.session_delete(self.cookie_token())
            return self.json_response(200, {"user": None}, "clinic_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        if path == "/api/requests":
            cleaned = validate_submission(payload)
            if payload.get('report_id') is not None:
                if payload.get('report_reviewed') is not True:
                    raise StoreError(422, 'Review the report extraction before attaching it to an intake request.')
                cleaned['report_extraction'] = self.server.store.get_report(payload['report_id'])
            key = self.headers.get("Idempotency-Key")
            if not key or len(key) > 200:
                raise StoreError(422, "An Idempotency-Key header is required")
            local_decision = policy.decide(cleaned["inputs"], variant="no_ai")
            local_decision = retain_reported_guidance(local_decision, cleaned["client_events"])
            immediate = local_decision if local_decision["route"] == "emergency_guidance" else None
            item, receipt, fresh = self.server.store.create(cleaned, key, immediate)
            if fresh:
                self.server.assess_request(item)
            public_item = self.server.store.present(item, False)
            public_item["receipt_token"] = receipt
            return self.json_response(201 if fresh else 200, {"request": public_item, "receipt_token": receipt, "created": fresh})
        parts = path.split("/")
        if len(parts) == 5 and parts[1:3] == ["api", "requests"]:
            user = self.user(required=True)
            rid, action = parts[3], parts[4]
            if action == "revisions":
                validate_inputs(payload.get("inputs"))
                local_decision = policy.decide(payload["inputs"], variant="no_ai")
                immediate = local_decision if local_decision["route"] == "emergency_guidance" else None
                item = self.server.store.revise(rid, payload, user, immediate)
                self.server.assess_request(item)
            else:
                item = self.server.store.mutate(rid, action, payload, user)
            return self.json_response(200, {"request": item})
        raise StoreError(404, "Endpoint not found")

    def static(self, path):
        name = "index.html" if path in {"/", "/intake", "/staff"} else unquote(path).lstrip("/")
        base = (ROOT / "static").resolve()
        target = (base / name).resolve()
        if base not in target.parents or not target.is_file() or target.suffix not in {".html", ".js", ".css", ".svg", ".png", ".ico", ".pdf", ".txt"}:
            raise StoreError(404, "Page not found")
        body = target.read_bytes()
        self.send_response(200)
        self.common_headers()
        self.send_header("Content-Type", (mimetypes.guess_type(str(target))[0] or "application/octet-stream") + ("; charset=utf-8" if target.suffix in {".html", ".js", ".css", ".svg"} else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(port=8080, db_path="var/clinic.db", fail_saves=False, coverage=None):
    if coverage is None:
        cfg = config.public_config().get("coverage", {})
        coverage = {"available": bool(cfg.get("open", True) and cfg.get("reviewer_available", True)),
                    "reason": cfg.get("description", "Simulated staffing"), "simulated": True,
                    "clinic_timezone": cfg.get("clinic_timezone", "UTC"),
                    "alternate_contact": "Not configured: synthetic demonstration only"}
    return ClinicServer(("127.0.0.1", port), Store(db_path, fail_saves=fail_saves, coverage=coverage))


def main():
    parser = argparse.ArgumentParser(description="Synthetic clinic demonstration, local use only")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", default="var/clinic.db")
    parser.add_argument("--test-mode", action="store_true", help="Permit explicit persistence failure injection for tests")
    args = parser.parse_args()
    fail = args.test_mode and os.environ.get("CLINIC_TEST_FAIL_SAVES") == "1"
    service = make_server(args.port, args.db, fail)
    print(f"Synthetic clinic server listening on loopback port {service.server_port}. No real patient data. Demo staff: reviewer / demo-reviewer; supervisor / demo-supervisor.", flush=True)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.server_close()


if __name__ == "__main__":
    main()
