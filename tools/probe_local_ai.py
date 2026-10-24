#!/usr/bin/env python3
"""Run eight visible, invented semantic probes against actual local inference.

Default: show the plan without inference. Add --execute after starting local AI.
No mocks, fixture replays, credentials, or cloud calls are used. The latest JSON
and an immutable run archive retain every actual attempt, including failures.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.assessors import assess, local_status
from clinic.config import POLICY_VERSION, local_model
from clinic.policy import decide, detect_local_warning
from clinic.server import validate_inputs


def evidence_matches_original(inputs, result):
    """Independent round-trip check on the adapter's selected Unicode spans."""
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        return False
    text = inputs["symptom_text"]
    for span in evidence:
        if not isinstance(span, dict):
            return False
        start, end, quote = span.get("start"), span.get("end"), span.get("quote")
        if (type(start) is not int or type(end) is not int or not isinstance(quote, str)
                or not 0 <= start < end <= len(text) or text[start:end] != quote):
            return False
    return result.get("summary", "") == " … ".join(span["quote"] for span in evidence)


def evaluate_case(case, repeat):
    started = time.monotonic()
    attempt = assess(case["inputs"], "local_ai")
    decision = decide(case["inputs"], assessment=attempt.get("assessment"),
                      model_status=attempt["model_status"], variant="local_ai")
    baseline = decide(case["inputs"], variant="no_ai")
    fields, expected = attempt.get("assessment") or {}, case["expected"]
    checks = {
        "live_inference_valid": attempt.get("mode") == "live_model" and attempt.get("model_status") == "valid" and attempt.get("local") is True,
        "route_matches": decision["route"] == expected["route"],
        "evidence_exact": evidence_matches_original(case["inputs"], attempt),
        "evidence_present": bool(attempt.get("evidence")),
    }
    for field in ("warning", "intent"):
        if field in expected:
            checks[field + "_matches"] = fields.get(field) in expected[field]
    if "local_signal" in expected:
        checks["local_signal_matches"] = decision["local_signal"] == expected["local_signal"]
    return {
        "id": case["id"], "title": case["title"], "repeat": repeat,
        "inputs": case["inputs"], "expected": expected,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "checks": checks, "passed": all(checks.values()),
        "no_ai_route": baseline["route"], "local_signal": decision["local_signal"],
        "model_dependent_emergency": decision["route"] == "emergency_guidance" and baseline["route"] != "emergency_guidance",
        "attempt": attempt, "decision": decision,
    }


def save_report(report, path, archive):
    report["completed_attempts"] = len(report["attempts"])
    report["passed_attempts"] = sum(row["passed"] for row in report["attempts"])
    report["valid_inferences"] = sum(row["checks"]["live_inference_valid"] for row in report["attempts"])
    report["evidence_exact_attempts"] = sum(row["checks"]["evidence_exact"] for row in report["attempts"])
    report["failed_case_ids"] = sorted({row["id"] for row in report["attempts"] if not row["passed"]})
    report["model_versions"] = sorted({row["attempt"]["model_version"] for row in report["attempts"] if row["attempt"].get("model_version")})
    report["prompt_versions"] = sorted({row["attempt"]["prompt_version"] for row in report["attempts"] if row["attempt"].get("prompt_version")})
    encoded = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    for target in (archive, path):
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run actual local inference; no cloud API calls")
    parser.add_argument("--case", action="append", dest="case_ids", help="Limit to selected LP IDs; may be repeated")
    parser.add_argument("--repeats", type=int, default=1, help="Actual inference repetitions per case, from 1 to 5")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/generated/local-probes.json")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5:
        parser.error("--repeats must be from 1 to 5")
    data = (ROOT / "fixtures/local-ai-probes.json").read_bytes()
    fixture = json.loads(data)
    all_cases = fixture["cases"]
    if args.case_ids and set(args.case_ids) - {case["id"] for case in all_cases}:
        parser.error("Unknown probe ID; inspect fixtures/local-ai-probes.json")
    cases = [case for case in all_cases if not args.case_ids or case["id"] in args.case_ids]
    for case in cases:
        if case.get("synthetic") is not True:
            parser.error("Every probe must be explicitly synthetic")
        validate_inputs(case["inputs"])
        if "local_signal" in case["expected"] and detect_local_warning(case["inputs"]["symptom_text"]) != case["expected"]["local_signal"]:
            parser.error("The paraphrase no longer tests a model-only warning; review the probe after guard changes")
    plan = {"mode": "local_live" if args.execute else "dry_run", "model": local_model(),
            "case_ids": [case["id"] for case in cases], "repeats": args.repeats,
            "planned_attempts": len(cases) * args.repeats, "fixture_sha256": hashlib.sha256(data).hexdigest(),
            "policy_version": POLICY_VERSION, "synthetic_only": True,
            "limitations": fixture["limitations"]}
    if not args.execute:
        print(json.dumps(plan, indent=2))
        print("No inference performed. Add --execute to run these visible development probes.")
        return 0
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ")
    path = args.output.resolve()
    archive = path.parent / "local-probe-runs" / (run_id + ".json")
    status = local_status()
    report = {**plan, "run_id": run_id, "started_at": started.isoformat(), "runtime": status,
              "state": "running", "attempts": [], "archive_path": str(archive.relative_to(path.parent)),
              "notes": ["No clinical performance claim.", "No mock or replay outputs are used.",
                        "Model-dependent warnings remain a pre-inference timing gap.",
                        "Provider failures and malformed output remain in the denominator.",
                        "This runner tests inference and routing, not UI, persistence, or staffing."]}
    if not status["available"]:
        report["state"] = "unavailable"
        save_report(report, path, archive)
        print(status["message"])
        return 2
    try:
        for repeat in range(1, args.repeats + 1):
            for case in cases:
                row = evaluate_case(case, repeat)
                report["attempts"].append(row)
                save_report(report, path, archive)
                print(f"{case['id']} [{repeat}] {'PASS' if row['passed'] else 'FAIL'}: {row['decision']['route']} "
                      f"({row['attempt']['model_status']}, {row['elapsed_seconds']:.1f}s)", flush=True)
        report["state"] = "complete"
    except KeyboardInterrupt:
        report["state"] = "interrupted"
    except Exception as error:
        report["state"] = "failed"
        report["runner_error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report(report, path, archive)
    print(f"{report['passed_attempts']}/{report['planned_attempts']} passed; actual attempts saved to {path}")
    return 0 if report["state"] == "complete" and report["passed_attempts"] == report["planned_attempts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
