#!/usr/bin/env python3
"""Run synthetic policy evaluation and authored replay conformance.

No external API calls. Replay numbers are not live-model accuracy. Browser
response timing, reviewer minutes, calibration and clinical safety are unmeasured.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.config import POLICY_VERSION  # noqa: E402
from clinic.policy import decide, detect_local_warning  # noqa: E402

EMERGENCY = "emergency_guidance"
HUMAN = "same_day_human_review"
ROUTINE = "routine_appointment"
KNOWN_LOCAL_CASES = ("FX-06", "FX-07", "FX-08", "FX-09", "FX-27", "FX-29", "FX-38")


def fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def route_metrics(rows):
    """Use explicit synthetic reference labels; preserve failures in denominators."""
    scored = [row for row in rows if row["reference_comparison_included"]]
    emergency = [row for row in scored if row["expected_route"] == EMERGENCY]
    nonroutine = [row for row in scored if row["expected_route"] in {EMERGENCY, HUMAN}]
    routine = [row for row in scored if row["expected_route"] == ROUTINE]
    routine_outputs = [row for row in scored if row.get("actual_route") == ROUTINE]
    emergency_misses = [row["id"] for row in emergency if row.get("actual_route") != EMERGENCY]
    routine_leaks = [row["id"] for row in nonroutine if row.get("actual_route") == ROUTINE]
    escalation = [row["id"] for row in routine if row.get("actual_route") in {EMERGENCY, HUMAN}]
    failures = [row["id"] for row in rows if row.get("error")]
    return {
        "reference_scored_cases": len(scored),
        "reference_excluded_cases": [{"id": row["id"], "reason": row["exclusion_reason"]}
                                     for row in rows if not row["reference_comparison_included"]],
        "emergency_route_miss_rate": fraction(len(emergency_misses), len(emergency)),
        "emergency_route_miss_cases": emergency_misses,
        "incorrect_routine_per_reference_nonroutine": fraction(len(routine_leaks), len(nonroutine)),
        "incorrect_routine_per_routine_suggestion": fraction(len(routine_leaks), len(routine_outputs)),
        "incorrect_routine_cases": routine_leaks,
        "unnecessary_escalation_per_reference_routine": fraction(len(escalation), len(routine)),
        "unnecessary_escalation_cases": escalation,
        "observed_route_counts": dict(Counter(row.get("actual_route") or "no_output" for row in rows)),
        "execution_failures": {"count": len(failures), "case_ids": failures},
        "same_day_review_suggestions": sum(row.get("actual_route") == HUMAN for row in rows),
        "nonemergency_saved_requests_requiring_staff_review": sum(
            row.get("actual_route") in {ROUTINE, HUMAN} and row["save_state"] == "succeeded" for row in rows),
        "reviewer_minutes": None,
        "emergency_guidance_ui_latency_ms": None,
        "calibration": None,
        "scope_note": "Rule outputs against authored synthetic expectations; no clinical gold standard, UI timing or human-workload study.",
    }


def evaluate_baseline(cases):
    rows = []
    no_decision = []
    for case in cases:
        if case["expected"]["route"] is None:
            no_decision.append({"id": case["id"], "reason": "Initial ordinary save fails; no decision/model call is permitted. Persistence/API test required."})
            continue
        # AI-failure cases encode a failure-specific action, not an independently
        # adjudicated clinical label that can fairly score a no-AI baseline.
        failure_only_label = case["expected"]["primary_rule"] == "H04"
        direct_output_only_label = case["variant"] == "direct_replay" and case["expected"]["primary_rule"] == "H05"
        excluded = failure_only_label or direct_output_only_label
        row = {"id": case["id"], "expected_route": case["expected"]["route"],
               "expected_primary_rule": case["expected"]["primary_rule"],
               "reference_comparison_included": not excluded,
               "exclusion_reason": ("Reference action is AI-only failure fallback, with no independent clinical label." if failure_only_label else
                                    "Reference action follows an authored direct-model output, not an independently adjudicated input disposition." if direct_output_only_label else None),
               "save_state": case["operations"]["save"]}
        try:
            result = decide(copy.deepcopy(case["inputs"]), variant="no_ai", model_status="not_called")
            row.update(actual_route=result["route"], actual_primary_rule=result["primary_rule"],
                       local_signal=result.get("local_signal"), matched_rules=result["matched_rules"],
                       information_sufficiency=result["information_sufficiency"], error=None)
        except Exception as exc:
            row.update(actual_route=None, actual_primary_rule=None, error=type(exc).__name__ + ": " + str(exc))
        rows.append(row)
    return {"mode": "no_ai", "evidence_kind": "executed_local_policy_behavior",
            "baseline_decision_policy": "Unreviewed ordinary narratives defer to human review via H05; no-AI cannot affirm narrative sufficiency.",
            "attempted_policy_cases": len(rows), "no_decision_cases": no_decision,
            "metrics": route_metrics(rows), "cases": rows}


def evaluate_replay(cases, variant):
    rows = []
    for case in cases:
        if case["variant"] != variant or case["expected"]["route"] is None:
            continue
        row = {"id": case["id"], "expected_route": case["expected"]["route"],
               "expected_primary_rule": case["expected"]["primary_rule"],
               "reference_comparison_included": True, "exclusion_reason": None,
               "save_state": case["operations"]["save"],
               "authored_model_status": case["operations"]["model_status"],
               "original_timing_requirement": case["expected"]["emergency_timing_requirement"],
               "raw_authored_direct_choice": (case["assessment_stub"] or {}).get("direct_route") if variant == "direct_replay" else None}
        try:
            result = decide(copy.deepcopy(case["inputs"]), copy.deepcopy(case["assessment_stub"]),
                            model_status=case["operations"]["model_status"], variant=variant,
                            local_signal=case["local_signal"])
            match = result["route"] == row["expected_route"] and result["primary_rule"] == row["expected_primary_rule"]
            row.update(actual_route=result["route"], actual_primary_rule=result["primary_rule"],
                       matched_rules=result["matched_rules"], conformance_pass=match, error=None)
        except Exception as exc:
            row.update(actual_route=None, actual_primary_rule=None, conformance_pass=False,
                       error=type(exc).__name__ + ": " + str(exc))
        rows.append(row)
    return {"mode": "replay", "variant": variant, "evidence_kind": "AUTHORED_STUB_RULE_CONFORMANCE_NOT_MODEL_PERFORMANCE",
            "executed_cases": len(rows), "conformance_passed": sum(row["conformance_pass"] for row in rows),
            "conformance_failed": sum(not row["conformance_pass"] for row in rows),
            "metrics_interpretation": "These counts only describe rule behavior on authored stubs. They are not Jev accuracy, calibration, latency or a fair cross-arm ranking.",
            "metrics": route_metrics(rows), "cases": rows}


def evaluate_local_guard(cases):
    by_id = {case["id"]: case for case in cases}
    rows = []
    for case_id in KNOWN_LOCAL_CASES:
        case = by_id[case_id]
        try:
            signal = detect_local_warning(case["inputs"]["symptom_text"])
            result = decide(copy.deepcopy(case["inputs"]), variant="no_ai", model_status="not_called")
            passed = signal in {"current_explicit_demo_warning", "current_possible_demo_warning"} and result["route"] == EMERGENCY
            rows.append({"id": case_id, "local_signal": signal, "route": result["route"],
                         "pass": passed, "previous_model_dependency_gap": case_id in {"FX-08", "FX-09", "FX-38"}})
        except Exception as exc:
            rows.append({"id": case_id, "pass": False, "error": type(exc).__name__ + ": " + str(exc)})
    return {"executed_cases": len(rows), "passed": sum(row["pass"] for row in rows),
            "failed": sum(not row["pass"] for row in rows), "cases": rows,
            "claim_limit": "Checks bounded Python text recognition before any model call. Browser event order and offline display need separate UI tests. No universal emergency-text detection claim."}


def format_fraction(value):
    if value["denominator"] == 0:
        return "not applicable (0 denominator)"
    return f"{value['numerator']}/{value['denominator']} ({value['rate']:.1%})"


def markdown_report(report):
    base = report["no_ai"]; metrics = base["metrics"]
    lines = ["# Synthetic policy evaluation", "", f"Run: `{report['run_id']}`. Policy: `{report['policy_version']}`. Fixture source: `{report['fixture_policy_version']}`.", "",
             "**Executed local policy behavior and authored replay conformance only. No live Jev/LLM calls, clinical evaluation, probability calibration, reviewer-minute measurement, or browser-timing claim.**", "",
             "## Measured no-AI policy behavior", "",
             f"Executed {base['attempted_policy_cases']} policy calls; {metrics['reference_scored_cases']} have comparable authored route expectations. Initial failed save FX-31 is excluded because the application must not derive a decision. FX-19–21 are excluded from reference scoring because their expected fallback is specific to an AI outage. FX-22–23 are also excluded because their human-review labels follow authored direct-model outputs on otherwise routine input, not independent reference dispositions. All five remain visible in case-level outputs.", "",
             "| Measure | Result |", "|---|---|",
             f"| Emergency route misses | {format_fraction(metrics['emergency_route_miss_rate'])} |",
             f"| Incorrect routine / reference non-routine | {format_fraction(metrics['incorrect_routine_per_reference_nonroutine'])} |",
             f"| Incorrect routine / routine suggestions | {format_fraction(metrics['incorrect_routine_per_routine_suggestion'])} |",
             f"| Unnecessary escalation / reference routine | {format_fraction(metrics['unnecessary_escalation_per_reference_routine'])} |",
             f"| Same-day review suggestions (all policy calls) | {metrics['same_day_review_suggestions']} |",
             f"| Saved non-emergency requests still needing staff review | {metrics['nonemergency_saved_requests_requiring_staff_review']} |",
             f"| Policy execution errors | {metrics['execution_failures']['count']} |",
             "| Reviewer minutes, UI guidance latency, calibration | Not measured |", "",
             "Incorrect routine cases: " + (", ".join(metrics["incorrect_routine_cases"]) or "none") + ".",
             "Emergency route miss cases: " + (", ".join(metrics["emergency_route_miss_cases"]) or "none") + ".", "",
             "The current no-AI arm does not affirm narrative sufficiency: every ordinary unreviewed narrative goes to human review (H05 unless a higher rule applies). This eliminates the observed routine-suggestion failures by increasing review escalation, including for reference routine cases. It does not demonstrate a winning model or measured workload savings.", "",
             "Reference labels are authored demonstration expectations, not clinician-adjudicated gold labels. The initial structured-only baseline is preserved at reports/iterations/initial-structured-baseline.json and .md: under policy0.2 it produced five incorrect routine suggestions among the 32 non-routine references. The current reviewer-gated policy is versioned separately; fixture labels were not changed to obtain passing outcomes.", "",
             "## Replay conformance — not live model performance", "", "| Authored replay arm | Cases | Passed | Failed |", "|---|---:|---:|---:|"]
    for arm in report["replay"]:
        lines.append(f"| {arm['variant']} | {arm['executed_cases']} | {arm['conformance_passed']} | {arm['conformance_failed']} |")
    guard = report["local_guard"]
    lines += ["", "The arms use different explicitly authored fixture subsets. Do not rank model candidates using these numbers. Direct stubs are finite choices, not sampled Jev predictions; decomposed stubs are supplied assertions, not measured detection results. AI failure states are injected metadata, not observed provider outages.", "",
              "## Independent bounded warning check", "", f"{guard['passed']}/{guard['executed_cases']} known warning descriptions produced an emergency route without a model. FX-08, FX-09 and FX-38 retain their historical model-dependent fixture labels; the current detector addresses these exact descriptions independently. This does not show that arbitrary emergencies are recognized or that browser guidance appeared on time.", "",
              "## Unrun work", "", "Live direct Jev, live decomposed Jev, and live structured-output LLM comparisons are not run by this tool. Calibration, blinded staff/user workflow evaluation, capacity under load, and clinical/jurisdiction approval remain separate. Persistence, event timing and concurrent overrides require the API/browser test results rather than this policy report.", "",
              "See `evaluation.json` for case-level outputs, exclusions, failure metadata, fixture hash, and denominators.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "fixtures" / "synthetic-cases.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "generated")
    args = parser.parse_args()
    raw = args.fixtures.read_bytes()
    fixture_set = json.loads(raw)
    if fixture_set.get("contains_real_patient_data") is not False or any(case.get("synthetic") is not True for case in fixture_set["cases"]):
        parser.error("Evaluation accepts explicitly synthetic fixtures only.")
    timestamp = datetime.now(timezone.utc)
    report = {"run_id": timestamp.strftime("policy-eval-%Y%m%dT%H%M%S.%fZ"),
              "created_at": timestamp.isoformat(), "policy_version": POLICY_VERSION,
              "fixture_policy_version": fixture_set["policy_version"],
              "fixture_set_version": fixture_set["fixture_set_version"],
              "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "live_model_calls": 0, "clinical_validation": False,
              "no_ai": evaluate_baseline(fixture_set["cases"]),
              "replay": [evaluate_replay(fixture_set["cases"], variant) for variant in ("direct_replay", "decomposed_replay")],
              "local_guard": evaluate_local_guard(fixture_set["cases"]),
              "unrun_arms": ["live_direct_jev", "live_decomposed_jev", "live_structured_output_llm"]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "evaluation.md").write_text(markdown_report(report))
    print(f"Wrote {args.output_dir / 'evaluation.json'} and {args.output_dir / 'evaluation.md'}")
    print(f"No-AI comparable cases: {report['no_ai']['metrics']['reference_scored_cases']}; live model calls: 0")
    failed = (sum(arm["conformance_failed"] for arm in report["replay"])
              + report["local_guard"]["failed"] + report["no_ai"]["metrics"]["execution_failures"]["count"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
