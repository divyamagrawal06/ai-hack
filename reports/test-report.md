> **Historical baseline report.** These sections describe the pre-local-AI tests. For the current build, use [the submission report](submission-report.md), [current automated results](generated/test-results.json), [current browser results](generated/browser-results.json), and the live-model evidence linked from the submission report.

# Executed verification and requirement coverage

Final policy: **demo-policy-0.3**. Detailed outcomes are stored in [test-results.json](generated/test-results.json), [tests.log](generated/tests.log), [browser-results.json](generated/browser-results.json) and [evaluation.json](generated/evaluation.json). No model service was called during these runs.

## Results

| Suite | Executed result | Scope |
|---|---|---|
| Python unittest suite | **122 passed; 0 failures/errors/skips** | 75 policy tests, 28 HTTP/storage tests, 17 mocked provider-contract tests, 2 evidence-provenance tests |
| Actual Chromium browser checks | **12 groups passed; 0 failed** | UI actions with the actual local service and temporary databases |
| Fixture route replay | **43/43** (included in the policy suite) | Original authored expectations; FX-31 has no decision and belongs to persistence tests |
| Live Jev/LLM comparison | **Unrun** | No credentials configured; mock/replay tests are not substitutes |
| Human usability/screen-reader study | **Unrun** | Basic labels, keyboard skip link, alert semantics and mobile layout checked; no participant conclusions |
| Clinical validation | **Unrun** | Illustrative policy and synthetic inputs only |

Actual browser coverage includes the notice with JavaScript disabled; client/server guard parity for 44 descriptions; six structured checks with both Yes and Unsure offline; independent local handling of FX-08/09/38; negation/history; persisted replay receipt; changed-input replay rejection; staff login/review/booking/audit; actual failed-save response; 390px layout; basic labels/keyboard semantics; and no uncaught JavaScript errors. Measured synchronous emergency-handler observations are in the JSON, including the maximum 12.5 ms for this run. This is not a clinical response-time or comprehension claim.

## Faults and fixes found during development

- Initial no-AI routing gave five incorrect routine suggestions on comparable authored nonroutine examples. Policy 0.3 instead requires human narrative interpretation, increasing escalation and same-day review demand; previous results remain under `reports/iterations/`.
- A negated phrase (“I do not have severe chest pain”) initially triggered the demo text guard. The prefix handling was corrected and the browser regression passes. Historical context followed by a current warning is checked separately.
- Input corrections could leave a stale routine suggestion/booking until assessment finished. Revisions now run independent emergency checks immediately and invalidate stale review/booking.
- Pending assessments could block human review. Staff can now take over; late results are rejected.
- Retried submissions and stale async responses could bind the wrong inputs/receipt; generation guards and payload-bound idempotency preserve the actual request.
- Concurrency conflicts and uncertain staff acknowledgments now preserve the draft and distinguish rejection from unknown save state.

These are addressed implementation defects, not evidence the phrase detector or workflow is universally safe.

## Requirement traceability to implemented evidence

| Requirement | Executed evidence | Remaining boundary |
|---|---|---|
| REQ-01 synthetic only | Invented fixture provenance, synthetic declaration API check, packaged screenshots | Arbitrary text is not automatically proven free of real information |
| REQ-02 intake | Browser submission and preserved JSON inputs; preference invariance tests | No real scheduling/clinic integration |
| REQ-03 immediate emergency | Offline 12 structured combinations, three former gaps, no-JS notice, actual failed-save browser path | Bounded language examples; no universal detector or human-action evidence |
| REQ-04 administrative only | Route enums, provider schemas, fixed reasons, no diagnosis UI | Not a clinical triage tool |
| REQ-05 independent sufficiency | Missingness, invalid output, unknowns, direct guard and no-AI H05 tests | Live semantic judgment quality unmeasured |
| REQ-06 actual explanations | Rule matches, original text, Unicode offset tests and browser audit | No model-selected evidence spans; semantic evidence selection untested |
| REQ-07 audit/versioning | Append-only SQL triggers, input revisions, raw/rejected output provenance, restart recovery | Database administrator/filesystem tampering is outside local-demo protection |
| REQ-08 overrides/concurrency | CAS conflict, explicit reason, different-supervisor emergency downgrade, late-output rejection | Production identity/governance not implemented |
| REQ-09 service failure | Missing keys, malformed/duplicate/nonfinite output, provider failures, total deadline, manual takeover | Real vendor access/rate limits untested |
| REQ-10 receipt/delivery truth | Failed save, lost-response retry/idempotency, no false notification and receipt-token tests | Notification delivery is simulated; no real transport |
| REQ-11 coverage/ownership | Queue claim, expiry, overdue sweep, closed-hours/unavailable coverage tests | UTC weekday simulation only; no approved contacts/holidays/DST service calendar |
| REQ-12 distinct status | Receipt, assessment, review and booking tested over HTTP and browser | Synthetic appointment inventory only |
| REQ-13 jurisdiction/scope | Scope/unknown tests, explicit unconfigured jurisdiction and fictional clock | No actual clinic jurisdiction approved |
| REQ-14 modes | No-AI/replay/degraded tests, exact-input replay rejection; mocked live normalization | Successful live-mode behavior not verified against providers |
| REQ-15 fair comparison | Reproducible baseline results, honest replay denominators, archived initial failures and evaluation protocol | Four-arm live experiment/calibration not run |
| REQ-16 accessibility | Labels, alert roles, keyboard skip link, no-JS notice and mobile overflow checks | Full WCAG/screen-reader/human usability audit unrun |
| REQ-17 privacy | No credentials in output, bounded input, receipt authorization, local-host/Origin/CSP checks | Production retention/vendor/privacy assessment unrun |
| REQ-18 gates | Synthetic-only notices and explicit unresolved approvals in reports | Clinical/operational sign-off not supplied |

Original T-01–T-22 are a broader planned catalogue. The checks above cover the implementation-relevant subsets; they do not reclassify the full human studies, live-model experiment, deployment audits or every hypothetical failure injection as passed. T-19 live comparison and T-20 participant study remain unrun. T-17 accessibility, T-18 governance and T-10 clinical calendar coverage remain partial.

## Reproduce

From the project root run `python3 tools/run_checks.py`, `python3 tools/evaluate.py`, and—with Playwright/Chromium installed—`python3 tools/browser_check.py`. The API/browser suites allocate temporary databases; no persistent demo records or user files are deleted. Each script preserves failures and exits nonzero on a failed relevant check. The evaluator deliberately reports safety/workload metrics even when authored-label mismatches occur; those mismatches are results rather than infrastructure exit failures.

Current policy tests passed after the recorded fixes. No unexecuted command is counted as a test, and no published paper's result is included in these pass counts.
