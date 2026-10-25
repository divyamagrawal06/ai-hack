> **Local-AI update, 25 October 2026.** The sections below preserve the earlier implementation notes. The current default is `local_ai`, implemented in `clinic/assessors.py`, and the current report/evidence are in [the submission report](submission-report.md).

## Current local AI integration

- Current policy is `demo-policy-0.4`: a validated primary warning survives a later verifier failure, but a partial result cannot establish routine eligibility. The first frozen challenge used policy 0.3; that original result and source snapshots are preserved separately.
- `GET /api/ai/status` probes the actual local Ollama model without generating text. It reports ready, offline, model missing or invalid configuration.
- `POST /api/requests` defaults to `local_ai`; the request is saved before inference. The six enum assessments and exact source excerpts are validated before routing.
- Public request receipts include a compact `ai` object: provider, local flag, model, status, inference duration, token counts, exact excerpts and any failure. The authenticated staff view retains the full raw prompt/response, model digest and prompt hash.
- `CLINIC_LOCAL_MODEL` defaults to `qwen3:4b-instruct`; `CLINIC_OLLAMA_URL` accepts literal loopback HTTP addresses only. Cloud Ollama models are refused in local mode. The transport bypasses system proxies and refuses redirects.
- Local inference has a 90-second total wall deadline and a semaphore serializing complete pipelines. The primary assessment and subsequent attributed assessment have 512-token output budgets. Timeline claim extraction and conditional source attribution have 768-token budgets. Busy, offline, malformed or timed-out requests visibly defer to staff, preserving any validated primary emergency warning. There is no authored-response substitution.
- A focused timeline check can add a conflict/human-review indication. When no independent emergency guard applies and the primary model signals a warning, source attribution distinguishes actual and fictional text. If both exist, an additional assessment of the actual excerpts can replace a false model warning with human review. It cannot suppress independent emergency checks or turn a disputed emergency into routine. Every verifier response and reconciliation is retained; public token counts sum all calls.
- Primary and attributed assessments select application-generated source IDs mapped to exact input spans. Timeline verification extracts source-linked timing claims, then compares their episode relationships across the description and structured onset. Evidence identifies its source field. Trusted form scope and completeness correct contradictory model flags, with the raw model judgment and reconciliation preserved.
- Staff detail automatically refreshes after pending AI completes; review and booking drafts survive refreshes. Original text, model findings and human decisions remain distinct.
- The launcher discovers the portable runtime or an existing Ollama installation. The Windows setup verifies pinned runtime files and the executable signature, enables Vulkan and downloads the model. Runtime/model files and SQLite are excluded from the submission ZIP.
- SQLite connections now close reliably on Windows; browser tooling discovers installed Chrome or Edge.

## Earlier implementation notes

# Implementation and reproducibility notes

Earlier snapshot policy: **demo-policy-0.3**. Runtime: Python 3.11+ standard library, SQLite, static HTML/CSS/JavaScript. These earlier tests ran on Python 3.12 with Chromium through Playwright. No build pipeline or third-party runtime install is required.

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
