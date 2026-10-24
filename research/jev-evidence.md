# Jev evidence and interface review

> **Subsequent update:** Paper and documentation access was restored during implementation. See [verified full-text research update](../reports/research-update.md) for methods, results and limitations read on 2026-10-24. Access failures below describe the earlier specification pass.

Status: research notes for a synthetic administrative-routing prototype; not clinical guidance. Reviewed 2026-10-24. No live model calls, model experiments, application tests, or clinical validation were performed.

## What was actually read

The three arXiv papers and two requested documentation pages could not be retrieved: HTTPS proxy CONNECT returned **403 Forbidden** on initial attempts and on a retry after network permission was granted. Their identities, methods, tables, and numerical findings have **not** been independently verified in this session. A user-supplied synopsis is a useful research lead, not a verified citation. No result below silently promotes those synopses into evidence.

An authoritative alternative was available for interface review: the official TypeSafe Python SDK repository, linked by the `typesafe-sdk` PyPI package metadata. Its generated OpenAPI models, response processing, defaults, client call documentation, and README were read. The public TypeSafe organization also publishes guidance in its `skills` repository. That guidance was read as vendor documentation, not installed or invoked as an agent skill. These sources establish interfaces and vendor claims; they do not establish clinical performance.

| ID | Source and exact location | Access/result |
|---|---|---|
| J1 | [Native Probability Outputs for Clinical Triage, supplied URL](https://arxiv.org/html/2610.24692v1) | Blocked twice; full text, title, authors, methods and results unverified. |
| J2 | [Jev in Medicine, supplied URL](https://arxiv.org/html/2609.34024v4) | Blocked twice; full text and identity unverified. |
| J3 | [Controlled Audit of Self-Knowledge, supplied URL](https://arxiv.org/html/2610.01006) | Blocked twice; full text and identity unverified. |
| J4 | [TypeSafe primitives](https://docs.typesafe.ai/primitives) | Blocked twice. |
| J5 | [TypeSafe confidence](https://docs.typesafe.ai/confidence) | Blocked twice; do not attribute a mathematical formula to this unread page. |
| J6 | [SDK generated API models, pinned commit](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_schemas/models.py) | Read: `NoulAnswer`, `ChoiceAnswer`, `ScoreAnswer`, question classes, model metadata. Header identifies generation from `https://api.typesafe.ai/openapi.json`; live OpenAPI not fetched. |
| J7 | [SDK response handling, same commit](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/response_types.py) | Read: `_prepare_system_one_response`, `SystemOneResponse`, answer models. |
| J8 | [SDK client defaults](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/constants.py) and [sync client](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/client/sync/client.py) | Read: configured model, base URL, timeout, request fields, exception behavior. |
| J9 | [Official vendor question-design guidance, pinned commit](https://github.com/typesafe-ai/skills/blob/302eea662c54bca6730873fe245bec1d69ebc23d/skills/typesafe-ai/SKILL.md) | Read: sections “Criteria”, “Compose requests”, “Read the answers”. Vendor recommendations, not independent evaluation. |
| J10 | [PyPI typesafe-sdk 0.7.5](https://pypi.org/project/typesafe-sdk/0.7.5/) and [package metadata](https://pypi.org/pypi/typesafe-sdk/0.7.5/json) | Read package description, version and repository/documentation links. Package was not installed. |
| J11 | [PyPI jev 0.3.0](https://pypi.org/project/jev/0.3.0/) and [metadata](https://pypi.org/pypi/jev/0.3.0/json) | Read wrapper README, field mappings and limitations. A convenience wrapper is not interchangeable with the raw probability API. |

Downloads and repository clones used for research are temporary under `/tmp/clinic-*`. The specification contains links and analysis, not copied patient conversations or clinical records.

## Interface findings supported by source code

The core API evaluates `state` with a named `questions` mapping. A question has instructions plus explicit criteria. The SDK accepts JSON-like state and returns answers keyed by question name, with model and usage metadata. Request design therefore does not require arbitrary generated text or a general-purpose conversational model [J6–J8].

| Primitive | Observed contract | Implication for this prototype |
|---|---|---|
| `Noul` | Answer has `type="noul"` and scalar `noul`: described as probability of yes/true. No separate `confidence` field in this answer schema. | Suitable for focused binary judgments, but a low probability of yes is not evidence that sufficient information was supplied. Ask a separate sufficiency question. |
| `Choice` | Selected label is described as the highest-probability criterion; includes `probabilities` by label and a separate `confidence`. | Supports direct routing with an explicit `defer` criterion. Preserve the entire distribution and defer result; do not store only argmax. |
| `Score` | `score` is the probability-weighted expected rubric level; includes probabilities, legend and confidence. | A midpoint can hide mass on both routine and emergency levels. Do not map an averaged urgency score directly into routine routing. |
| Questions | `criteria` supplies named choice alternatives or yes/no meanings. Instructions can carry state references. | Version exact questions/criteria and use concrete descriptions. Audit must show actual input and triggered rules. |

The pinned generated schema uses ordinary floats for several probabilities/confidences; descriptive text says “0 to 1,” but those fields do not include explicit `ge=0`, `le=1` constraints. `probabilities` is a dictionary; the generated type does not itself enforce the expected labels or sum. The response layer can **drop unrecognized future answer types**, retaining the raw HTTP payload [J6–J7]. Therefore successful SDK parsing is insufficient for safe application acceptance. Validate required question presence, exact answer type, known labels, finite numerical values, permitted ranges, distribution keys and normalization tolerance; treat invalid or missing output as model failure. Preserve raw outputs securely for the synthetic audit, including rejected outputs.

The SDK defaults to model alias `jev-latest`, API base URL `https://api.typesafe.ai`, and a 10-second timeout for each HTTP operation [J8]. For evaluation, request a pinned model release if available; record requested model, returned model identifier, SDK version, timestamp, questions hash and policy version. An alias alone is not reproducibility. An HTTP operation timeout is not a demonstrated total workflow deadline: retries and multiple operations must fit a separately bounded application deadline. Emergency guidance runs locally before this path.

The `jev` convenience wrapper's README says Boolean fields are thresholded (default 0.5), `Choice` returns argmax, and `Score` returns an expected value. Its limitations explicitly say probabilities and confidence never reach the caller [J11]. Use the lower-level `typesafe_sdk` in any future probability-preserving experiment rather than losing information in a convenience wrapper. No numerical threshold in that README is a clinically approved operating threshold.

## Confidence, probabilities and evidence

The official vendor guidance says confidence measures concentration of the probability distribution rather than probability of being correct [J9, “Confidence is rarely the gate”]. The generated schema uses less precise phrases such as “greater certainty” [J6]. Neither warrants treating `confidence=0.95` as a 95% probability that routine routing is safe. The vendor also describes probabilities as likelihoods of correct answers [J9]; that is a semantic claim requiring local calibration evaluation, not a guarantee for this clinic or this question distribution.

Keep three quantities separate:

1. A model's probability for a specified proposition or choice.
2. A vendor concentration/confidence measure.
3. Empirical error/safety rates for final routing under the particular policy, population and workflow.

A proposition can be unclear because the input lacks information; confidence alone cannot reliably identify every missing fact. Evaluate sufficiency judgments independently. An uncertain sufficiency judgment must never turn into permission to select routine.

Jev's read text primitives do not provide arbitrary explanatory prose or text evidence spans [J6]. The image `Box` primitive is not text evidence. Generate stable sentence IDs and exact character offsets in the application. If evaluating evidence selection, ask finite questions over those sentence IDs (or one focused question per candidate sentence). Validate every returned ID against the original input and exact substring. ID validity establishes provenance, not that the sentence logically supports the judgment; that must be checked separately. Keep selected evidence optional and distinguish “no supporting text selected” from “no warning sign.” Avoid copying an LLM-style `reason` string into a Jev adapter contract.

J9 says questions in the same request cannot see each other's answers. Decomposed assessments can be asked together against the same state, but dependent composition happens in application rules or an explicit subsequent request. J9 also cautions that Choice always selects an option and suggests a companion Noul for “anything fits”; this is a vendor recommendation, not a reason to discard direct routing with an explicit defer alternative. Compare explicit defer alone against direct routing plus a separate sufficiency assessment as a prespecified ablation.

## Fair comparison of the four candidates

All arms share the persistent emergency notice, immediate structured emergency checks, identical form, versioned policy, save/error handling, human fallback, and audit rules. Hard safety checks take precedence in every arm; this comparison does not ask any model to remove them.

| Arm | Serious rationale | Main hypotheses/risks to test |
|---|---|---|
| Structured form plus human review; no AI | Deterministic eligibility and explicit patient answers can perform much of the task; exposes the minimum usable workflow and true reviewer burden. | Humans still need to inspect free text. Measure unsafe form responses, incomplete data, time to review, after-hours gaps and queue load; do not assume no-AI is error-free. |
| Direct Jev classification plus explicit `defer` | Finite `routine`, `same_day_review`, `emergency_guidance`, `defer` output matches a bounded decision model; may avoid error propagation and extra calls. Native class distribution supports operational analysis. | Is policy compliance reliable under incomplete/negated/historical/contradictory text? Does `defer` absorb ambiguity? Does information sufficiency improve detection or mainly increase unnecessary clarification? Direct labels alone cannot supply a faithful medical rationale. |
| Decomposed Jev assessments plus rules | Focused warning-sign, current-intent, scope, sufficiency and contradiction judgments make deterministic policy composition inspectable. Common state can support parallel questions. | Errors are correlated, and more questions can create more failure points or excessive escalation. Easier audit is a design benefit, not proof of better routing. Measure intermediate judgments and final routes. |
| Structured-output LLM with equivalent assessments | Tests whether contextual understanding or evidence selection improves the same bounded task. It is an empirical comparator, not a prerequisite. | Schema validity does not assure correctness. Test unsupported reasoning, prompt injection, evidence fabrication, latency, cost, and pressure toward unnecessary prose. No diagnosis or free medical explanation is accepted. |

Direct routing is a genuine contender. It should lose or win on prespecified safety/workload/latency criteria under matched inputs, not on a prior belief that only decomposition is “safe” or only LLMs understand language. Direct inference may be cheaper or more reliable; decomposed inference may be easier to debug; both claims remain hypotheses. Compare policy agreement and safety floors at matched reviewer capacity or coverage. Do not select a winner from a few hand-authored fixtures.

## Paper questions that remain open

The user carried forward the following summaries. They are **unverified research leads**, not findings independently read here:

- J1: lower probability error did not establish better routing; adding separate sufficiency questions increased detection and unnecessary clarification.
- J2: medical benchmark/calibration results may concern diagnosis rather than administrative intake.
- J3: confidence, missing evidence and sufficiency/self-knowledge are distinct evaluation targets.

Before promoting any of these to evidence, retrieve and read the full papers and supplements, verify title/authors/version, and extract:

| Source | Required methods extraction | Required limitations/transfer analysis |
|---|---|---|
| J1 | Dataset construction, patient/record source, sample size, exact route labels, Jev/comparator versions, probability metric, question wording, threshold tuning, sufficiency ablation, confidence intervals, held-out design. | Does “urgent” distinguish same-day review from emergency? Was routing measured separately from probability error? Were clarification burden, label ambiguity, leakage and prevalence addressed? |
| J2 | Tasks and benchmarks, number and provenance of cases, calibration metrics/bins, model versions, comparators, statistical uncertainty and external validation. | Diagnostic benchmark success cannot establish safe intake workflow performance, supported populations, or real patient behavior. Identify vendor involvement and benchmark contamination risks. |
| J3 | Missing-evidence interventions, known/unknown ground truth, sufficiency labels, self-knowledge measures, failure modes, aggregation and uncertainty. | Synthetic missingness may differ from frightened users' omissions or contradictory timelines. Determine whether confidence separates uncertainty from absence of current emergency evidence. |

Do not use the papers' supplied titles as proof of existence or publish numerical claims until source identities and text are verified. Network restrictions prevented paper reading; they do not demonstrate that the papers are nonexistent. This document fulfills interface investigation and analysis; **substantive reading of these three papers remains an outstanding research dependency**.

## Decision record contribution

Keep Jev decomposed assessments as the initial prototype candidate because its bounded outputs fit the intended contract and permit rule-level inspection. This is an engineering hypothesis supported by observed interface capabilities, not a proven clinical or performance advantage. Keep the direct Jev and no-AI arms in the evaluation plan. No production threshold, model winner, clinical policy, or live deployment is approved by this memo.

## Additional vendor evaluation methodology: WorkflowEvals

A bounded follow-up inspected the public TypeSafe organization and its `typesafe-ai.github.io`, `skills`, `typesafe-public-examples`, and `WorkflowEvals` repositories for authored research material. No copy of J1–J3 or a medical benchmark report was located in those inspected repositories. This does not establish that none exists elsewhere. The meaningful additional source is an executable **vendor evaluation framework**, not a peer-reviewed paper or independent clinical validation:

- [WorkflowEvals README, pinned commit `0ac3b8ad845429f0d8e064ecfb2430a47c5a25cb`](https://github.com/typesafe-ai/WorkflowEvals/blob/0ac3b8ad845429f0d8e064ecfb2430a47c5a25cb/README.md).
- [Scoring implementation](https://github.com/typesafe-ai/WorkflowEvals/blob/0ac3b8ad845429f0d8e064ecfb2430a47c5a25cb/core/scoring.py), [record contract](https://github.com/typesafe-ai/WorkflowEvals/blob/0ac3b8ad845429f0d8e064ecfb2430a47c5a25cb/core/contract.py), and [provider configuration](https://github.com/typesafe-ai/WorkflowEvals/blob/0ac3b8ad845429f0d8e064ecfb2430a47c5a25cb/core/providers.py).

The README lists four nonmedical workflows: invoice approval/fraud triage (150 cases), customer-service routing/actions (204), agent-run action selection (111), and security-alert triage/containment (240). These are repository-reported dataset sizes, not results reproduced here. Workflow code is assumed correct, and evaluated models supply judgments within that workflow. References come from OpenAI, Anthropic and consensus labels. The principal metrics are exact action-set agreement (including arguments) and primary-action agreement. A model is excluded from comparison with its own reference answers. Thus this benchmark measures **agreement with reference-model decisions under supplied policies**, not clinical correctness or observed harm.

The source makes several useful evaluation choices explicit. `score_pair` distinguishes prediction errors, missing predictions/labels, unresolved labels, stale/unverified input and policy mismatch. Prediction errors count as wrong; other coverage states remain visible. `build_score_data` uses a shared case/policy cohort per reference and reports metric denominators. `Call` records payloads, hashes, responses, failures, time and cost; `Observation` records question and state hashes and requires a named confidence calculation method. The dataset revision is recorded, and changes in model/settings/data/code require a different run name. These are useful design precedents for reproducible intake evaluation, with clinical/adjudicated labels substituted for reference-model consensus.

Important limitations follow directly from the methods:

1. Assuming workflow code is correct omits policy-rule defects, failed storage, notification failures, override conflicts and missed deadlines. The clinic evaluation must test those independently as system hazards.
2. Model agreement does not establish a safe reference label. Independent, policy-trained human adjudication is required, and disputed cases must remain visibly disputed.
3. None of the four listed tasks evaluates same-day versus emergency medical intake, patient language, supported populations, clinical calibration, or staff workflow outcomes. No transfer performance can be claimed.
4. Missing or invalid cases affect coverage and shared cohorts. Publish both full-cohort failure/coverage rates and conditional model metrics so filtering does not hide operational failures.
5. `configuration()` defaults to questions together for TypeSafe and one request per question for LLMs. That is a real design difference that may affect latency, cost and contextual interactions. A clinic comparison should report batching explicitly and include matched and provider-appropriate configurations as separately identified arms or ablations.
6. The framework defaults to `jev-1.13.0`; this does not establish the best model or the version used in any supplied medical paper. Its provider configuration rejects other Jev versions for that benchmark. Model versions must be pinned in the clinic's own protocol rather than inferred from an SDK default.

No datasets were imported into this project, no benchmark runner was executed, and no reported model ranking, cost advantage or accuracy figure is asserted. This follow-up improves the methodology review but does not replace the still-unread medical papers.
