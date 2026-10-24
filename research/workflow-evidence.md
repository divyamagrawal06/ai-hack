# Workflow and evaluation evidence ledger

> Historical specification-stage evidence ledger. The access failures below were subsequently resolved for all four main articles. See [the current full-text workflow research report](../reports/research-workflow-update.md) for verified methods, results, limitations, and the official PMC alternative for the randomized study. The original ledger remains below to preserve the chronology; its unread/blocked status is no longer current.

Status: direct paper access blocked; CARE-Bench repository methods were independently read. No paper full text was obtained or read in this workspace. This ledger records the distinction between the user's research carry-forward and independently observed repository evidence. It is not a completed full-text literature review. Prepared 2026-10-24 for a standalone synthetic-only clinic intake specification.

## Retrieval record

All four supplied URLs were requested using Python's standard HTTPS client through the environment's configured proxy. Each failed with `Tunnel connection failed: 403 Forbidden` before an article response was received. They were retried once after the parent agent obtained a network permission change; the same failure remained. This establishes an access blocker, not a missing, fabricated, or invalid publication.

| ID | Supplied source | Observed access | Evidence available in this workspace |
|---|---|---|---|
| W1 | [CARE-Bench](https://arxiv.org/html/2608.03731) | Paper: proxy CONNECT 403; companion GitHub repository accessible | Repository identifies title/authors and matching arXiv ID; public methods/interface read; full-paper methods, review details, and results remain unverified |
| W2 | [Randomized study of public use of medical LLMs](https://www.nature.com/articles/s41591-025-04074-y) | Proxy CONNECT 403 | User's description only; paper identity, sample size, arms, results, and limitations not independently verified |
| W3 | [DECIDE-AI](https://pmc.ncbi.nlm.nih.gov/articles/PMC9116198/) | Proxy CONNECT 403 | User's identification only; source text/checklist not inspected |
| W4 | [FUTURE-AI](https://pmc.ncbi.nlm.nih.gov/articles/PMC11795397/) | Proxy CONNECT 403 | User's identification only; source text/recommendations not inspected |

Authoritative alternate endpoints were also attempted: PubMed search for DECIDE-AI, Europe PMC's article page, EBI Europe PMC `fullTextXML` for PMC9116198, the CARE-Bench arXiv PDF and export API, Crossref's DOI record for W2, and a BMJ endpoint for FUTURE-AI. All returned the same proxy-level 403. No abstract, PDF, checklist, or bibliographic metadata was recovered. No credentials were requested, proxy bypass used, or TLS verification disabled. No patient data were transmitted.

Required direct-source hosts for resuming this reading: `arxiv.org`, `www.nature.com`, `pmc.ncbi.nlm.nih.gov`. Alternate hosts are optional and must not be treated as automatically authorized additions. Once access is available, retrieve and read full methods, results, limitations, and supplements before replacing the unverified entries below.

## Independently read CARE-Bench repository evidence

GitHub repository search located [ningkko/CARE-bench](https://github.com/ningkko/CARE-bench), which links the exact supplied arXiv ID and identifies the paper as *CARE-Bench: Benchmarking Patient-Facing LLM Triage*, by Yining Hua, Hongbin Na, and Cyrus Ayubcha (2026 preprint). Its project-page footer lists the same authors, and its maintainer contact names Yining Hua. This is a matching companion-project attribution, not independent publisher verification. Read at commit `090e84167f23c72d29c3a4d9c4f73e857afe0458`:

- [README: task, construction, release, scoring, limitations](https://github.com/ningkko/CARE-bench/blob/090e84167f23c72d29c3a4d9c4f73e857afe0458/README.md)
- [Project page source](https://github.com/ningkko/CARE-bench/blob/090e84167f23c72d29c3a4d9c4f73e857afe0458/index.html)
- [Label schema](https://github.com/ningkko/CARE-bench/blob/090e84167f23c72d29c3a4d9c4f73e857afe0458/data/public/label_schema.json)
- [Generation system protocol v3](https://github.com/ningkko/CARE-bench/blob/090e84167f23c72d29c3a4d9c4f73e857afe0458/configs/prompts/generation_system_protocol_v3.txt)
- [Deterministic scorer](https://github.com/ningkko/CARE-bench/blob/090e84167f23c72d29c3a4d9c4f73e857afe0458/code/score_label_submission.py)

**Methods established from repository text, not paper full text:** the task evaluates current action at successive patient-disclosure prefixes, with one to three prefixes per case. Four labels represent needed clarification, self-care/monitoring, nonurgent professional care, and urgent/emergency care. The release describes 500 total cases and 1,059 prefixes: development 284/609, validation 93/181, public Test 1 62/135, and controlled-access Test 2 61/134. Thus 439 cases/925 prefixes are public. Cases are reconstructed from MedDialog, two ChatDoctor sources, PriMock57, and follow-up-question sources; GPT-5.5 assisted construction/review/revision followed by human review. Detailed human-review methods and validation analyses are explicitly deferred to the companion paper.

**Interface and measurement established by reading source:** providers receive label-free accumulated patient text, with prompted and unprompted protocols. Direct action-label predictions can be scored without a model mapper. For open text, the documented mapper receives the current prefix, response, and label codebook, but not gold labels or future turns. The scorer rejects missing predictions, unknown labels, duplicate IDs, and unknown IDs. It reports accuracy/macro-F1 alongside threshold-specific missed care, unnecessary care, urgent false negatives, and false urgent escalation, retaining counts and denominators. Its ordered escalation metric uses `information_needed < self_care < nonurgent < urgent`. The code returns zero for rates with an empty denominator; our evaluation should instead display `not estimable` to prevent an empty subgroup from looking safe. No scorer or model was executed here.

**Limitations observed in the release:** urgent and emergency actions share one class; it cannot directly validate our distinct emergency-guidance versus same-day-review outcome. The action taxonomy treats information sufficiency as part of the ordered class, whereas our requirements need a separate sufficiency axis. Source reconstruction and model-assisted construction introduce provenance/annotation questions that require the full paper. Public cases and labels may be exposed to training; controlled access reduces casual ingestion but the maintainers explicitly note it cannot prevent later logging/copying. Raw model responses, reviewer records, internal construction code, and private labels are outside the public release, so the public package does not reproduce every paper experiment. The repository explicitly says this narrow escalation benchmark does not establish clinical safety or deployment readiness.

**Implications:** direct-label Jev routing is a valid experimental arm; the benchmark contract does not require a generative LLM. Preserve raw and final decisions and measure escalation-specific failures. Adopt the idea of disclosure-prefix/temporal tests and transparent scorer denominators, but create wholly new records, keep sufficiency separate, and split emergency from same-day actions. Do not import the benchmark's source-derived patient records into this synthetic-only project. No benchmark records are used as project fixtures or sent to a model.

**Result boundary:** no model ranking or quantitative performance finding is taken from this repository inspection. The companion paper remains required for its actual experimental results, human-review design, and limitations. This is substantive source-code/methods research, not a claim to have read the inaccessible paper.

Additional GitHub searches for DECIDE-AI/FUTURE-AI guideline and author-specific repositories found secondary mentions or unrelated projects, not a verified author full-text copy. A later search returned HTTP 429 and the search was stopped. A repository matching the randomized paper DOI was a third-party reference, not established author material; it was not used as evidence.

## Source-specific carry-forward and extraction questions

The entries labeled **carry-forward** below reproduce the user's contextual summary; they are not findings established by this run. The implications labeled **proposal** are independently reasoned specification choices, not empirical claims about model performance.

### W1 — CARE-Bench

**Verified repository finding:** intermediate disclosure prefixes are evaluated, and the urgent label combines urgent/emergency actions. The repository does not separately establish a clinic-specific same-day definition; that mapping must be defined locally.

**Full-paper verification still needed:** patient population and inclusion/exclusion; detailed case construction and provenance review; annotations and adjudication; evaluated model versions; patient-facing versus clinician-facing setting; use of patient history and context; quantitative errors at each decision stage; subgroup coverage; benchmark contamination and uncertainty limitations. Locate the methods taxonomy, outcome tables, and error analysis before citing a number or class mapping.

**Proposal:** maintain separate labels for `emergency_guidance`, `same_day_review`, and `routine_appointment`; do not import a merged benchmark label as the routing oracle. Score each bounded judgment as well as the composed route. A model can improve a benchmark's merged urgent sensitivity while still failing emergency action timing or overloading same-day review. Neither result can be inferred without separate measurements.

### W2 — randomized public-use study

**Carry-forward:** evaluate the human workflow rather than standalone model accuracy alone.

**Verification needed:** actual trial allocation unit, eligibility and recruitment, comparator arms, user instructions, exposure to AI, whether cases were simulated or real, model/version and tool access, sample size and power, primary endpoint and analysis population, missing data, effect sizes with uncertainty, adherence, user actions, and study-specific limitations. Establish whether performance was measured as clinical correctness, source choice, action choice, or another endpoint; those are not interchangeable.

**Proposal:** separate an offline component comparison from a later synthetic workflow exercise with participants acting as patients and staff. Measure whether users notice and act on emergency guidance, whether they understand receipt versus booking, and whether staff identify uncertainty and correct unsafe suggestions. Even perfect component classifications do not establish appropriate user action, timely review, successful persistence, or adequate staffing.

### W3 — DECIDE-AI

**Carry-forward:** early evaluation should account for workflow, human factors, and safety documentation.

**Verification needed:** reporting guideline scope, development/consensus method, intended development stage, exact checklist wording, handling of human-AI interaction and safety events, and stated limitations. Do not claim compliance by merely citing the guideline. Create an item-by-item applicability matrix only after reading the actual checklist.

**Proposal:** record intended users and setting, workflow placement, versioned interventions, staff training, error detection, overrides, human interaction, safety events, and changes made during evaluation. A synthetic demonstration is an early design exercise; it is not a clinical evaluation or evidence of effectiveness.

### W4 — FUTURE-AI

**Carry-forward:** traceability, trustworthy deployment, and safety documentation are relevant.

**Verification needed:** source identity and version, recommendation-development method, scope and intended users, specific traceability and lifecycle recommendations, their evidence basis, and limitations. Avoid interpreting a consensus framework as comparative clinical-performance evidence for Jev, an LLM, or this workflow.

**Proposal:** assign accountable owners, retain provenance, define failure handling and review triggers, and document limitations across the lifecycle. Require a documented decision before any change from synthetic demonstration to a clinical setting. A model swap, policy change, population change, or new jurisdiction needs re-evaluation of affected contracts and scenarios.

## Evaluation design contributions

The following is a proposed design for future experiments. No experiment, model inference, application test, or participant study has been conducted.

### Controlled comparisons

Compare four arms using the same frozen synthetic cases, route definitions, structured inputs, immediate emergency preflight, policy version, infrastructure failure injection, staff interface, and service assumptions:

1. Structured form plus human review without AI.
2. Direct Jev route classification with an explicit defer outcome.
3. Decomposed Jev assessments composed by deterministic rules.
4. A structured-output LLM supplying the same decomposed assessments.

The immediate structured emergency safeguard belongs to every arm. Direct classification is a serious candidate within that shared boundary; it must not remove immediate guidance to make the comparison more 'pure.' Report both the raw model decisions and the final safeguarded routes so the effect of the safeguard is visible. Compare model abstentions with actual downstream action and review burden; deferral is not automatically success.

Use fixed prompts/contracts and record model IDs, versions, sampling controls if available, latency, failure rates, and token/call cost where exposed. Match information and evaluation targets; disclose irreducible vendor differences. Select thresholds on development cases only, then lock them before running the holdout set. Do not tune thresholds to a small demonstration fixture pack.

### Case and oracle design

Construct newly invented scenarios with paired variants for negation, past versus current symptoms, third-person quotations, conflicting answers, time preferences, missing answers, unsupported ages/populations, low literacy, code switching, and adversarial instructions. Include explicit emergencies in both structured answers and free text, and non-emergencies containing emergency vocabulary in historical or quoted contexts.

Split by scenario family, not by individual paraphrase: variants of one invented situation must not cross train/development/holdout boundaries. For any stochastic system, repeated calls remain clustered by scenario and are not independent cases. Include a representative synthetic mix and a separately reported challenge set; prevalence in an emergency-heavy challenge set cannot estimate real clinic workload.

The demonstration oracle is a versioned mapping from the illustrative policy to expected behavior. It is not a medical ground truth label. Before clinical evaluation, qualified local policy owners must define routing labels, acceptable alternatives, and timing; two independent reviewers and adjudication are a proposed labeling process, with disagreement retained rather than erased. Label urgency and information sufficiency separately. 'Insufficient' must not silently map to 'routine.'

### Required metrics and denominators

| Metric | Numerator / denominator or distribution | Interpretation and caveat |
|---|---|---|
| Emergency miss rate | Oracle emergency scenarios lacking the required emergency guidance / all oracle emergency scenarios | Include crashes, timeouts, and save failures; also report structured and free-text-only emergency slices |
| Emergency timing failure | Structured emergency scenarios where guidance is gated on submission, network/model response, save, or staff review / all structured emergency scenarios | Report elapsed time in addition to pass/fail; timing target requires policy sign-off; persistent notice is not evidence that a text-specific trigger was detected |
| Incorrect routine suggestion | Cases assigned routine despite an oracle emergency or same-day route / all oracle non-routine cases | Also report the fraction among routine suggestions, since it answers a different question; list counts and route confusion matrix |
| Unnecessary escalation | Oracle routine cases escalated to same-day or emergency / all oracle routine cases | Separate same-day and emergency destinations; policy-approved conservative fallbacks may still consume workload |
| Information failure | Cases with missing/contradictory information assigned routine / all cases marked insufficient or contradictory | Denominator must be separately labeled, not inferred from the model's own answer |
| Defer behavior | Defer count / all eligible model calls; coverage = non-deferred eligible calls / eligible calls | Report route error at coverage, plus final action after deferral; high deferral can mask low useful coverage |
| Reviewer workload | Number of queued requests, duplicate tasks, handling minutes, handoffs, and escalations per 100 requests | Report task distribution and capacity assumptions; measure simulated workload separately from a real staffing forecast |
| Review timeliness | Time from durable receipt to first human review and overdue count / review-eligible requests | Track unowned and unreviewed items explicitly; medians alone hide long tails |
| System failure rate | Failed operations / attempted operations, by save, notification, model call, parse, queue claim, override, and booking | Show recovery, duplicate effects, and safety action under each failure; never drop failed cases from headline denominators |
| Explanation fidelity | Decisions whose displayed input facts, sentence references, fired rules, and versions match recorded execution / decisions inspected | Persuasive prose does not count as faithful evidence; unsupported or out-of-range sentence IDs fail |
| Human correction | Inappropriate suggestions corrected, new inappropriate changes introduced, override time, and reasons | Staff agreement alone is not a correctness oracle; preserve model and staff error categories |
| Receipt/booking comprehension | Participants correctly distinguishing received, assessment pending, staff reviewed, and booked / participants tested | Proposed future workflow study outcome; no such study has run |

For all rates report numerator, denominator, and uncertainty where sample size permits. A fixture pack is suitable for checking specified examples, not estimating safety. With zero observed emergency misses in n independent relevant cases, the rough one-sided 95% upper bound is about 3/n; this small fixture pack cannot support a rare-event safety claim, especially when only a subset are emergency cases and variants are dependent. Use appropriate exact or clustered estimates in a real evaluation; do not imply independence or clinical generalization from invented cases.

### Failure and interaction tests to preserve

- Emergency guidance appears before submission and remains available offline and while the model is unavailable; blocking validation, slow requests, and failed persistence cannot hide it.
- Empty or contradictory answers preserve uncertainty, offer clarification when safe, and trigger the defined review/fallback route; a routine self-rating or convenient future appointment cannot reduce an otherwise higher urgency.
- Timeout, malformed/extra fields, unknown enums, invalid sentence IDs, stale policy output, and unsupported model versions produce an explicit degraded state and a safe rule-driven fallback.
- Save failure says the request was not received; a later idempotent retry cannot create duplicate requests or notifications. A notification failure after a successful save is distinguished from a failed save.
- Queue ownership is atomic. Simultaneous staff claims and stale overrides use optimistic concurrency or an equivalent conflict contract; no silent last-write-wins loss of safety-relevant decisions.
- After-hours or unavailable-reviewer states cannot promise same-day review or report that staff were notified without evidence. Retain the administrative route separately from whether the service can actually fulfill it, and show configured fallback contact guidance.
- Emergency guidance has no 'wait for clinic reply' dependency; later downgrade does not erase the original decision, user-visible guidance, or audit history.
- Replay mode uses saved synthetic outputs and displays that fact. Live mode records a real model call and version. Degraded mode must not masquerade as a model assessment.

### Decision rule for choosing an architecture

Do not select a winner from overall accuracy or vendor confidence. Predefine acceptable emergency misses, incorrect routine suggestions, excess escalation, latency, workload, and failure-recovery behavior with the team. Compare uncertainty and use a predeclared tradeoff rule. If those thresholds, jurisdiction, population, and staffing are absent, retain all four arms as candidates and limit conclusions to observed synthetic demonstration behavior. Better native probability error, if verified in a paper, would still not prove better routing at a particular operating point or in this clinic.

## Unresolved evidence work

Obtain permitted access or supplied paper copies, verify publication identities, and complete the full-paper method/result/limitation extraction above. CARE-Bench public repository findings are established only to the extent described in the independently read section. No claim in this memo that a particular paper showed a numerical improvement, validated a specific model, or established clinical safety should be inferred. This evidence gap is independent of whether the specification documents are internally coherent.
