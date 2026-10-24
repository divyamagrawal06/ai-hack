# Synthetic specification fixtures

[synthetic-cases.json](synthetic-cases.json) contains **44 newly invented scenarios**, written for this package. No records were copied, de-identified, or adapted from patient conversations. All cases have `synthetic: true` and a provenance statement. There are no real contact details or identities.

These are expected outcomes under illustrative policy `demo-policy-0.1`, not approved clinical labels and not executed test results. Every `test_status` is `not_executed`. No model outputs or benchmark scores are stored. The `assessment_stub` fields are authored inputs for a future replay harness. Even if a deterministic rule checker agrees with them, that does not validate Jev, an LLM, or the medical safety of the demonstration policy.

## Fields

- `id`, `title`, `requirements`: stable case identifier, purpose, and requirements covered.
- `variant`: `decomposed_replay` by default, or `direct_replay` for direct-classification adapter tests. All cases are replay specifications. An LLM using the same assessment contract can reuse relevant cases; this file does not claim it produced the stubs.
- `inputs`: original invented symptom text, preferred appointment times, self-reported routine/urgent/unsure status, illustrative age/supported-language inputs, requester, pregnancy/postpartum status, onset/currentness, explicit no-time-preference choice, and structured emergency answers. `CHECK-01`–`CHECK-06` are ordered emergency-question identifiers; the policy document defines their wording. Answer values are `yes`, `no`, `unsure`, or `unanswered`. Explicit `unsure` activates precautionary emergency guidance; absent/unanswered input invokes incomplete-information handling while keeping the persistent emergency notice.
- `local_signal`: an authored expectation about a supported local current-warning check, not output from a detector. `none` does not certify absence of all emergencies. `current_explicit_demo_warning` and `current_possible_demo_warning` represent illustrative known triggers.
- `assessment_stub`: independently authored `warning`, `intent`, `information_sufficiency`, `contradiction`, `scope`, `human_review_indication`, and `direct_route` expectations matching the normalized assessment enums in the data contract. `null` or a deliberately malformed object is permitted only in failure cases. No probability/confidence values are invented.
- `operations`: simulated model, submission, save, staffing, and slot state. `model_status: valid` means a valid authored replay stub, not a live successful model call. `not_called` is intentional for immediate pre-submit guidance. Staff delivery/notification is never claimed by any case because a save alone provides no delivery receipt.
- `expected`: administrative route (or absent decision for initial ordinary save failure), first applicable rule, immediate-guidance property and timing requirement, truthful receipt state, contact fallback need, booking state, and explanatory notes. `primary_rule` identifies the first applicable policy rule; it is not a complete execution trace. A future implementation must retain all rule inputs, evaluated predicates, matches, and the selected precedence result.

The ordered policy expectation is E01/E02 before H01–H05 before R01. Invalid assessor output cannot supply any apparently valid routine fields; H04 applies unless an independent emergency or other observed higher-priority rule already decides the route. Direct-replay guard cases carry reference context to exercise common guards; a live direct Jev call must not be assumed to return decomposed assessments.

`guidance_without_submission_or_model` is true only when a structured/local trigger is available independently. `emergency_timing_requirement` is `not_applicable` for non-emergency cases, `independent_trigger_required` for structured/local emergencies, or `known_gap_model_dependent` for FX-08, FX-09 and FX-38. Those three cases deliberately expose a design gap: their eventual emergency route is expected, but an implementation that waits for the model FAILS immediate REQ-03 timing. They cannot count as passing emergency-timing compliance. A persistent general notice does not erase the delayed specific instruction. Before claiming compliance, provide an independent appropriate trigger/fallback for these descriptions and execute the timing tests; do not merely change the label to passed.

An emergency route can exist before any request is submitted or saved. Ordinary processing saves the request before model assessment. FX-31 therefore has `route: null`, `primary_rule: null`, `assessment_state: not_started`, and `model_status: not_called`: no suggestion exists when its initial save fails. Decision absence is not a fourth route. `route` must never be used as proof of receipt, notification, review, or booking. `staff_notification_claim: false` is intentional even after save success; notification delivery has a separate state in the system contract.

The application may use age bands; fixtures carry invented `age_years` solely to make scope-boundary tests concrete. The grouped `onset_currentness` fixture field is a reduced rule-test input; `current` represents the authored currentness condition, and null tests missing routing information. It is not a complete serialization of the UI’s separate onset/currentness answers, and a future form adapter must not silently synthesize an onset answer. Convert 18–64 to the supported adult band, younger/older to unsupported bands, and null to unknown. Do not infer requester, pregnancy/postpartum status, or currentness from demographic defaults: these fields are explicit in each record.

## Coverage and use

- FX-01–09: routine, self-urgent, explicit/uncertain structured warnings, current/possible text warnings, and time preferences.
- FX-10–18: missing information, unanswered checks, contradictions, age/scope, and unsupported language.
- FX-19–24: timeout, malformed/error output, direct defer/same-day decisions, and decomposed review indications.
- FX-25–29: negation, history, third-person emergency, quoted/prompt-injection text, and outage priority.
- FX-30–35: failed persistence, after hours, unavailable reviewers/slots, and scope versus emergency priority.
- FX-36–42: direct guardrails, direct emergency, non-emergency uncertainty, honest replay mode, explicit no-time-preference selection, and urgency independent of scheduling.
- FX-43–44: unsupported pregnancy/postpartum scope and missing onset/currentness.

Concurrency, retry, notification, state transitions, version changes, and accessibility require sequences or observed interaction. They are specified as T-08–T-18 and T-21 in [the evaluation plan](../docs/06-evaluation-test-plan.md), rather than falsely represented as validated by one JSON row. No fixture is a substitute for those tests.

Before using these fixtures, the team must reconcile labels with its actual policy and document any amendments as a new version. Keep an untouched independent synthetic test set for model comparison; these visible examples are development material. Never insert real patient content to make the examples more realistic.
