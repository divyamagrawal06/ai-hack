# 07 — Safety note and delivery plan

> **Design snapshot (policy 0.1).** This document preserves the original requirements and proposed contracts. The runnable policy 0.3 implementation, executed checks, research updates and explicit deviations are described in [the submission report](../reports/submission-report.md) and [implementation notes](../reports/implementation.md). Statements below about unstarted work or blocked reading describe the earlier specification stage.

## Safety note for every demonstration

**This prototype is a synthetic administrative-routing demonstration. Its illustrative rules are not approved clinical guidance. It does not diagnose, provide treatment, establish that someone is safe, or replace a clinician or emergency services. If a situation may be an emergency, contact local emergency services immediately; do not wait for submission, AI processing or clinic review. No real patient records may be entered.**

This note is not a substitute for the emergency interaction or a way to excuse unsafe workflow. Real clinical use is blocked until policy, jurisdiction, staffing, supported populations and acceptable error thresholds are approved and implementation/evaluation gates are met. The current package consists of specifications; there is no operating service.

## Hazard and mitigation register

| Hazard | Mechanism | Proposed control and validation | Remaining uncertainty / owner |
|---|---|---|---|
| Emergency missed or delayed | Misread language, omitted checkbox, model/network/save delay | Persistent notice, immediate structured checks, E01/E02 precedence, pre-submit/offline fault tests, text-only miss/timing metrics | A bounded guard cannot recognize all emergencies. Clinical policy owner must define scope and validation. |
| Missing data becomes routine | Model confuses absent evidence with negative evidence | Independent sufficiency, explicit unanswered fields, H01/H05, missingness tests | Conservative routing can overload review; evaluate both harms. |
| False reassurance from confidence/explanation | Concentration interpreted as safety; persuasive invented rationale | No safety probability UI; actual inputs/rules only; validate evidence IDs and semantic support | Provenance does not establish correctness; human factors owner tests comprehension. |
| Excess escalation overwhelms clinic | Blanket warnings, over-deferral, correlated component errors | Separate escalation metrics, review-time measurement, capacity stress tests, threshold development | Synthetic mix cannot establish real demand; operations owner approves capacity. |
| Same-day route with no service | After-hours, absent reviewer, undelivered notification | Owned queue, deadlines, coverage calendar, escalation and approved alternate care path | No real intake until contacts/coverage are verified. |
| Lost submission or false notification | Commit/response loss, outbox failure, duplicate retry | Honest receipt states, idempotency, durable outbox and reconciliation tests | Infrastructure owner must prove actual transport semantics. |
| Unsafe override or lost update | Stale view, role misuse, staffing pressure | Role checks, version conflict, reason, second review for emergency downgrade, immutable history | Staff can also err; overrides need review and are not automatic truth labels. |
| Wrong model/policy applied | Alias drift, stale text, mixed policy versions | Pin versions, revision hashes, late-output rejection, replay provenance | A vendor may not expose immutable releases; document reproducibility limits. |
| Prompt injection / unsupported output | Text attempts to control model or UI | Treat text as data; bounded enums; schema/value validation; escaped display; adversarial cases | Structured output reduces format freedom, not semantic error. |
| Population/language mismatch | Unsupported users treated as routine | Explicit scope, unknowns to review, emergency precedence, subgroup test cases | The narrow demo scope cannot justify clinical generalization. |
| Privacy breach or accidental real-data use | Copied examples, live contact integrations, raw-log exposure | Newly invented fixtures, synthetic-only UX, no live messaging, access control and retention plan | Any real-data incident pauses collection; privacy owner determines handling. |
| Audit loss during outage | Unsaved client alert mistaken for server event | Distinguish observed local guidance from durable audit; write when available without gating help | Total persistence failure necessarily limits audit completeness. |

## Data and research governance

Use entirely invented records, including names/contact placeholders if needed. No production EHR connection, scraped patient forum conversations, copied case vignettes or de-identification pipeline is allowed. Research papers and published benchmark methods may be read to understand design, but their underlying source records must not be reused as demonstration fixtures. Public accessibility does not make a clinical conversation appropriate input.

The fixture author declares provenance per record; peer review checks for accidental real details and rule consistency. Avoid realistic reachable phone/email addresses. Do not send synthetic alerts to actual clinicians or emergency services. Any test transport is simulated or isolated and labelled.

Future model experiments must document vendor retention/training settings, data location, credentials and access roles, even with synthetic input. Preserve the synthetic audit required by this specification, with credentials removed. Proposed demo retention is through the review period and then explicit deletion/archive according to the project owner's choice; no clinical retention term is invented here. Real use requires a jurisdiction-specific privacy/legal review and approved retention schedule.

## Delivery gates and accountable decisions

| Gate | Evidence needed | Current status |
|---|---|---|
| G0: Standalone specification | Independent workspace, seven documents, fixture provenance, traceability and consistency review | Package created; see validation report for actual checks. |
| G1: Research complete | Full primary methods/results/limitations read; verified bibliographic identity; evidence table and conflicts | Blocked by source-host access. Official SDK/guidance and accessible companion methodology do not substitute for unread papers. |
| G2: Demonstration policy review | Team review of illustrative assumptions and expected fixtures; confirmed synthetic-only boundaries | Not approved. Fixtures demonstrate proposed semantics only. |
| G3: Implementation readiness | Contracts, accessible form, immediate guidance, save/queue/audit/override failure behavior implemented and tested | Not started. No application tests run. |
| G4: Comparative evidence | Preregistered paired four-arm experiment, independent reference labels, locked holdout, uncertainty/failure/workload reports | Not run. No model choice established. |
| G5: Human workflow readiness | Synthetic participant tasks, staff training, comprehension/override/coverage tests, operational exercise | Not run. |
| G6: Any real pilot | Approved local policy, jurisdiction, populations, thresholds, staffing/contacts, privacy/regulatory review and authorized prospective evaluation | Blocked; outside this deliverable's authorization. |

No broad “safe” or “ready for clinic” label follows from fixture checks or a zero-miss tiny synthetic sample. Release criteria need numerator/denominator, uncertainty bounds and reviewer-capacity limits. Safety gates must precede comparative efficiency selection; a more accurate but delayed system can fail the emergency timing requirement.

The team must explicitly assign a clinical policy owner, operations/coverage owner, engineering owner, evaluation lead and data/privacy owner. Keep names/contacts unconfigured rather than fabricating them. Required decisions include warning definitions, same-day meaning, urgency thresholds, approved contact wording, supported ages/pregnancy/languages, timezones/calendars, review targets and escalation acknowledgments. Staff may not silently substitute appointment availability for urgency.

## Change control, monitoring and stop criteria

Version policy, prompts/questions, model adapter, contracts, local text guards, segmenter and UI wording. A change identifies affected requirements and tests, then reruns those checks and the locked evaluation where applicable. Preserve previous decisions; a replay under a new policy is a new evaluation event. Vendor aliases, scope changes and language additions trigger review.

Future operational monitoring must distinguish model failures, missed/late guidance, erroneous routine suggestions, excess escalation, unowned/overdue tasks, notification failures, unsupported inputs and override patterns. Monitor by supported subgroup where valid and avoid treating protected attributes as urgency reducers. An unexplained emergency miss, disappearance of emergency guidance, systematic lost requests, unstaffed urgent queues or audit corruption pauses the relevant workflow pending investigation; the emergency static notice remains available. Exact operational thresholds and authority are team decisions, not supplied here.

## Research access and handoff

Research hosts were rejected by the environment proxy even after a network-permission retry. A draft was saved adding `arxiv.org`, `export.arxiv.org`, `docs.typesafe.ai`, `www.nature.com`, `pmc.ncbi.nlm.nih.gov`, `europepmc.org`, `www.ebi.ac.uk`, and `www.bmj.com`, preserving the existing package-manager preset. Saving this draft did not apply it or publish the environment. To resume full-paper reading, review and save the changes in environment settings, then publish the environment, or provide accessible paper copies. Do not treat this administrative step as clinical approval.

The package is usable for specification review now. Outstanding research and clinical/operational approvals are explicit; none are silently delegated to a model. The next engineering task, if authorized, is an isolated synthetic implementation of the approved contracts followed by the tests in [06](06-evaluation-test-plan.md).
