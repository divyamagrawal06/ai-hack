# Synthetic policy evaluation

Run: `policy-eval-20261024T181230.235927Z`. Policy: `demo-policy-0.3`. Fixture source: `demo-policy-0.1`.

**Executed local policy behavior and authored replay conformance only. No live Jev/LLM calls, clinical evaluation, probability calibration, reviewer-minute measurement, or browser-timing claim.**

## Measured no-AI policy behavior

Executed 43 policy calls; 38 have comparable authored route expectations. Initial failed save FX-31 is excluded because the application must not derive a decision. FX-19–21 are excluded from reference scoring because their expected fallback is specific to an AI outage. FX-22–23 are also excluded because their human-review labels follow authored direct-model outputs on otherwise routine input, not independent reference dispositions. All five remain visible in case-level outputs.

| Measure | Result |
|---|---|
| Emergency route misses | 0/13 (0.0%) |
| Incorrect routine / reference non-routine | 0/32 (0.0%) |
| Incorrect routine / routine suggestions | not applicable (0 denominator) |
| Unnecessary escalation / reference routine | 6/6 (100.0%) |
| Same-day review suggestions (all policy calls) | 30 |
| Saved non-emergency requests still needing staff review | 30 |
| Policy execution errors | 0 |
| Reviewer minutes, UI guidance latency, calibration | Not measured |

Incorrect routine cases: none.
Emergency route miss cases: none.

The current no-AI arm does not affirm narrative sufficiency: every ordinary unreviewed narrative goes to human review (H05 unless a higher rule applies). This eliminates the observed routine-suggestion failures by increasing review escalation, including for reference routine cases. It does not demonstrate a winning model or measured workload savings.

Reference labels are authored demonstration expectations, not clinician-adjudicated gold labels. The initial structured-only baseline is preserved at reports/iterations/initial-structured-baseline.json and .md: under policy0.2 it produced five incorrect routine suggestions among the 32 non-routine references. The current reviewer-gated policy is versioned separately; fixture labels were not changed to obtain passing outcomes.

## Replay conformance — not live model performance

| Authored replay arm | Cases | Passed | Failed |
|---|---:|---:|---:|
| direct_replay | 5 | 5 | 0 |
| decomposed_replay | 38 | 38 | 0 |

The arms use different explicitly authored fixture subsets. Do not rank model candidates using these numbers. Direct stubs are finite choices, not sampled Jev predictions; decomposed stubs are supplied assertions, not measured detection results. AI failure states are injected metadata, not observed provider outages.

## Independent bounded warning check

7/7 known warning descriptions produced an emergency route without a model. FX-08, FX-09 and FX-38 retain their historical model-dependent fixture labels; the current detector addresses these exact descriptions independently. This does not show that arbitrary emergencies are recognized or that browser guidance appeared on time.

## Unrun work

Live direct Jev, live decomposed Jev, and live structured-output LLM comparisons are not run by this tool. Calibration, blinded staff/user workflow evaluation, capacity under load, and clinical/jurisdiction approval remain separate. Persistence, event timing and concurrent overrides require the API/browser test results rather than this policy report.

See `evaluation.json` for case-level outputs, exclusions, failure metadata, fixture hash, and denominators.
