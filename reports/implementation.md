# Implementation and reproducibility notes

Current runnable policy: **demo-policy-0.3**. Runtime: Python 3.11+ standard library, SQLite, static HTML/CSS/JavaScript. Tests ran on Python 3.12 with Chromium through Playwright. No build pipeline or third-party runtime install is required.

## Components and flow

`static/index.html` contains the emergency notice before scripts run. `static/app.js` independently checks six structured questions and a bounded contextual phrase set on input. It never waits for validation, save, model or staff review to display guidance. The server mirrors these guards in `clinic/policy.py`; parity is tested across all 44 invented descriptions. Negation, historical clauses, quoted fiction and a later current warning have explicit regression examples. This finite phrase set cannot recognize all medical emergencies.

`clinic/server.py` exposes local HTTP endpoints and starts assessment only after receipt/queue persistence succeeds. `clinic/storage.py` uses SQLite transactions, input hashes/revisions, an idempotency table, append-only audit triggers and version-based concurrency checks. Workers resume durable pending tasks after restart. Human review can take over a pending model assessment; a late model result cannot overwrite it. A changed input invalidates the prior review/booking and receives independent emergency checks immediately.

`clinic/assessors.py` implements no-AI, exact-fixture replay, direct Jev, decomposed Jev and structured-output LLM adapters. Live calls have a ten-second wall-clock deadline, fixed HTTPS destinations, verified TLS, no redirect credential forwarding and no automatic retries. Invalid output never partly supports routine. Raw outputs, response text where received, rejected-output representations, question hashes, requested/returned model identity and error status are retained without authorization headers. A late result discarded after timeout is not falsely claimed to have been persisted.

## Rules and evidence

E01 is immediate structured yes/unsure guidance. E02 is an independent local current-warning signal or valid model emergency signal. H01 handles required missing/unclear input, H02 urgent/unsure self-report, H03 scope/conflict/unclear intent, H04 unusable model output, H05 human review/defer, and R01 eligible assessed routine. All matches are retained with fixed precedence. Information sufficiency, route, persistence, review, booking and notification are separate fields.

In policy 0.3, **no-AI H05 defers ordinary unreviewed narrative to staff**, even when structured fields are complete. This responds to observed incorrect routine suggestions, not a failed provider. Live direct Jev remains a direct choice with defer, not hidden decomposition; common form and emergency guards still apply.

Explanations are fixed templates populated from actual fields, assessed labels and executed rules. Original text and application-generated sentence IDs/Unicode offsets are preserved. Adapters do not request or manufacture evidence spans or medical prose; selected-evidence IDs are explicitly empty. The UI shows original text and rule facts, not a generated medical explanation. Valid source locations alone would not prove semantic support if evidence-selection is added later.

Client-reported earlier emergency guidance is bounded, labelled unverified history and conservatively retained. It cannot silently become routine after a user edits the current answer. Independent server findings remain distinct. A staff downgrade of emergency guidance needs a different supervisor and a reason; historical guidance is never erased.

## API surface

Mutations use JSON. The server rejects cross-origin/non-loopback Host requests, duplicate JSON keys, unexpected input fields, malformed enum types, non-finite numbers and oversized input. It serves only whitelisted static extensions under `static/`.

| Endpoint | Behavior / access |
|---|---|
| `GET /api/health`, `/api/config`, `/api/fixtures` | Local health, nonsecret configuration and invented scenarios |
| `POST /api/requests` | Synthetic declaration, inputs, variant and optional fixture ID; `Idempotency-Key` required; durable receipt/token |
| `GET /api/requests/{id}?receipt=…` | Receipt token required; raw assessment/audit internals withheld |
| `POST /api/login`, `/api/logout`; `GET /api/session` | Demo accounts, HttpOnly SameSite session cookies, expiry |
| `GET /api/queue`, `/api/requests/{id}/audit` | Staff session required |
| `POST /api/requests/{id}/claim` | Atomic ownership claim with `expected_version` |
| `POST /api/requests/{id}/review` | Action, reason, comment and expected version; explicit manual takeover allowed |
| `POST /api/requests/{id}/approve-override` | Different supervisor approves pending emergency downgrade |
| `POST /api/requests/{id}/book`, `/cancel-booking` | Review/confirmation required; explicit timezone; separate booking state |
| `POST /api/requests/{id}/revisions` | Staff correction with new revision and preserved original; immediate emergency guards |

No API calls an EHR, clinic contact, messaging provider or emergency service. Notification status is `simulated`, never delivered. There is no real appointment inventory; booking is a synthetic demonstration record. Known failed saves and lost acknowledgments have different UI messages. Receipt retries use the same key; edits after an uncertain receipt cannot silently create a new request. Concurrent staff updates return 409 and preserve the user's draft.

## Scope and configuration

The demonstration's supported routine scope is self-request, English, age 18–64, without pregnancy/postpartum context. Unsupported or unknown values go to review; emergency guidance takes priority. These boundaries and six warning examples are illustrative, not clinical guidelines. `UTC` is a fictional scheduling clock, not inferred jurisdiction. Review targets are simulated 30 minutes for urgent/emergency work and two weekdays for routine; the sweeper handles overdue items and expired claims. There is no holiday/location-specific clinical calendar.

`CLINIC_DEMO_OPEN=0` or `CLINIC_DEMO_REVIEWER_AVAILABLE=0` simulates unavailable coverage. No alternate real care contact is configured. `CLINIC_TEST_FAIL_SAVES=1` takes effect only with `--test-mode`. Live credentials/model settings are described in README; values never belong in the submission.

Reusable startup instructions and optional secret requirements were saved to the cloud environment draft. `api.typesafe.ai` and `api.openai.com` were added as secret destinations. Review/save these settings and publish the environment to activate the saved configuration; saving a draft does not publish or supply credential values. There is no installation script because the runtime has no third-party dependencies. The submission archive runs independently of cloud publication.

## Version history and deviations

| Version/stage | Difference and evidence |
|---|---|
| Original 0.1 specification | No implementation; 44 authored fixtures including three model-dependent emergency timing gaps. Preserved unchanged. |
| Initial 0.2 implementation | Local detection for FX-08/09/38 and actual workflow. Structured-only baseline still proposed routine for five nonroutine authored expectations. Original run archived under `reports/iterations/`. |
| Final 0.3 | No-AI narrative review required; evaluation records the escalation/workload cost. Negation, stale async UI, manual takeover and correction/booking hazards received regression fixes. |

Some design features remain outside this local synthetic submission: real notifications, approved alternate-care contacts, clinical calendar/jurisdiction, production authentication/TLS, real appointment inventory, a broad emergency recognizer, live evidence-selection and real-data integration. Staff input revisions and booking cancellation have tested APIs; the main UI concentrates on intake, review, override, booking and audit. This is documented scope, not a claim all conceptual features were clinically deployed.
