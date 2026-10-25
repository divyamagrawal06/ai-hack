#!/usr/bin/env python3
"""Run the once-only targeted fresh temporal check after earlier disclosed failures.

Cases and policy labels are assistant-authored; the candidate local model was not
queried while authoring them. The tuning agent must freeze its pipeline before
seeing their text. This targeted check is not a broad or clinical benchmark.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluate_blind_challenge import canonical_hash, save_report, sha256, source_hashes, validate_frozen_files
from evaluate_challenge_regression import field_checks

AUTHORING_CLARIFICATION = (
    "Cases and policy labels were authored by an AI assistant after earlier disclosed failures. "
    "The candidate local model was not queried during authoring, and the tuning agent had not "
    "seen these texts before its final freeze. These are not human-authored or clinician-labelled ground truth."
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "fixtures/fresh-temporal-v1.json")
    parser.add_argument("--freeze", type=Path, default=ROOT / "fixtures/fresh-temporal-v1.freeze.json")
    parser.add_argument("--adapter-sha256")
    parser.add_argument("--model-digest")
    parser.add_argument("--prompt-version")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dataset_path, freeze_path = args.dataset.resolve(), args.freeze.resolve()
    try:
        dataset, freeze = validate_frozen_files(dataset_path, freeze_path)
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    if not args.execute:
        print(json.dumps({"mode": "targeted_fresh_temporal_dry_run", "case_count": len(dataset["cases"]),
                          "dataset_sha256": freeze["sha256"], "dataset_frozen_at": freeze["frozen_at"],
                          "candidate_local_model_calls": 0, "authoring_clarification": AUTHORING_CLARIFICATION}, indent=2))
        return 0
    if not all((args.adapter_sha256, args.model_digest, args.prompt_version)):
        parser.error("Execution requires the developer's frozen adapter SHA, model digest and prompt version")
    initial_hashes = source_hashes()
    if initial_hashes["clinic/assessors.py"] != args.adapter_sha256:
        parser.error("Adapter does not match the final developer-supplied freeze hash")
    from clinic.assessors import assess, local_status, LOCAL_PROMPT_VERSION
    from clinic.config import POLICY_VERSION
    from clinic.policy import decide, validate_assessment
    if LOCAL_PROMPT_VERSION != args.prompt_version:
        parser.error("Prompt version does not match the developer's final freeze")
    runtime = local_status()
    if not runtime["available"] or runtime.get("digest") != args.model_digest:
        parser.error("The frozen local model is unavailable or has a different digest")
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ")
    stable = ROOT / "reports/generated/fresh-temporal-results.json"
    directory = stable.parent / "fresh-temporal-runs"
    archive = directory / (run_id + ".json")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with (directory / (freeze["sha256"] + ".started.json")).open("x", encoding="utf-8") as file:
            json.dump({"run_id": run_id, "dataset_sha256": freeze["sha256"],
                       "adapter_sha256": args.adapter_sha256, "started_at": started.isoformat()}, file, indent=2)
    except FileExistsError:
        parser.error("This fresh set has already started evaluation; subsequent runs must be labelled disclosed regression")
    report = {
        "evaluation": "targeted_fresh_temporal_check_after_disclosed_failures", "run_id": run_id,
        "started_at": started.isoformat(), "state": "running", "planned_attempts": len(dataset["cases"]),
        "dataset_file": dataset_path.name, "dataset_sha256": freeze["sha256"],
        "dataset_frozen_at": freeze["frozen_at"], "dataset_freeze": freeze,
        "provenance": [AUTHORING_CLARIFICATION, *dataset["authoring_provenance"]],
        "authoring_clarification": AUTHORING_CLARIFICATION,
        "candidate_local_model_queried_during_authoring": False,
        "unseen_by_tuning_agent_until_pipeline_freeze": True,
        "policy_version": POLICY_VERSION, "dataset_policy_version": dataset["policy_version"],
        "model_digest": args.model_digest, "prompt_version": args.prompt_version,
        "source_hashes": initial_hashes, "pipeline_sha256": canonical_hash(initial_hashes),
        "evaluator_sha256": sha256(Path(__file__)),
        "shared_helper_hashes": {name: sha256(ROOT / "tools" / name) for name in
                                 ("evaluate_blind_challenge.py", "evaluate_challenge_regression.py")},
        "runtime": runtime,
        "case_plan": [{"id": case["id"], "family": case["family"]} for case in dataset["cases"]],
        "limitations": ["Targeted at temporal generalization after prior disclosed failures; not an untouched broad benchmark.",
                        "Synthetic assistant-authored policy labels are not clinical ground truth.",
                        "All raw attempts and failures remain in the record; no case was removed or relabelled after execution.",
                        "A pass does not guarantee universal or real-world accuracy.",
                        "The set becomes disclosed development evidence after this single evaluation."],
        "attempts": [],
    }
    save_report(report, stable, archive)
    try:
        for case in dataset["cases"]:
            if source_hashes() != initial_hashes or sha256(dataset_path) != freeze["sha256"]:
                raise RuntimeError("Pipeline or frozen fresh dataset changed during execution")
            case_started = time.monotonic()
            try:
                attempt = assess(copy.deepcopy(case["inputs"]), "local_ai")
                if not isinstance(attempt, dict):
                    raise TypeError("Adapter returned a non-object result")
            except Exception as exc:
                attempt = {"assessment": None, "model_status": "evaluation_exception", "mode": "degraded",
                           "error": {"type": type(exc).__name__, "message": str(exc)}, "raw_output": None,
                           "raw_output_unavailable": "Adapter raised before returning its captured response."}
            assessment = attempt.get("assessment")
            decision = decide(case["inputs"], assessment=assessment,
                              model_status=attempt.get("model_status"), variant="local_ai")
            checks = field_checks(case["expected"], assessment if isinstance(assessment, dict) else {})
            valid = (attempt.get("mode") == "live_model" and attempt.get("model_status") == "valid"
                     and attempt.get("local") is True and attempt.get("model_digest") == args.model_digest
                     and attempt.get("prompt_version") == args.prompt_version and validate_assessment(assessment))
            route_matched = decision["route"] == case["expected"]["route"]
            row = {"id": case["id"], "family": case["family"], "title": case["title"],
                   "inputs": case["inputs"], "expected": case["expected"], "policy_rationale": case["policy_rationale"],
                   "elapsed_seconds": round(time.monotonic() - case_started, 3), "valid_inference": valid,
                   "route_matched": route_matched, "field_checks": checks,
                   "strict_match": valid and route_matched and all(c["matched"] for c in checks.values()),
                   "attempt": attempt, "decision": decision}
            report["attempts"].append(row)
            save_report(report, stable, archive)
            print(f"{case['id']}: {'MATCH' if route_matched else 'MISMATCH'}; valid_inference={valid}; "
                  f"strict_match={row['strict_match']}; {row['elapsed_seconds']:.1f}s", flush=True)
        if source_hashes() != initial_hashes:
            raise RuntimeError("Pipeline source changed before fresh evaluation completed")
        report["state"] = "complete"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["source_hashes_after"] = source_hashes()
        for source in (dataset_path, freeze_path):
            target = ROOT / "fixtures" / source.name
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise RuntimeError("A different published fresh dataset already exists")
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
