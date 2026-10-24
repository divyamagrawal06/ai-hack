# 01 — Requirements and acceptance criteria

> **Design snapshot (policy 0.1).** This document preserves the original requirements and proposed contracts. The runnable policy 0.3 implementation, executed checks, research updates and explicit deviations are described in [the submission report](../reports/submission-report.md) and [implementation notes](../reports/implementation.md). Statements below about unstarted work or blocked reading describe the earlier specification stage.

## Purpose and scope

Specify an AI-assisted appointment intake and administrative routing prototype for a community clinic. Deliver a reviewable form specification, transparent decision procedure, synthetic cases with expected outcomes, an evaluation protocol, and a safety/delivery note. This package starts no implementation and makes no clinical validation claim.

The actors are a fictional person requesting an appointment, an authorized clinic reviewer, a queue supervisor, and a policy administrator. Model vendors supply bounded judgments; they do not own the disposition. A staff reviewer remains responsible for review and booking. The system may suggest one of three actions: `routine_appointment`, `same_day_human_review`, or `emergency_guidance`. A suggestion is not an appointment, a diagnosis, or a clinical assurance.

## Normative requirements

“Must” is a prototype requirement. Demonstration constants are explicitly marked and require approval before any real use.

| ID | Requirement | Acceptance evidence |
|---|---|---|
| REQ-01 | Use newly invented synthetic records only. No real, copied, transformed, or de-identified patient conversation may enter fixtures, prompts, logs, screenshots, or demonstrations. | Fixture provenance and input controls reviewed; synthetic-only banner visible. |
| REQ-02 | Collect a symptom description, preferred appointment windows, and self-reported routine/urgent/unsure status; offer “no preference.” | Form fields and payload preserve original choices; preferences cannot lower route priority. |
| REQ-03 | Display emergency guidance immediately when a structured emergency answer or recognized potential emergency triggers it, before validation, save, submission, model completion, or staff review. Keep a persistent emergency notice. | Client/offline event-order tests and assistive-technology review; include failed network/save cases. |
| REQ-04 | Produce only administrative actions and supported explanations. Never diagnose, prescribe, or claim a person is safe. | Enumerated output contract and UI content review; adversarial-output tests. |
| REQ-05 | Keep urgency and information sufficiency separate. Missing/unclear information must not be a route to routine; clarification must not postpone emergency guidance. | Independent assessment fields, precedence tests, and incomplete emergency fixtures. |
| REQ-06 | Explain using the actual submitted inputs, validated structured assessments, triggered policy rules, and their ordering. Do not manufacture medical rationale or model quotations. | Explanation-to-event correspondence checks; invalid evidence selection rejected. |
| REQ-07 | Preserve original text and input revisions, raw model output, parsed output/errors, actual rules executed, policy/model/prompt versions, and staff corrections. | Replay from an immutable event snapshot; corrections append rather than erase. |
| REQ-08 | Support staff overrides with authorization, reason and preserved prior result. Prevent silent lost updates during concurrent review. | Optimistic concurrency tests; stale overrides rejected and shown for reconciliation. |
| REQ-09 | Handle timeouts, malformed/incomplete outputs, unavailable models, and unsupported scope with a visible fallback. | Fault injection shows no silent routine result; provisional review action or emergency guidance as appropriate. |
| REQ-10 | Distinguish unsaved input from confirmed receipt, and saved requests from delivered notifications. Never say staff were notified when persistence or delivery failed. | Transaction/notification fault tests and exact status text assertions. |
| REQ-11 | Give queues an owner, deadline, coverage calendar, acknowledgment and escalation path. Handle after-hours and unavailable reviewers explicitly. | Simulated clock, handoff, overdue and closure tests; no unattended “same-day” promise. |
| REQ-12 | Distinguish request received, assessment pending, staff reviewed, and appointment booked. Booking requires a confirmed booking record. | State-transition tests and patient/staff wireframes. |
| REQ-13 | Configure jurisdiction, emergency contacts, population and language scope explicitly. Never infer jurisdiction from timezone, IP address, or preferred appointment time. | Missing-configuration release gate; out-of-scope cases and DST tests. |
| REQ-14 | Label live-model, replay, degraded and no-AI modes accurately; replay must not appear as a fresh model assessment. | Mode/provenance checks in UI, logs and evaluation exports. |
| REQ-15 | Compare all four architectures under matched inputs, guardrails and review policies; measure harmful routing and workflow burden, not accuracy alone. | Preregistered paired evaluation, confidence intervals, denominator and failure reporting. |
| REQ-16 | Provide keyboard/screen-reader operation, plain-language questions and accessible urgent notices without color-only meaning. | Accessibility review; emergency guidance remains visible with JavaScript/network unavailable. |
| REQ-17 | Minimize data and access; keep synthetic identifiers and contacts obviously fictional. Redact credentials from audit/transport logs. | Data inventory, access tests and retention policy review. |
| REQ-18 | Gate model choice, pilot and deployment on evidence and team approval. Do not present illustrative policy or synthetic success as clinical validation. | Signed decision log and evidence report; unresolved dependencies block real use. |

## Required form inputs and optional information

Required for an ordinary complete request: original symptom text, self-reported status, preferred window or explicit no preference, age band and supported-language selection, onset/currentness answer, and yes/no/unsure emergency checklist responses. An incomplete ordinary request may be preserved for clarification, but cannot receive a routine suggestion. An emergency alert must work even if every required field is blank. Do not force lengthy intake to obtain help.

Use generated synthetic person IDs and optional fictional contact channels for the demonstration. No insurance, financial, address, real date of birth, identity document or full medical history is needed. Preserve text as entered; store normalized/segmented representations separately. Limits and supported languages must be declared; truncation must never be silent.

Preferred windows express scheduling preference, not urgency. The clinic's configured timezone is shown explicitly; a viewer's timezone may be offered as a labelled display conversion only. A routine request can still require staff clarification or be subsequently escalated.

## Boundaries and dependencies

No automated diagnosis, treatment, prescribing, autonomous booking, patient prioritization by wealth/insurance, or live EHR integration is included. No model sees real patient data. The prototype may simulate staffing and delivery only when visibly labelled. Approval to create a synthetic specification does not authorize a clinical pilot.

The team must decide supported populations (including children, pregnancy/postpartum, older adults and complex illness), supported languages, emergency warning definitions, coverage and deadlines, oversight credentials, failure paths, and acceptable harms. A narrower fictional adult-only demonstration scope cannot justify a broader deployment.

Acceptance is layered: document/fixture coherence first; implementation contract and fault tests second; model and workflow experiments third; clinical/operational approval last. Passing an earlier layer does not imply the later layers passed. [The evaluation plan](06-evaluation-test-plan.md) maps these requirements to executable future tests and current fixture assertions.
