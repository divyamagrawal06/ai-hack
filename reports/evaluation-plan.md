# Implemented evaluation protocol and remaining experiments

This document describes the runnable evaluation harness; it does not turn authored stubs into live-model evidence. Run from the standalone project root:

```sh
python -m unittest discover -s tests -p 'test_policy.py' -v
python tools/evaluate.py --output-dir reports/generated
```

The commands require only Python's standard library. They call no vendor endpoint and read only the explicitly synthetic fixture set. `evaluation.json` contains case-level results, explicit exclusions, denominators, fixture hash, policy version, timestamps, and failed execution details. `evaluation.md` summarizes the same run. Run the full repository test suite separately for persistence, adapters, concurrency and browser behavior.

## Versioned baseline decision and preserved failures

The initial `demo-policy-0.2` structured baseline suggested routine from complete structured inputs while free-text interpretation remained pending. Executed evaluation found five routine suggestions on authored non-routine reference cases (FX-11, FX-14, FX-24, FX-28 and FX-39). Its original JSON and annotated Markdown are preserved at [initial-structured-baseline.json](iterations/initial-structured-baseline.json) and [initial-structured-baseline.md](iterations/initial-structured-baseline.md), with the original run timestamp. No fixture expected label was altered to conceal these failures.

Under `demo-policy-0.3`, the default no-AI arm cannot affirm narrative sufficiency. An ordinary unreviewed narrative is explicitly `unclear` and receives H05 human review unless a higher-priority rule applies; missing fields remain insufficient and emergency checks still act immediately. This is a conscious change in behavior, not a model upgrade or proof of clinical safety. It prevents those automatic routine suggestions at the cost of sending reference routine cases to same-day human review. Measure the added queue burden, preserve all original fixture expectations, and do not declare a model winner from this policy choice. Baseline absence of AI is still an intentional mode, not an H04 outage.

## Three distinct evidence types

1. **Executed local no-AI policy behavior.** Every decision-bearing fixture is sent to the actual rule function with actual local text detection. Expected-route comparisons use authored synthetic policy labels. FX-19–21 are excluded from comparative reference scoring because their reference H04 outcome represents an AI-specific failure, not an independently adjudicated clinical disposition. FX-22–23 are also excluded because they pair otherwise routine inputs with authored direct defer/same-day outputs, rather than independent reference dispositions. All five remain visible as exercised no-AI scenarios. FX-31 is excluded from policy invocation because ordinary initial save failure must leave no decision and no model call; verify it in API persistence tests.
2. **Authored replay conformance.** Direct replay uses only explicitly direct fixtures; default direct fields in other fixtures are not invented experimental predictions. Decomposed replay uses its assigned fixtures. Known local signals are passed explicitly to reconstruct the historical fixture scenarios. The original fixtures retain `demo-policy-0.1`; results report the current implementation policy version. Matching expected outputs demonstrates rule composition on given assertions, not Jev/LLM accuracy, calibration, or relative merit.
3. **Actual independent bounded warning recognition.** The detector runs against seven specific descriptions, including FX-08/09/38, which previously needed a model in the specification. Current rule code must return an emergency action before any model call for those exact examples. Negative, historical and quoted controls are unit-tested. This is a finite demonstration boundary, not universal emergency recognition. Browser display, accessibility, script failure and event timing need separate interaction tests; Python recognition alone cannot close those requirements.

Report emergency route misses, incorrect routine suggestions, unnecessary escalation, same-day queue suggestions, saved non-emergency cases still requiring staff interpretation, and execution failures with denominators. Preserve failure cases and comparison exclusions. Reviewer minutes, calibration, UI guidance latency, prospective demand, and live-model performance remain null/unmeasured in this harness. All non-emergency requests still require staff review; fewer same-day suggestions do not prove lower workload or safer care.

The public fixtures are development material authored alongside the specification. Results are not an independent held-out benchmark. A zero observed emergency miss on this finite set cannot establish a clinical error bound. Real clinical policy, jurisdiction, staffing, supported populations and acceptable error thresholds remain prerequisites for any patient use.

## Live four-arm experiment still required

Freeze a clinician-reviewed synthetic policy reference set and group related paraphrases before train/tune/test separation. Compare structured/no-AI plus human review, direct Jev with explicit defer, decomposed Jev composed by rules, and a structured-output LLM on matched inputs, guards, staffing conditions and policy. Keep direct classification genuinely direct: absent decomposed answers are not missing mandatory outputs. If a separate sufficiency question is added, report it as a separate ablation and measure its clarification burden.

Use the available live adapters only with synthetic input and configured credentials. Pin/report provider model identity, adapter/SDK, templates, parameters, retries and total deadlines. Keep raw model action separate from the guarded action and report errors/timeouts/defer in the total workflow denominator. Do not replace failed live calls with replay and label them live. Record native probabilities and vendor confidence separately; neither establishes clinical safety.

Before measuring gains, execute fault-injection tests for initial save failure, lost acknowledgements, duplicate submission, unavailable reviewer, after-hours handling, notifications, stale assessments and concurrent overrides. Run randomized synthetic patient/staff tasks to observe understanding, action timing, review time, override quality and automation bias. Compare models only after safety constraints pass; report uncertainty intervals and scenario-family clustering instead of accuracy alone.

The full metric definitions, requirements traceability and planned workflow tests remain in [06 — Evaluation and test plan](../docs/06-evaluation-test-plan.md). Research and release gates remain in [07 — Safety and delivery](../docs/07-safety-delivery.md).
