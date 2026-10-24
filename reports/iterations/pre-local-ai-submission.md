# Archived report: before local AI integration

This report describes the earlier build. See [the current report](../submission-report.md) for the delivered local-AI version.

# CareRoute: AI-assisted appointment intake and administrative routing

**Submission type:** implemented synthetic prototype with research, source, tests and reports. **Policy:** demo-policy-0.3. **Date:** 24 October 2026. No real patient data or clinical deployment.

## 1. Problem and delivered system

A community clinic needs to collect symptom descriptions, preferred appointment times and self-reported urgency, then support a transparent administrative next step. The system offers routine appointment, same-day human review or immediate emergency guidance according to a versioned illustrative policy. It does not diagnose, recommend treatment or determine that a person is safe.

The delivered application includes a responsive accessible form, immediate client-side emergency checks, deterministic routing, authored assessment replay, optional live decision-model adapters, durable SQLite requests, a staff queue, review and overrides, synthetic booking, preserved audit history and operational fallbacks. It runs with Python's standard library and a browser. All 44 records were newly invented for this project. The workspace is standalone and unrelated to OCS.

Emergency advice is present in the initial HTML. Yes/Unsure structured checks and bounded current-warning phrases show guidance before submission or any network/model request. In a failed save, the emergency message remains while receipt is denied or unconfirmed as appropriate. The application never says it contacted emergency services.

## 2. Research and model decision

Seven main papers were read beyond abstracts, including methods, results and limitations. Full reviews with section/table references are in the Jev and workflow research reports. These are published findings, not results from this implementation.

| Source | Method and relevant finding | Limitation for this project |
|---|---|---|
| Native Probability Outputs for Clinical Triage | Direct four-action comparison on 135 decision points from 62 CARE-Bench test cases; Jev had the lowest observed Brier score (0.610), but macro-F1 0.461 ranked fourth of five. Separate binary sufficiency Choice/Noul each detected 36/37 clarification cases, with 54/98 and 53/98 false positives. | Probability quality did not establish routing superiority; high sufficiency detection substantially increased clarification. Its urgent class merges same-day and emergency actions. |
| Jev in Medicine | Single-run benchmark comparison across medical knowledge/diagnostic tasks; lower calibration error in one task did not establish better matched-coverage selective prediction. | Diagnostic benchmarks, unoptimized prompts, training overlap and unavailable clinical adjudication limit transfer; decomposed Jev was not tested. |
| Controlled Audit of Self-Knowledge | Paired missing-evidence interventions; focused sufficiency questions ranked complete/incomplete inputs better than answer confidence in the tested setting. | One closed model/version; constructed contrasts and surface cues; ranking is not a calibrated probability of safety. |
| CARE-Bench | Disclosure-prefix action evaluation, case-clustered uncertainty, open-response mapping and direct-label support. | Source reconstruction, model-assisted annotation, a merged urgent/emergency class and mapper disagreement prevent direct adoption as our oracle. |
| Randomized public-use medical LLM study | 1,298 UK adults, 2,400 interactions, three model arms and usual-source control; no significant disposition improvement over control. | Ten scenarios and 2024 models; model-only performance differed from human use. API-timeout replacement means completed-interaction accuracy is not full service reliability. |
| DECIDE-AI | Modified Delphi reporting guideline for early live clinical AI evaluation, including human interactions and system failures. | Consensus reporting guidance; simulated scenarios are not a live clinical evaluation or regulatory approval. |
| FUTURE-AI | International consensus on lifecycle traceability, local validity, oversight, robustness and explanation evaluation. | General guidance rather than model-performance evidence; no direct patient/public involvement in the guideline process. |

The architecture comparison remains genuine: (A) structured form plus human review, (B) direct Jev finite classification with explicit defer, (C) decomposed Jev assessments composed by rules, and (D) a structured-output LLM using equivalent assessments. All have common emergency and operational guards. A general-purpose LLM is not assumed necessary, and Jev is not declared the winner.

Official TypeSafe documentation and SDK code were also inspected. Choice supports finite labels with probability distributions; confidence summarizes concentration, not probability of clinical safety. Questions do not see other answers within one request. Jev does not return arbitrary explanatory prose or text evidence spans. The implementation preserves native outputs, enforces schema/ranges/labels, and generates explanations from actual inputs and rules. Direct classification remains a separate adapter rather than being disguised decomposition.

## 3. Design and operational behavior

The system keeps urgency separate from information sufficiency and from persistence, review, delivery and booking. A preference for next week cannot lower urgency. Missing fields, ambiguous assessments, contradictions, unsupported scope, invalid outputs and unavailable models invoke human review, while emergency guidance has priority. The default no-AI mode explicitly defers unassessed narrative to staff.

Requests are saved transactionally with an owned queue item before assessment begins. An idempotency key prevents duplicate requests after a lost acknowledgment; conflicting reuse returns a conflict. Receipt tokens protect patient status access. Staff sign-in, version checks and separate reviewer/supervisor roles protect the synthetic workflow. Staff can take over a pending assessment; late model results cannot overwrite that review. Emergency downgrade needs a different supervisor. A new input revision preserves prior text and invalidates stale review/booking state.

Original input, application-generated sentence offsets, model/replay output, rejected-output records, policy/question/model versions, actual rule matches and staff actions remain auditable. Explanations contain recorded evidence, not persuasive medical reasoning. Notifications and appointments are explicitly simulated; no external service is contacted. After-hours or unavailable reviewers preserve the route and show service unavailability rather than a false same-day promise.

The narrow demonstration scope is English self-requests from invented adults aged 18–64 without pregnancy/postpartum context. These limits, six warning examples, a 30-minute review target and a fictional UTC clock are test configuration, not approved clinical guidance. Actual jurisdiction is unconfigured and is not inferred from timezone.

## 4. Executed verification

| Evidence | Result | What it establishes |
|---|---|---|
| Standard-library automated suite | **122 passed, 0 failed, 0 skipped** | Policy invariants, 43 authored routed fixture expectations, provider-contract mocks, HTTP/SQLite workflows, fault handling and evidence provenance. |
| Chromium browser groups | **12 passed, 0 failed** | Actual form interaction, offline/pre-submit emergency behavior, receipt, replay honesty, staff review/booking/audit, failed persistence, mobile layout and basic semantics. |
| Structured immediate checks | All six questions × Yes/Unsure worked offline before submission | Local event-handler behavior, independent of model/network/save. |
| Previous model-dependent examples | FX-08/09/38 now triggered local guidance before submission in the browser | Three bounded demonstration gaps closed; not universal emergency recognition. |
| Adapter coverage | Missing keys, malformed data, wrong distributions, choice/distribution disagreement, refusals and total deadline tested with explicit mocks | Contract/fallback behavior; not external-provider availability or accuracy. |
| Application status | Started successfully, health checked; functional requests exercised | Local executable demonstration, not deployment or clinical readiness. |

The browser measured immediate input-event-to-DOM visibility in-process, with a maximum observed 12.5 ms in that run. This is an engineering observation on this machine, not a clinical latency standard, screen-reader comprehension measure or human response-time study. Detailed JSON, logs and procedures accompany the report. Tests do not hide failed saves or model outages from operational outcomes.

## 5. Routing results and the safety/workload tradeoff

Forty-three fixture records represent routed requests; FX-31 represents failed initial persistence and correctly has no route. The no-AI comparison has 38 records with comparable authored dispositions. Five AI-specific failure/output scenarios are retained in outputs but excluded from that baseline's reference scores, with reasons recorded. These are visible development examples, not independently adjudicated clinical ground truth or a held-out model benchmark.

| Metric | Initial structured baseline 0.2 | Final reviewer-gated no-AI 0.3 |
|---|---|---|
| Emergency-route misses | 0/13 | 0/13 |
| Incorrect routine / nonroutine references | 5/32 | 0/32 |
| Incorrect routine / routine suggestions | 5/11 | Not estimable: no routine suggestions |
| Escalation / routine references | 0/6 | 6/6 |
| Same-day suggestions across 43 routed examples | 14 | 30 |

The initial failures included vague text, contradiction and unclear intent. Rather than present those routine suggestions as safe, policy 0.3 requires human narrative interpretation in no-AI mode. This removes automated routine leakage on these examples but creates more same-day work. Thirty saved nonemergency requests still require staff work; actual handling minutes, capacity and deadline performance under real demand were not measured. Original labels and initial results are preserved in the archive.

Authored replay conformance is **5/5 direct cases and 38/38 decomposed cases**. Those cases have different denominators and authored outputs; the figures establish rule/adapter wiring, not comparative Jev performance. No live model calls were made because credentials were absent. No live model accuracy, probability calibration, cost advantage or workload saving is claimed. Models must later be compared on the same independent held-out inputs with recorded versions, thresholds, batching and failure-inclusive denominators.

## 6. Limits, safety and delivery

This is ready to submit as an implemented synthetic demonstration with source, reproducible tests, research and honest results. It is not ready for real patients. Public demo credentials, loopback HTTP, simulated coverage/notification/booking and unapproved policy are explicit boundaries.

Important remaining evidence gaps are live Jev/LLM evaluation, independent clinical policy labels, human usability/accessibility evaluation, real reviewer handling time and capacity, supported-population fairness, and clinical outcomes. The bounded warning detector does not understand all language. A synthetic checkbox cannot technically guarantee that arbitrary user text contains no personal information; users must enter invented material only.

Before any authorized clinical pilot, the team must supply jurisdiction, approved routing policy, supported populations/languages, staffed hours, escalation contacts and acceptable error/workload thresholds, with privacy/security and operational approval. The local prototype keeps these dependencies visible instead of inventing them.

## 7. Included artifacts and reproduction

The submission includes runnable Python/HTML/CSS/JavaScript, 44 invented records, 122 automated tests, browser checks, generated JSON/logs, three screenshots, seven original design snapshots, current research reviews, implementation/API notes, safety note and demonstration guide. `README.md` contains exact run commands. The ZIP manifest records file hashes and excludes live databases, credentials and Git metadata.

Read the [test report](../test-report.md), [executed evaluation](../generated/evaluation.md), [Jev research](../research-update.md), [workflow research](../research-workflow-update.md), [implementation notes](../implementation.md) and [safety note](../safety-note.md) for the detailed evidence. No test results from the cited literature are represented as our own experiments.

## References

1. [Native Probability Outputs for Clinical Triage](https://arxiv.org/html/2610.24692v1).
2. [Jev in Medicine](https://arxiv.org/html/2609.34024v4).
3. [Beyond Answer Confidence: A Controlled Audit of Self-Knowledge](https://arxiv.org/html/2610.01006).
4. [CARE-Bench](https://arxiv.org/html/2608.03731v1).
5. [Reliability of LLMs as medical assistants for the general public](https://pmc.ncbi.nlm.nih.gov/articles/PMC12920132/?report=reader), DOI 10.1038/s41591-025-04074-y.
6. [DECIDE-AI](https://pmc.ncbi.nlm.nih.gov/articles/PMC9116198/).
7. [FUTURE-AI](https://pmc.ncbi.nlm.nih.gov/articles/PMC11795397/).
8. [TypeSafe primitives](https://docs.typesafe.ai/primitives) and [confidence semantics](https://docs.typesafe.ai/confidence). Vendor interface documentation, not independent clinical validation.
