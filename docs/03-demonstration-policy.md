# 03 — Illustrative demonstration policy

> **Design snapshot (policy 0.1).** This document preserves the original requirements and proposed contracts. The runnable policy 0.3 implementation, executed checks, research updates and explicit deviations are described in [the submission report](../reports/submission-report.md) and [implementation notes](../reports/implementation.md). Statements below about unstarted work or blocked reading describe the earlier specification stage.

**Policy ID: `demo-policy-0.1`. Synthetic demonstrations only; not approved clinical guidance.**

The clinical team has not provided its policy. These rules exist to make the proposed interface, audit and tests concrete. They are not an exhaustive red-flag list or a triage algorithm suitable for patients. Do not infer jurisdiction or invent a working emergency number. The demo says “Contact your local emergency services now”; jurisdiction-specific contact and accessible calling options are mandatory before any real use.

## Configuration and outputs

The fictional supported routine scope is age 18–64, English input, appointment requests for the requester, with no declared pregnancy/postpartum or other unsupported context. This choice is a test boundary, not a statement about risk by age or language. Any unsupported or unknown scope receives human review; an emergency still takes precedence. Reference fixture metadata is never passed to a model as an input feature.

Routes: `emergency_guidance` has highest priority, followed by `same_day_human_review`, then `routine_appointment`. These priorities describe the proposed action, not a clinical severity score. `defer` is an assessor result, never a fourth route. `information_sufficiency` is independently `sufficient`, `insufficient`, or `unclear`.

Illustrative simulation constants: model deadline 10 seconds from request; human review target 30 minutes from persisted receipt for same-day requests; routine review target two simulated staffed business days. These timings are engineering test values without clinical endorsement. Production must refuse to activate until approved hours, targets, ownership and escalation contacts are configured.

## Immediate emergency layer

A persistent notice appears with the initial HTML and stays visible on every intake and receipt screen: **“If you think this may be an emergency, contact your local emergency services now. Do not wait for this form or a clinic reply.”** The demonstration also states “Synthetic demonstration only—do not enter real patient information.”

Short structured checks ask whether the person is currently experiencing the configured emergency examples. For this fictional test policy the examples are severe trouble breathing, severe chest discomfort, sudden trouble speaking or new one-sided weakness, uncontrolled heavy bleeding, possible overdose/poisoning, and immediate danger of self-harm. Each answer is yes/no/unsure. A yes or unsure answer activates precautionary emergency guidance immediately. An unanswered check is missing information, not a no. No list should be described as exhaustive.

Local text handling may recognize a small versioned set of clear or possible current warning descriptions. This is an additional demo guard with specified test cases, not an assumption that a regex recognizes clinical meaning. Broad substring matches are unacceptable: negation, historical symptoms, quoted/third-party text and uncertainty require contextual tests. Unsupported language or ambiguous generic complaints do not get silently cleared by a phrase detector. The static notice is the fallback when the client cannot interpret the text.

Emergency guidance does not need a saved record, successful JavaScript initialization, completed fields, submission, model response or staff acknowledgment. The structured alert is an enhancement; the static notice still exists without JavaScript. A server repeat of these checks protects API submissions, but cannot replace the client timing requirement. The system never claims to call or notify emergency services.

## Decision table (highest matching priority wins)

| Rule | Actual predicate | Result | Explanation template |
|---|---|---|---|
| E01 | Any structured current emergency answer is `yes` or `unsure`. | Show `emergency_guidance` immediately. | “You answered {answer} to {question}. Under demo rule E01, contact local emergency services now; do not wait for this form.” |
| E02 | Local contextual guard identifies explicit/possible current emergency wording; a valid assessment marks a specified current warning `present` or `possible`; or a direct assessor selects emergency. | Show `emergency_guidance` as soon as the signal is available. | Identify the actual input/selected warning and rule. A model-only alert is explicitly an automated suggestion, not confirmation. |
| H01 | Required request information missing, incomplete or unclear, including unanswered checks and neither preferred times nor explicit no-preference. | `same_day_human_review`; clarification optional. | “Information needed for this request is missing or unclear: {field IDs}. Staff review is needed.” |
| H02 | Self-report is `urgent` or `unsure`. | `same_day_human_review`. | “You selected {status}; demo rule H02 requests human review.” |
| H03 | Contradiction, unknown/unsupported intent, unsupported population/language, indeterminate warning meaning, or unresolved relevance/currentness. | `same_day_human_review`; a *possible current emergency* is E02 instead. | Show actual conflict/scope/uncertainty flags without clinical inference. |
| H04 | AI mode has timeout, unavailable/error response, malformed schema, missing expected assessment, invalid values, unsupported evidence ID or stale response. | `same_day_human_review`, mode `degraded`. | “Automated assessment unavailable or unusable; staff review is needed.” |
| H05 | Valid direct result is same-day or defer, or decomposed result indicates review, or assessor cannot affirm eligibility for routine. | `same_day_human_review`. | Show actual selected action/assessment, version and rule. |
| R01 | Supported scope, all structured checks explicitly no, self routine, sufficient information, supported appointment intent, no contradiction/warning, no higher rule, and usable assessor supports routine. | Provisional `routine_appointment` suggestion. | “The recorded inputs meet the demonstration routine-routing conditions. Staff must review and arrange an appointment.” |

H01–H05 may all match; retain all matches and select a stable reason order. Do not short-circuit the emergency client path on an H rule. If E01/E02 matches, incomplete information remains incomplete; the highest-priority action is still emergency guidance. If no rule can safely establish R01, H05 applies. Every `unknown` has an explicit fallback.

For the no-AI arm, the structured policy checker supplies the assessor slot, with known scope and completeness from fields, local emergency guards and no statistical judgment. If its structured routine conditions pass, R01 may suggest routine while displaying “free text awaiting staff review.” It must not claim to have assessed meaning not covered by its checks. Human review is required in all arms; quantify this baseline's missed text warnings and workload instead of assuming it is safer or worse.

## Ordering, revisions and evidence

Evaluate local emergency checks whenever relevant inputs change. A triggered emergency instruction remains visible for that intake session; later model outputs cannot retract it. A person may explicitly correct an answer, but a correction must be recorded as a new revision and the prior alert retained in audit history. For a later request/review, show both versions; do not label a silent downgrade as a cleared emergency.

For backend routing, bind the assessor response to a request revision and hash. Derive independent structured guards first, validate the assessor envelope, record matching rules, select the highest route, and persist suggestion plus events atomically. Never apply a response for an older text revision. Review/booking are separate later events. A model output cannot override a structured warning or upgrade information sufficiency beyond missing required fields.

An invalid model response is never partly trusted to support routine. Invalid evidence citations invalidate the assessment; absent optional citations do not. Existing emergency guards remain in force regardless of model errors. Do not make a free-form diagnostic explanation out of a flagged phrase.

An eventual E02 model alert does not prove the immediate-emergency requirement was met. FX-08, FX-09 and FX-38 intentionally represent model-dependent detection gaps: their eventual route is emergency, but waiting for inference would fail REQ-03. They must remain visible failures in an implementation until an independent immediate path handles the required scenario. A persistent general notice cannot be used to score a missed explicit warning as correctly detected. No universal free-text emergency recognizer is claimed.

## Operational policy

Persisting a request creates queue ownership and a review deadline transactionally, or records the inability to assign coverage. A notification is a separate tracked event. A failed save leaves the UI `not_received`; never show a receipt or imply a staff notification. Emergency guidance remains visible. Allow idempotent retry and offer a configured alternate contact path; in this demo missing contacts are labelled unavailable, not fabricated.

Outside staffed hours, calculate coverage using the configured clinic calendar. Same-day requests must not quietly roll over to the next business day. If no staffed alternate reviewer can meet the target, display “Clinic review is unavailable now” and the approved alternate human-care path. While that path is unconfigured, a synthetic demo may show a labelled placeholder, but real intake is disabled. Escalation timers and supervisor ownership are explicit; delivery failure never pauses an urgency clock. A deadline measures from receipt, not from when a model finally responds.

Staff may override a suggestion with authorization and a recorded reason. Lowering an emergency suggestion requires an appropriately authorized human review of the warning and a second review in the fictional demo policy; it cannot erase guidance already shown. Record disagreement, original action and final staff decision independently. Staff overrides are not automatically training labels or ground truth.
