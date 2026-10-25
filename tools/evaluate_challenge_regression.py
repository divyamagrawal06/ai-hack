#!/usr/bin/env python3
"""Re-run a disclosed challenge while preserving its first frozen evaluation.

This is a development regression, never a new blind/held-out evaluation. The
dataset bytes and authored labels remain unchanged. Source changes are recorded,
and every authored reference route must still agree with the current demo policy.
Default: validation only, with zero model calls. Add --execute for actual local
inference. All runs receive retained archives; only the disclosed latest changes.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluate_blind_challenge import canonical_hash, save_report, sha256, source_hashes


def validate_disclosed_set(dataset_path, freeze_path, first_path):
    from clinic.policy import decide, validate_assessment
    from clinic.server import validate_inputs

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    first = json.loads(first_path.read_text(encoding="utf-8"))
    if sha256(dataset_path) != freeze["sha256"]:
        raise ValueError("The challenge bytes or authored labels changed after their freeze")
    if first.get("state") != "complete" or first.get("dataset_sha256") != freeze["sha256"]:
        raise ValueError("A completed original frozen report for this exact dataset is required")
    cases = dataset["cases"]
    if (len(cases) != freeze["case_count"] or dataset["authored_case_count"] != freeze["case_count"]
            or first["summary"]["completed"] != len(cases)):
        raise ValueError("The disclosed and first blind case counts differ")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate challenge IDs")
    first_rows = {row["id"]: row for row in first["attempts"]}
    for case in cases:
        if case.get("synthetic") is not True:
            raise ValueError("Every challenge input must be explicitly synthetic")
        validate_inputs(case["inputs"])
        original = first_rows.get(case["id"])
        if not original or original["inputs"] != case["inputs"] or original["expected"] != case["expected"]:
            raise ValueError(f"Inputs or labels differ from the first blind run: {case['id']}")
        reference = case["reference_assessment_for_policy_check"]
        if not validate_assessment(reference):
            raise ValueError(f"Authored reference is no longer accepted: {case['id']}")
        route = decide(case["inputs"], assessment=reference, model_status="valid", variant="local_ai")["route"]
        if route != case["expected"]["route"]:
            raise ValueError(f"Current policy changes the authored reference route: {case['id']}")
    return dataset, freeze, first


def field_checks(expected, assessment):
    checks = {}
    for key, value in expected.items():
        if key == "route":
            continue
        field = key.removesuffix("_any_of")
        actual = assessment.get(field)
        if key.endswith("_any_of"):
            matched = actual in value
        elif type(value) is bool:
            matched = type(actual) is bool and actual is value
        else:
            matched = actual == value
        checks[field] = {"expected": value, "actual": actual, "matched": matched}
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "fixtures/blind-challenge-v1.json")
    parser.add_argument("--freeze", type=Path, default=ROOT / "fixtures/blind-challenge-v1.freeze.json")
    parser.add_argument("--first-blind", "--first-frozen", dest="first_blind", type=Path,
                        default=ROOT / "reports/generated/blind-challenge-results.json",
                        help="Original frozen evaluation to preserve, including a targeted fresh check")
    parser.add_argument("--output-prefix", default="challenge-regression",
                        help="Safe filename prefix for the latest disclosed result and its separate run archive")
    parser.add_argument("--adapter-sha256", help="Optionally require an explicitly frozen current adapter hash")
    parser.add_argument("--model-digest", help="Optionally require an explicitly frozen installed model digest")
    parser.add_argument("--prompt-version", help="Optionally require an explicitly frozen current prompt version")
    parser.add_argument("--policy-change-note", help="Required for execution if the policy/config changed since the blind freeze")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dataset_path, freeze_path, first_path = args.dataset.resolve(), args.freeze.resolve(), args.first_blind.resolve()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.output_prefix):
        parser.error("Output prefix must contain only lowercase letters, digits and hyphens, starting with a letter")
    stable = ROOT / "reports/generated" / (args.output_prefix + "-results.json")
    protected = {first_path, ROOT / "reports/generated/blind-challenge-results.json",
                 ROOT / "reports/generated/fresh-temporal-results.json"}
    if stable.resolve() in {path.resolve() for path in protected}:
        parser.error("Disclosed output must not overwrite an original frozen evaluation")
    try:
        dataset, freeze, first = validate_disclosed_set(dataset_path, freeze_path, first_path)
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    if stable.exists():
        try:
            previous = json.loads(stable.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            parser.error(f"Cannot verify the existing output belongs to this dataset: {exc}")
        if previous.get("dataset_sha256") != freeze["sha256"]:
            parser.error("This output prefix belongs to a different dataset; choose a separate --output-prefix")
    initial_hashes = source_hashes()
    from clinic.config import POLICY_VERSION
    original_hashes = first["source_hashes"]
    policy_changed = any(initial_hashes[name] != original_hashes[name]
                         for name in ("clinic/policy.py", "clinic/config.py"))
    if not args.execute:
        print(json.dumps({"mode": "disclosed_regression_dry_run", "case_count": len(dataset["cases"]),
                          "dataset_sha256": freeze["sha256"], "first_frozen_run_id": first["run_id"],
                          "authored_labels_unchanged": True, "reference_routes_still_match": True,
                          "dataset_policy_version": dataset["policy_version"],
                          "current_policy_version": POLICY_VERSION,
                          "output_prefix": args.output_prefix,
                          "policy_or_config_changed_since_blind": policy_changed, "model_calls": 0}, indent=2))
        return 0
    if policy_changed and not (args.policy_change_note or "").strip():
        parser.error("Provide --policy-change-note describing the explicit changes since the first blind policy")
    if args.adapter_sha256 and initial_hashes["clinic/assessors.py"] != args.adapter_sha256:
        parser.error("Current adapter differs from the developer-supplied freeze hash")

    from clinic.assessors import assess, local_status, LOCAL_PROMPT_VERSION
    from clinic.policy import decide, validate_assessment

    if args.prompt_version and LOCAL_PROMPT_VERSION != args.prompt_version:
        parser.error("Current prompt version differs from the developer-supplied freeze")
    runtime = local_status()
    if not runtime["available"] or (args.model_digest and runtime.get("digest") != args.model_digest):
        parser.error("The required local model is unavailable or has a different digest")
    model_digest = runtime.get("digest")
    prompt_version = LOCAL_PROMPT_VERSION
    first_file_hash = sha256(first_path)
    first_semantic_hash = canonical_hash(first)
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ")
    archive = stable.parent / (args.output_prefix + "-runs") / (run_id + ".json")
    if archive.exists():
        parser.error("Run archive unexpectedly exists; existing raw runs are never overwritten")
    report = {
        "evaluation": "disclosed_development_regression", "previously_disclosed": True,
        "output_prefix": args.output_prefix,
        "is_new_blind_evaluation": False, "run_id": run_id, "started_at": started.isoformat(),
        "state": "running", "planned_attempts": len(dataset["cases"]),
        "dataset_file": dataset_path.name, "dataset_sha256": freeze["sha256"],
        "dataset_frozen_at": freeze["frozen_at"], "dataset_freeze": freeze,
        "authored_labels_unchanged": True, "reference_routes_still_match": True,
        "first_frozen_reference": {
            "path": "reports/generated/" + first_path.name, "run_id": first["run_id"],
            "evaluation_kind": first.get("evaluation"),
            "sha256": first_semantic_hash,
            "hash_basis": "Canonical JSON: UTF-8, sorted keys, compact separators, ensure_ascii=True; independent of checkout line endings.",
            "summary": first["summary"],
        },
        "policy_evolution": {
            "changed_since_blind": policy_changed, "reason": args.policy_change_note or "No policy/config change.",
            "original_policy_version": first["policy_version"], "current_policy_version": POLICY_VERSION,
            "original_policy_sha256": original_hashes["clinic/policy.py"],
            "current_policy_sha256": initial_hashes["clinic/policy.py"],
            "original_config_sha256": original_hashes["clinic/config.py"],
            "current_config_sha256": initial_hashes["clinic/config.py"],
        },
        "model_digest": model_digest, "prompt_version": prompt_version, "source_hashes": initial_hashes,
        "pipeline_sha256": canonical_hash(initial_hashes), "evaluator_sha256": sha256(Path(__file__)),
        "shared_summary_helper_sha256": sha256(ROOT / "tools/evaluate_blind_challenge.py"),
        "runtime": runtime, "policy_version": POLICY_VERSION,
        "dataset_policy_version": dataset["policy_version"],
        "case_plan": [{"id": case["id"], "family": case["family"]} for case in dataset["cases"]],
        "authoring_provenance": dataset["authoring_provenance"],
        "authoring_clarification": "Cases and policy labels were authored by an AI assistant. The candidate local model was not queried during authoring. These are not human-authored or clinician-labelled ground truth.",
        "limitations": ["The developers already know this challenge and may have used its failures to improve the pipeline.",
                        "This run is a disclosed development regression, not an independent blind score.",
                        "The first frozen evaluation is referenced without being replaced or revised.",
                        "Dataset bytes and authored labels are unchanged; every reference route was rechecked against current policy.",
                        "Authored synthetic demo labels are not clinical ground truth or a guarantee of universal accuracy.",
                        "Provider failures remain in the denominator, with every returned raw attempt retained."],
        "attempts": [],
    }
    if first.get("evaluation") == "independently_authored_blind_synthetic_challenge":
        report["first_blind_reference"] = report["first_frozen_reference"]
    save_report(report, stable, archive)
    try:
        for case in dataset["cases"]:
            if source_hashes() != initial_hashes:
                raise RuntimeError("Pipeline source changed during the disclosed regression")
            if sha256(first_path) != first_file_hash or sha256(dataset_path) != freeze["sha256"]:
                raise RuntimeError("The immutable blind result or dataset changed during regression")
            started_case = time.monotonic()
            try:
                attempt = assess(copy.deepcopy(case["inputs"]), "local_ai")
                if not isinstance(attempt, dict):
                    raise TypeError("Adapter returned a non-object result")
            except Exception as exc:
                attempt = {"assessment": None, "model_status": "evaluation_exception", "mode": "degraded",
                           "error": {"type": type(exc).__name__, "message": str(exc)}, "raw_output": None,
                           "raw_output_unavailable": "Adapter raised before returning its captured response."}
            decision = decide(case["inputs"], assessment=attempt.get("assessment"),
                              model_status=attempt.get("model_status"), variant="local_ai")
            assessment = attempt.get("assessment")
            checks = field_checks(case["expected"], assessment if isinstance(assessment, dict) else {})
            valid = (attempt.get("mode") == "live_model" and attempt.get("model_status") == "valid"
                     and attempt.get("local") is True and attempt.get("model_digest") == model_digest
                     and attempt.get("prompt_version") == prompt_version and validate_assessment(assessment))
            route_matched = decision["route"] == case["expected"]["route"]
            row = {"id": case["id"], "family": case["family"], "title": case["title"],
                   "inputs": case["inputs"], "expected": case["expected"], "policy_rationale": case["policy_rationale"],
                   "elapsed_seconds": round(time.monotonic() - started_case, 3), "valid_inference": valid,
                   "route_matched": route_matched, "field_checks": checks,
                   "strict_match": valid and route_matched and all(check["matched"] for check in checks.values()),
                   "attempt": attempt, "decision": decision}
            report["attempts"].append(row)
            save_report(report, stable, archive)
            print(f"{case['id']}: {'MATCH' if route_matched else 'MISMATCH'}; valid_inference={valid}; "
                  f"strict_match={row['strict_match']}; {row['elapsed_seconds']:.1f}s", flush=True)
        if source_hashes() != initial_hashes or sha256(first_path) != first_file_hash:
            raise RuntimeError("Frozen pipeline or original blind result changed before regression completion")
        report["state"] = "complete"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["source_hashes_after"] = source_hashes()
        report["first_frozen_report_unchanged"] = True
        if "first_blind_reference" in report:
            report["first_blind_report_unchanged"] = True
    except BaseException as exc:
        report["state"] = "interrupted"
        report["interruption"] = {"type": type(exc).__name__, "message": str(exc)}
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report(report, stable, archive)
        raise
    save_report(report, stable, archive)
    print(json.dumps(report["summary"], indent=2), flush=True)
    return 0 if report["summary"]["strict_matches"] == report["planned_attempts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
