# 04 — System and data contracts

> **Design snapshot (policy 0.1).** This document preserves the original requirements and proposed contracts. The runnable policy 0.3 implementation, executed checks, research updates and explicit deviations are described in [the submission report](../reports/submission-report.md) and [implementation notes](../reports/implementation.md). Statements below about unstarted work or blocked reading describe the earlier specification stage.

These are implementation specifications, not implemented APIs. Version all contracts (`contract-0.1` initially). Examples and fixtures contain invented data only. Unknown enum values, absent required keys, duplicate keys, unexpected question IDs, non-finite numbers and unapproved versions must be rejected; do not coerce them into a safe-looking default.

## Data inventory and separation

| Entity | Required content | Invariant |
|---|---|---|
| `RequestRevision` | request/revision IDs; synthetic marker; original symptom text; submitted structured answers; preferred windows and timezone; client event IDs; received time | Original text immutable. Corrections create revisions. Server assigns authoritative receipt time only after durable save. |
| `TextSegmentation` | input revision/hash; segmenter version; ordered sentence IDs with start/end offsets and exact text | Preserve original text; define offsets as Unicode code-point offsets, end-exclusive. IDs cannot be reused across text revisions. |
| `AssessmentAttempt` | arm; mode; request revision/hash; timestamps/deadline; requested and returned model IDs; SDK/prompt/questions hash; raw request excluding credentials; raw response; validation result; parsed outputs; latency/failure | An attempt is not a successful assessment. Capture raw output before SDK transformations if supported; otherwise record that raw capture is unavailable and fail the audit gate. |
| `PolicyDecision` | route; information status; actual guards and matching rule IDs in priority order; selected rule; input/assessment references; policy and contract versions; explanatory template keys and arguments | Reproducible from saved inputs; no generated clinical rationale. Store model's raw proposal separately from final route. |
| `QueueItem` | owner team/person; coverage decision; due time; acknowledged/reviewed times; escalation state; durable notification events | Receipt and ownership independent of model success. No unowned item silently waiting. |
| `StaffReview` | actor/role; expected row version; prior decision; override/correction; reason code and bounded comment; secondary review where required | Append-only audit; no last-write-wins safety changes. Staff input is not automatically model ground truth. |
| `Booking` | confirmed appointment ID, slot/timezone and staff actor; notification result | Booked status requires confirmation, not a route recommendation. |
| `AuditEvent` | unique event ID; correlation/request/revision IDs; actor; timestamp; event type; before/after references; policy/model versions | Ordered per request using server sequence, not client clock alone. Do not put API keys or authentication headers in events. |

Use explicit synthetic contacts such as `patient-001@example.test`; do not send messages. Logs and exports carry a synthetic-only marker. Text must be escaped when displayed; patients' or fixture authors' text never becomes system instructions. Access scope is per role, not a shared public audit screen.

## Intake contract

`symptom_text` is the exact submitted string, with a proposed 4,000-character limit and clear overflow handling. `self_reported_urgency` is `routine|urgent|unsure`. `preferred_times` is an array of windows with timezone or an explicit no-preference marker. A missing preference can be clarified but is not evidence for lowering urgency. `emergency_answers` contains versioned question IDs and `yes|no|unsure|unanswered`. Onset/currentness and requester relationship are explicit fields.

Age band is the UI default. Some fixtures use invented `age_years` for exact boundary testing; an implementation adapter maps those to policy bands without collecting real birth dates. The fixture shorthand `language=en`, `requester=self`, `pregnancy_postpartum=false` expresses demo scope; unknown values remain unknown. Fixtures use a reduced `onset_currentness` guard input and do not exercise separate onset/currentness form-field serialization; T-05 must test those fields independently in the implementation. Defaults documented by a future fixture harness are test setup, not defaults the patient UI may silently assume. A missing scheduling response (neither windows nor explicit no preference) invokes H01 in this conservative demonstration policy; measure the resulting extra review burden.

Input validation returns field errors without hiding emergency guidance. Unsupported characters/languages are preserved and flagged, never stripped into a different symptom statement. No silent truncation. Repeat submissions use an idempotency key bound to a payload hash; the same key with different content is a conflict.

## Assessment adapters

The application-normalized contract below is **not a claimed native Jev response schema**. Each adapter must map a verified vendor response into it, preserve the original, and report any unsupported fields.

| Field | Values and use |
|---|---|
| `warning` | `current_present|current_possible|absent|unclear_non_emergency`; present/possible activates E02. Generic indeterminate meaning activates H03, not an assertion of absence. |
| `warning_checks` | Optional per-policy warning answers with stable IDs; if required by a selected prompt version, every expected answer must be present. |
| `intent` | `appointment_request|other|unclear`; only the first is routine eligible. |
| `information_sufficiency` | `sufficient|insufficient|unclear`; separate from warning and route. |
| `missing_fields` | Application-known missing field IDs plus separately marked model-suggested omissions; a model cannot fill required inputs by inference. |
| `contradiction` | `true|false|unclear`, plus pairs of actual field/sentence IDs if collected. |
| `scope` | `supported|unsupported|unclear`; combines configured deterministic checks and assessor flags without overriding known exclusions. |
| `human_review_indication` | `true|false|unclear`; unknown is review. |
| `direct_route` | For B: `routine_appointment|same_day_human_review|emergency_guidance|defer`. A/C/D may omit this field; a replay fixture may contain both for comparison. |
| `selected_sentence_ids` | Optional IDs selected by finite questions; verify revision, existence and substring. Never invent spans/prose to satisfy the contract. |
| `native_outputs` | Probabilities/confidence/usage exactly as returned and labelled with their semantics; absent values remain absent. |

For C and D, freeze the same questions: is a specified warning current/potentially current; is the intent a supported appointment request; what required information is absent; are statements contradictory; is scope supported; is human review indicated. Use distinct criteria for “no evidence supplied” and “evidence of absence.” Do not collapse time/history, third-person statements or quotes into current symptoms. This is a question-design requirement, not proof the model follows it.

For B, use an explicit four-choice task with the full approved policy and defer criteria. Do not require the decomposed fields as hidden prerequisites. Application-required completeness and scope checks remain shared. A separate sufficiency Noul/Choice is an experimental ablation with separate results. No candidate may supply diagnoses, treatment instructions or arbitrary reasons through the UI contract.

For Jev Choice, validate answer type, exact labels and probability-key set, finite values in [0,1], sum within a documented numeric tolerance (proposed 1e-3), confidence range where supplied, and consistency of the selected label with vendor semantics including tie handling. These numeric checks validate format, not calibration. For Noul validate a finite scalar in [0,1]; any mapping thresholds are versioned and experimental. Do not assume an HTTP timeout bounds end-to-end latency: enforce the 10-second demo deadline across retries and calls. A late response is archived as late, not applied.

## State and transaction semantics

Keep these independent dimensions:

| Dimension | States |
|---|---|
| Persistence | `not_received`, `received` |
| Client receipt observation | `not_sent`, `sending`, `confirmed_not_received`, `confirmed_received`, `receipt_unknown` |
| Assessment | `not_started`, `pending`, `complete`, `degraded`, `stale` |
| Human review | `unassigned`, `assigned`, `acknowledged`, `reviewed`, `overdue`, `coverage_unavailable` |
| Booking | `not_booked`, `pending_confirmation`, `booked`, `cancelled` |
| Notification | `not_attempted`, `pending`, `delivered`, `failed`, `unknown` |
| Mode | `no_ai`, `live_model`, `replay`, `degraded` |

`live_model` means an actual recorded successful model response is being used. While a call is pending, show “assessment pending,” with the configured arm recorded separately. Fallback from a configured live arm is `degraded`. Replay identifies the source fixture/output ID and displays “saved synthetic result.” A saved request can be pending assessment and not booked simultaneously.

Proposed API surface: `POST /requests` atomically persists input and queue/outbox records and returns a durable receipt; `GET /requests/{id}` exposes authorized status; `POST /requests/{id}/revisions` preserves corrections; `POST /queue/{id}/claim` atomically claims; `POST /requests/{id}/reviews` requires `expected_version`; `POST /requests/{id}/bookings` records a confirmed staff booking. No endpoint performs diagnosis. Emergency guidance does not depend on any endpoint.

Response lost after commit is an unknown receipt state, not a confirmed failure: offer an idempotent receipt lookup/retry; do not make duplicate requests. Failed persistence cannot produce successful delivery text. A transactionally recorded notification intent is not delivery evidence. Durable outbox retries are idempotent, bounded and observable; failure escalates to an operational owner. Simulated delivery is labelled simulated.

Concurrent overrides return a conflict (proposed HTTP 409) with the latest version; the reviewer reloads and reconciles explicitly. Queue claims have expiring leases and safe reassignment. Emergency routes are never automatically downgraded by late model output or a stale revision. Corrections, re-runs and policy migrations are new audit events; preserve what the user saw under the previous policy.

## Failure contracts

If the model fails, record H04 and degraded assessment status while retaining all independently observed E/H matches and the policy's reason order. Never use valid-looking fragments of an invalid model envelope to establish warning absence, sufficiency or routine eligibility. If initial persistence fails, ordinary model processing does not start; there may be no route decision (`null`, not a fourth route) while immediate emergency guards still operate. If policy/configuration is invalid, disable live routing and show human contact guidance; do not fall back to unspecified clinical logic. If staff coverage is unavailable, preserve the suggested route and report service unavailability with configured alternate care instructions. If all persistence is down, emergency guidance still works and no audit durability or staff notification is claimed. Preserve a local event only where safe and possible; do not claim a saved server audit from an unsaved browser event.

No integration credentials, environment changes or installed model SDK are required for reviewing this package. Future experiments must use synthetic inputs and isolated credentials, record versions, and follow the release gates in [07](07-safety-delivery.md).
