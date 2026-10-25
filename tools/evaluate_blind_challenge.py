#!/usr/bin/env python3
"""Evaluate a pre-frozen authored challenge once against a frozen local adapter.

The default only validates the frozen files; it makes no model calls. Execution
requires the developer's adapter hash and model digest. Every planned case stays
in the denominator, including provider failures, and every raw attempt is saved.
This is an independently authored synthetic challenge, not clinical ground truth.
"""
from __future__ import annotations

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


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    return {name: sha256(ROOT / name) for name in
            ("clinic/assessors.py", "clinic/policy.py", "clinic/config.py")}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_frozen_files(dataset_path, freeze_path):
    from clinic.policy import decide, validate_assessment
    from clinic.server import validate_inputs

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if sha256(dataset_path) != freeze["sha256"]:
        raise ValueError("Challenge contents no longer match the pre-evaluation freeze hash")
    if dataset["authored_case_count"] != freeze["case_count"] or len(dataset["cases"]) != freeze["case_count"]:
        raise ValueError("Frozen challenge case count does not match")
    if len({case["id"] for case in dataset["cases"]}) != len(dataset["cases"]):
        raise ValueError("Duplicate challenge IDs")
    if source_hashes()["clinic/policy.py"] != freeze["policy_source_sha256"]:
        raise ValueError("Demo policy changed after challenge freeze; do not silently relabel the challenge")
    if source_hashes()["clinic/config.py"] != freeze["config_source_sha256"]:
        raise ValueError("Demo config changed after challenge freeze; review the freeze before execution")
    for case in dataset["cases"]:
        if case.get("synthetic") is not True:
            raise ValueError("Every challenge input must be explicitly synthetic")
        validate_inputs(case["inputs"])
        reference = case["reference_assessment_for_policy_check"]
        if not validate_assessment(reference):
            raise ValueError(f"Invalid authored reference assessment: {case['id']}")
        route = decide(case["inputs"], assessment=reference, model_status="valid", variant="local_ai")["route"]
        if route != case["expected"]["route"]:
            raise ValueError(f"Authored reference route disagrees with frozen policy: {case['id']}")
    return dataset, freeze


def update_summary(report):
    records = report["attempts"]
    families = sorted({case["family"] for case in report["case_plan"]})
    semantic_mismatches = []
    for row in records:
        for field, check in row["field_checks"].items():
            if not check["matched"]:
                semantic_mismatches.append({"id": row["id"], "field": field,
                                            "expected": check["expected"], "actual": check["actual"]})
    report["summary"] = {
        "matched": sum(row["route_matched"] for row in records),
        "total": report["planned_attempts"],
        "completed": len(records),
        "valid_inferences": sum(row["valid_inference"] for row in records),
        "strict_matches": sum(row["strict_match"] for row in records),
        "mismatches": [{"id": row["id"], "expected": row["expected"]["route"],
                        "actual": row["decision"]["route"]} for row in records if not row["route_matched"]],
        "invalid_inference_ids": [row["id"] for row in records if not row["valid_inference"]],
        "semantic_mismatches": semantic_mismatches,
        "pending_ids": [case["id"] for case in report["case_plan"]
                        if case["id"] not in {row["id"] for row in records}],
        "per_family": {family: {
            "total": sum(case["family"] == family for case in report["case_plan"]),
            "completed": sum(row["family"] == family for row in records),
            "matched": sum(row["family"] == family and row["route_matched"] for row in records),
            "valid_inferences": sum(row["family"] == family and row["valid_inference"] for row in records),
            "strict_matches": sum(row["family"] == family and row["strict_match"] for row in records),
        } for family in families},
    }
    report["observed_model_versions"] = sorted({row["attempt"].get("model_version") for row in records
                                                if row["attempt"].get("model_version")})
    report["observed_prompt_versions"] = sorted({row["attempt"].get("prompt_version") for row in records
                                                 if row["attempt"].get("prompt_version")})
    report["observed_prompt_hashes"] = sorted({row["attempt"].get("questions_hash") for row in records
                                               if row["attempt"].get("questions_hash")})


def save_report(report, stable, archive):
    update_summary(report)
    encoded = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    for target in (archive, stable):
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--adapter-sha256", help="Final frozen adapter hash supplied by its developer")
    parser.add_argument("--model-digest", help="Installed model manifest digest supplied at model freeze")
    parser.add_argument("--prompt-version", help="Final prompt version supplied by its developer")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dataset_path, freeze_path = args.dataset.resolve(), args.freeze.resolve()
    try:
        dataset, freeze = validate_frozen_files(dataset_path, freeze_path)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    if not args.execute:
        print(json.dumps({"mode": "dry_run", "case_count": len(dataset["cases"]),
                          "family_count": len(dataset["families"]), "sha256": freeze["sha256"],
                          "frozen_at": freeze["frozen_at"], "model_calls": 0}, indent=2))
        return 0
    if not all((args.adapter_sha256, args.model_digest, args.prompt_version)):
        parser.error("Execution requires --adapter-sha256, --model-digest and --prompt-version from the final freeze")
    initial_hashes = source_hashes()
    if initial_hashes["clinic/assessors.py"] != args.adapter_sha256:
        parser.error("Adapter does not match the final developer-supplied freeze hash")

    from clinic.assessors import assess, local_status, LOCAL_PROMPT_VERSION
    from clinic.policy import decide

    if LOCAL_PROMPT_VERSION != args.prompt_version:
        parser.error("Adapter prompt version does not match the final freeze")
    runtime = local_status()
    if not runtime["available"] or runtime.get("digest") != args.model_digest:
        parser.error("The frozen local model is unavailable or has a different digest")
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ")
    stable = ROOT / "reports/generated/blind-challenge-results.json"
    run_directory = stable.parent / "blind-challenge-runs"
    archive = run_directory / (run_id + ".json")
    run_directory.mkdir(parents=True, exist_ok=True)
    marker = run_directory / (freeze["sha256"] + ".started.json")
    try:
        with marker.open("x", encoding="utf-8") as file:
            json.dump({"run_id": run_id, "started_at": started.isoformat(),
                       "dataset_sha256": freeze["sha256"], "adapter_sha256": args.adapter_sha256}, file, indent=2)
    except FileExistsError:
        parser.error("This frozen challenge has already started execution. Do not rerun and call it blind.")
    report = {
        "evaluation": "independently_authored_blind_synthetic_challenge", "run_id": run_id,
        "started_at": started.isoformat(), "state": "running", "planned_attempts": len(dataset["cases"]),
        "dataset_file": dataset_path.name, "dataset_sha256": freeze["sha256"],
        "dataset_frozen_at": freeze["frozen_at"], "dataset_freeze": freeze,
        "model_digest": args.model_digest, "prompt_version": args.prompt_version,
        "source_hashes": initial_hashes, "pipeline_sha256": canonical_hash(initial_hashes),
        "evaluator_sha256": sha256(Path(__file__)),
        "runtime": runtime, "policy_version": dataset["policy_version"],
        "case_plan": [{"id": case["id"], "family": case["family"]} for case in dataset["cases"]],
        "authoring_provenance": dataset["authoring_provenance"],
        "limitations": ["Authored labels implement the fictional demo policy, not clinical ground truth.",
                        "No claim of universal or clinical accuracy follows from this finite synthetic set.",
                        "Failures remain in the denominator; no cases are removed or relabelled after execution.",
                        "The set becomes disclosed development evidence after this first evaluation.",
                        "Route correctness and valid model inference are reported separately.",
                        "Semantic field checks are intentionally stricter than route-only matching."],
        "attempts": [],
    }
    save_report(report, stable, archive)
    try:
        for case in dataset["cases"]:
            if source_hashes() != initial_hashes:
                raise RuntimeError("Pipeline source changed during frozen challenge evaluation")
            started_case = time.monotonic()
            try:
                attempt = assess(case["inputs"], "local_ai")
                if not isinstance(attempt, dict):
                    raise TypeError("Adapter returned a non-object result")
            except Exception as exc:
                # An unexpected provider/adapter exception is still an attempted
                # case. Preserve it and continue; never drop it from the score.
                attempt = {"assessment": None, "model_status": "evaluation_exception", "mode": "degraded",
                           "error": {"type": type(exc).__name__, "message": str(exc)},
                           "raw_output": None, "raw_output_unavailable": "Adapter raised before returning its captured response."}
            decision = decide(case["inputs"], assessment=attempt.get("assessment"),
                              model_status=attempt.get("model_status"), variant="local_ai")
            fields, checks = attempt.get("assessment") or {}, {}
            for expected_key, expected_value in case["expected"].items():
                if expected_key == "route":
                    continue
                field = expected_key.removesuffix("_any_of")
                actual = fields.get(field)
                if expected_key.endswith("_any_of"):
                    matched = actual in expected_value
                elif type(expected_value) is bool:
                    matched = type(actual) is bool and actual is expected_value
                else:
                    matched = actual == expected_value
                checks[field] = {"expected": expected_value, "actual": actual, "matched": matched}
            valid = (attempt.get("mode") == "live_model" and attempt.get("model_status") == "valid"
                     and attempt.get("local") is True and attempt.get("model_digest") == args.model_digest
                     and attempt.get("prompt_version") == args.prompt_version)
            route_matched = decision["route"] == case["expected"]["route"]
            row = {"id": case["id"], "family": case["family"], "title": case["title"],
                   "inputs": case["inputs"], "expected": case["expected"],
                   "policy_rationale": case["policy_rationale"],
                   "elapsed_seconds": round(time.monotonic() - started_case, 3),
                   "valid_inference": valid, "route_matched": route_matched,
                   "field_checks": checks, "strict_match": valid and route_matched and all(c["matched"] for c in checks.values()),
                   "attempt": attempt, "decision": decision}
            report["attempts"].append(row)
            save_report(report, stable, archive)
            print(f"{case['id']}: {'MATCH' if route_matched else 'MISMATCH'}; valid_inference={valid}; "
                  f"strict_match={row['strict_match']}; {row['elapsed_seconds']:.1f}s", flush=True)
        if source_hashes() != initial_hashes:
            raise RuntimeError("Pipeline source changed before evaluation completed")
        report["state"] = "complete"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["source_hashes_after"] = source_hashes()
        # Publication happens only after the single blind evaluation is complete.
        for source in (dataset_path, freeze_path):
            target = ROOT / "fixtures" / source.name
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise RuntimeError("A different published challenge file already exists")
            target.write_bytes(source.read_bytes())
        report["published_fixture_files"] = ["fixtures/" + dataset_path.name, "fixtures/" + freeze_path.name]
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
