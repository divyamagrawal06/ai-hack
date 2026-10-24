# Evaluation and test plan

> **Design snapshot (policy 0.1).** This document preserves the original requirements and proposed contracts. The runnable policy 0.3 implementation, executed checks, research updates and explicit deviations are described in [the submission report](../reports/submission-report.md) and [implementation notes](../reports/implementation.md). Statements below about unstarted work or blocked reading describe the earlier specification stage.

**Status:** specification only, synthetic records only. No model experiments, application tests, usability study, or clinical evaluation have been run. The 44 fixtures contain authored expectations under `demo-policy-0.1`; they are not a measured benchmark result. The policy and its example labels are not approved clinical guidance.

## Questions the evaluation must answer

1. Does the entire interaction deliver emergency guidance immediately when an explicit structured answer or supported local warning indicates possible emergency, including before submission and during outages?
2. How often does each decision method miss emergency guidance, suggest routine for a case requiring more urgent action, or escalate unnecessarily under the agreed policy?
3. Does separating urgency from information sufficiency expose uncertainty without generating excessive clarification or delaying emergency action?
4. What human work remains: unresolved requests, time to ownership and review, overrides, duplicate contacts, and out-of-hours fallbacks?
5. Can users distinguish request received, assessment pending, staff reviewed, and appointment booked? Can staff see the actual basis of a suggestion and safely override it?

Accuracy alone does not answer these questions. A model can obtain a high accuracy on routine-heavy cases while failing the emergency pathway. Even flawless performance on this small authored set would establish only conformance to its examples.

## Four comparable variants

| Variant | Decision mechanism | Explicit uncertainty | Main hypothesis and limitation |
|---|---|---|---|
| A: structured form plus staff | Local emergency guard, structured eligibility checks, human interpretation of narrative | Unanswered/unclear inputs and unresolved narrative remain staff work | May be sufficient with little model complexity; workload and interpretation delay must be measured. |
| B: direct Jev | Choice among `routine_appointment`, `same_day_human_review`, `emergency_guidance`, `defer` | Defer is a first-class output; common validation and guardrails still apply | A direct finite decision may perform well; probabilities alone do not demonstrate safe routing. |
| C: decomposed Jev | Bounded warning, sufficiency, contradiction, scope, and review assessments composed by rules | Unknown/unclear states are preserved independently | May make errors easier to locate; extra calls, correlated component errors, and excessive deferral may outweigh benefits. |
| D: structured-output LLM | Equivalent bounded assessments and same routing rules as C | Same output states and invalid-output fallback as C | Tests whether an LLM helps these specific assessments; format constraints do not establish truth or clinical safety. |

All variants use the same form, approved-or-illustrative policy version, emergency notice, local guards, staffing simulation, scheduling inputs, persistence controls, and human review rights. A has no model timeout: absence of AI is its declared operating mode, not an incident. Narrative that has not been interpreted by a human remains explicitly unreviewed. Any routine suggestion from structured eligibility is provisional; it cannot assert that text was assessed or waive human review of that text. Record a baseline's provisional route separately from its final human-reviewed route.

B remains a genuine direct classification experiment. Do not replace it with C and call it direct. Its adapter can map a direct emergency classification to E02 and same-day/defer to H05, while deterministic prerequisites and hard emergency guards remain common. If B does not produce sufficiency or contradiction judgments, unresolved prerequisites cannot be silently considered satisfied: use observed structured completeness and human assessment or explicit unknown values. Report this extra human burden. Do not manufacture component outputs from B's class probability.

Report both the **raw assessor output** and the **final guarded route** for B–D. This shows whether guardrails rescued errors or caused escalation. Compare complete deployable workflows as the primary endpoint; describe any unequal information, human effort, or model calls. The authored `direct_replay` fixtures supply additional reference context for guard tests, and are not evidence that a direct Jev call supplies decomposed judgments.

## Dataset and reference labels

Use [the fixture manifest](../fixtures/README.md) and [synthetic cases](../fixtures/synthetic-cases.json) for specification examples. These are newly invented, not copied, summarized, or de-identified patient conversations. Restrict evaluation to fictional identities and invented text. Reject accidental real-patient input before external model transmission.

Before experiments, a team policy owner and clinical reviewer must independently label synthetic cases for action, warning presence/currentness, information sufficiency, supported scope, and explanation evidence. Adjudicate disagreements and record both original labels and rationale. Reference labels should follow a frozen policy, not the candidate model's answer. Cases without reliable adjudication remain in an ambiguity analysis; do not silently score them as routine or exclude them from workload measures.

Develop a larger synthetic set from a scenario matrix: route, warning type, negation, temporal context, third-person intent, uncertainty, literacy, supported language, accessibility format, contradictions, missing fields, self-report, scope, and operational failure. Group paraphrases and related scenarios before splitting development/tuning/test sets to prevent leakage. Keep an untouched test split; record authoring process, seed if generated, revisions, and any model used for synthetic generation. Model-generated labels are not independent ground truth. The 44 public examples are development material and must not become the sole held-out evaluation.

Include a representative synthetic case mix and a separate challenge set enriched for emergencies and ambiguous text. Report both, with their prevalence. Any reweighting requires an explicitly hypothetical prevalence; synthetic frequency is not evidence of clinic prevalence. Compare each variant on the same cases and policy; randomize order and blind staff to variant identity where practical. Record model identifier, SDK/API version, prompts/question templates, retries, temperature if supported, provider endpoint, mode, token/call cost, and timestamps. Repeated runs measure variability and failures; do not choose the best run after observing results.

## Metrics and denominators

| Measure | Definition and reporting |
|---|---|
| Emergency miss rate | Reference-emergency cases without required emergency guidance / all reference-emergency cases. Treat failed, missing, and timed-out pathways as failures if guidance was required; show raw and guarded rates. Also list individual misses. |
| Emergency delay | Time from the first available triggering input to visible guidance, including pre-submit time. Separate structured/local triggers from model-only discoveries. Record median, upper tail, maximum, and any guidance that waited for save, submission, AI, or reviewer. A notice present on load is necessary but does not erase a delayed explicit interrupt. |
| Incorrect routine suggestion | Reference same-day or emergency cases receiving a routine suggestion / all reference same-day or emergency cases; also report false routine / all routine suggestions. Count provisional patient-visible suggestions separately from final staff actions. |
| Unnecessary escalation | Reference routine cases sent to same-day or emergency / all reference routine cases. Show both destinations, cause, and resulting staff work. Policy ambiguity must be separated from true over-escalation. |
| Defer and coverage | Deferrals / all cases; automated non-deferred decisions / all cases; risk versus coverage curves where meaningful. Never remove deferred cases from the workflow denominator or headline results. |
| Clarification burden | Requests needing clarification / all requests; questions per request, completion/abandonment, and delays. Emergency clarification that precedes guidance is a safety failure even if the final route is correct. |
| Reviewer workload | Requests requiring human interpretation or review, minutes per case, total reviewer minutes, pending volume, peak backlog, duplicate work, and escalation contacts. Include baseline narrative review and time spent interpreting AI explanations. |
| Operational reliability | Save failure, duplicate creation, notification failure, no-owner request, expired deadline, concurrent-override rejection, malformed output, model timeout, and recovery success rates with explicit denominators. |
| Usability and human decisions | Correct understanding of four workflow states; task completion; override correctness and time; missed emergency actions; staff agreement and automation bias. Measure the interaction, not only assessor output. |
| Probability quality | Brier score/log loss for defined mutually exclusive reference classes, calibration curves and bin counts, and uncertainty intervals. For binary component questions, score against that component's reference label. Never label probability or vendor confidence as “clinical safety probability.” |

Use paired case-level comparisons, confidence intervals, and subgroup counts. Bootstrap at the scenario family level when paraphrases are related. For rare emergency failures, report exact or appropriate binomial intervals as well as counts; zero observed misses in a small sample does not establish zero risk. Select sample size and clinically acceptable upper error bounds with the team before testing. Do not invent universal numerical thresholds from these documents. Unsupported populations are outside deployment scope but remain essential escalation tests, not a reason to ignore their failures.

For the inspected Jev guidance, confidence means distribution concentration, not clinical safety or probability of correctness. Native probabilities require empirical evaluation against matching reference targets. Inspect the precise interface for the chosen version. If any score affects defer thresholds, select thresholds on development data, freeze them, and report held-out risk/coverage and workload. A calibration gain is not a routing benefit unless the downstream action comparison demonstrates it.

Do not score a four-class direct distribution against three-class reference labels by silently dropping defer. Prespecify either an independently adjudicated four-action reference (including justified defer) or an explicit mapping of defer probability into the human-review action, reporting that transformation and separate deferral results. Do not renormalize away failed/unknown outcomes to improve scores. Do not multiply decomposed probabilities as though their errors were independent. Report probabilities for their own propositions; the composed route needs its own observed error analysis.

Use `not estimable` for empty denominators, with a count of zero; never display zero error for an untested group. Report failure-inclusive system metrics alongside conditional successful-call scores. The TypeSafe WorkflowEvals methods use different default batching for Jev and LLM questions; specify batching, retries and total deadline here so an interface choice does not masquerade as a model speed advantage.

## Test catalogue

Each test below is **planned, not executed**. A document/fixture consistency check is not a substitute for running it against an implementation. FX-08, FX-09 and FX-38 deliberately identify model-dependent emergency timing gaps: their expected eventual route does not satisfy REQ-03 if guidance waits for the model. Report these as known design gaps until an independent appropriate trigger/fallback is specified and verified; a persistent general notice does not make them timing passes. FX-31 instead expects no route and no model call because initial ordinary persistence failed.

| ID | Procedure and expected observation |
|---|---|
| T-01 | Replay all authored cases through the policy adapter; compare route/absence of decision, first applicable rule, explanation inputs, receipt state, and mode with expectations. Evaluate emergency timing separately: matching an eventual route in a known-gap case cannot be counted as a timing pass. Record mismatches, never relabel fixtures merely to make results pass. |
| T-02 | Enter yes/unsure on each structured emergency check before submit; block network and omit required fields. Guidance appears immediately and is reachable by keyboard and screen reader. No save/model/reviewer prerequisite. |
| T-03 | Exercise current, possible, negated, historical, quoted, misspelled, indirect, and third-person warning narratives. Check known local guards and model-only warning latency independently; document missed phrases. |
| T-04 | Vary only preferred appointment time and slot availability. Urgency and emergency guidance remain unchanged; booking is never fabricated. |
| T-05 | Independently vary sufficiency and urgency. Missing information, unsupported scope, contradictions, or defer cannot become routine; possible emergencies cannot be delayed by clarification. |
| T-06 | Inject timeout, connection reset, invalid JSON, omitted/duplicate question IDs, unknown labels, NaN/infinite/out-of-range probabilities, invalid distributions, extra prohibited output, and invalid sentence references. Fail validation into human review while retaining emergency guards. |
| T-07 | Inject symptoms containing instructions to ignore policy, replace labels, or reveal secrets. Preserve as data; output contract and policy cannot be changed by narrative text. |
| T-08 | Fail initial save and retry; fail acknowledgement after durable save; replay same idempotency key. No false receipt/notification claims, duplicate request, or lost emergency guidance. Recover actual durable state. |
| T-09 | Save succeeds but model or notification fails. Request remains received with accurate pending/degraded status; work remains visible in the staff queue. Notification delivery has its own confirmed status. |
| T-10 | Simulate open hours, after hours, missing reviewer, review deadline breach, absent escalation contact, next-day opening, and daylight-saving calendar transitions. Preserve route and deadline history; execute configured alternate-care/escalation path without false same-day promises. |
| T-11 | Two staff members read revision N and submit conflicting overrides. Exactly one compare-and-swap update succeeds; the other sees current state and must intentionally reconsider. Audit history contains both attempts. |
| T-12 | Override routine to same-day and emergency; attempt downgrade of emergency guidance. Require authorized role/reason, preserve prior advice/history, and never retract the patient's immediate emergency instruction. Apply the team-specified downgrade policy. |
| T-13 | Move through received, assessment pending, staff reviewed, and booked, including cancellation and rescheduling. State changes require evidence from the relevant subsystem. “Reviewed” never implies “booked.” |
| T-14 | Switch no-AI, live, replay, and degraded modes; make live unavailable. UI, logs, and export remain honest about mode and provenance. No quiet replay replacement presented as live inference. |
| T-15 | Inspect explanation and audit reconstruction for each route. Show actual relevant answers/sentence IDs and triggered rules, exact versions, original and corrected text, model response or error, and staff actions; no generated diagnostic justification. |
| T-16 | Try different known jurisdiction configurations and missing configuration. No guessed country or emergency number; unset jurisdiction visibly blocks clinical/live use. Demo copy uses “local emergency services.” |
| T-17 | Conduct keyboard-only, screen-reader, zoom, low literacy, and supported-language tasks with synthetic scenarios; emergency action remains prominent and focus changes are announced without trapping input. |
| T-18 | Inspect storage, telemetry, errors, exports, fixtures, and model requests. No real records, tokens, or unnecessary identifiers; access controls, deletion, retention, and external vendor logging behavior match declared demo configuration. |
| T-19 | Run the frozen paired four-variant experiment and analyze raw/guarded outputs, deferrals, staffing time, latency, failure rates, and route-specific errors. Include all attempted cases and failed calls. |
| T-20 | Blind staff workflow study with synthetic scenarios, randomized variant/order, and logged actions. Measure understanding, override quality, workload, and automation bias. Report training effects and sample limitations. |
| T-21 | Regression-test any policy/model/template/SDK version change, preserving old reference labels and explicitly reviewing changed expectations. Verify replay pins exact versions and cannot reuse mismatched fixtures silently. |
| T-22 | Check release gates and unresolved dependencies. Absence of approved policy, jurisdiction, staffing/escalation configuration, supported population, or accepted error criteria blocks use with real patients. |

T-02 must be tested with JavaScript/runtime failure as well as model-network failure. The static page must still show emergency guidance; interactive checks must never be the only way to discover that instruction. A universal free-text emergency detector is not claimed. Document supported local triggers and residual missed-text risk explicitly.

## Requirement-to-test traceability

| Requirement | Acceptance focus | Tests | Examples |
|---|---|---|---|
| REQ-01 | Only invented synthetic data | T-18, T-22 | All FX-01–44 |
| REQ-02 | Symptoms, preferences, self-report | T-01, T-04, T-05 | FX-01–05, 10, 13, 34, 41–42, 44 |
| REQ-03 | Immediate emergency guidance | T-02, T-03, T-06, T-08 | FX-03–09, 27, 29–30, 35–36, 38 |
| REQ-04 | Administrative routes; no diagnosis | T-01, T-15, T-19 | FX-01–02, 22–26, 38, 42 |
| REQ-05 | Sufficiency independent of urgency | T-05, T-06 | FX-04, 07, 09–14, 18, 22, 28, 37, 39, 41 |
| REQ-06 | Actual input/rule explanations | T-03, T-15 | FX-06, 14, 25–26 |
| REQ-07 | Original outputs and versioned audit | T-11, T-15, T-21 | All cases plus override/version tests |
| REQ-08 | Safe overrides and concurrency | T-11, T-12 | Operational test sequences; no single-row fixture suffices |
| REQ-09 | Validated outputs and safe failure | T-02, T-06, T-07, T-09 | FX-03, 19–21, 28–29 |
| REQ-10 | Truthful persistence and notifications | T-08, T-09 | FX-03, 30–31 |
| REQ-11 | Ownership, deadlines, alternate care | T-10 | FX-32–33 |
| REQ-12 | Distinct workflow/booking status | T-09, T-13 | FX-31, 34 |
| REQ-13 | Explicit jurisdiction and scope | T-05, T-16, T-22 | FX-15–18, 27, 35, 43 |
| REQ-14 | Honest live/replay/degraded labels | T-09, T-14, T-21 | FX-19, 40 |
| REQ-15 | Fair decision-model comparison | T-19, T-20 | FX-22–24, 36–38 |
| REQ-16 | Accessible form and guidance | T-02, T-17 | FX-17 plus observed usability tasks |
| REQ-17 | Privacy and data minimization | T-18 | Synthetic provenance of all fixtures |
| REQ-18 | Explicit release and safety gates | T-21, T-22 | Dependency checklist and version records |

## Execution and reporting protocol

1. Freeze the fixture/test policy, reference labels, model adapters, and analysis plan. Resolve actual team policy before making clinical performance claims.
2. Run deterministic local controls and persistence/concurrency fault tests first. Any delay of required immediate guidance or false saved/notified claim blocks the demonstration release until corrected.
3. Run replay fixtures to validate rule wiring and explanation reconstruction. Replay passing says nothing about live model detection accuracy.
4. Run live model comparisons only with appropriate access, synthetic-data controls, and recorded versions. Keep errors and timeouts in denominators. Compare cost and latency as well as decisions.
5. Run simulated staff/patient tasks and overload/after-hours scenarios. A correct model label is insufficient if the request remains unowned or users misunderstand it.
6. Publish a report with run ID/date, mode, executed test counts, passed/failed/skipped/unrun counts, per-route confusion matrices, failure examples, latency/workload measures, uncertainty intervals, and unresolved risks. Preserve failed runs.

**Current evidence:** documents and fixture expectations only. No model accuracy, calibration, latency, workload reduction, clinical safety, or implemented app behavior has been established. Research sources and their access status are recorded in the research memos; the source-derived findings must remain separate from the proposed evaluation design in this document.
