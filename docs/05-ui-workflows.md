# 05 — Prototype form and UI workflows

> **Design snapshot (policy 0.1).** This document preserves the original requirements and proposed contracts. The current runnable implementation, executed checks, research updates and explicit deviations are described in [the submission report](../reports/submission-report.md) and [implementation notes](../reports/implementation.md). Statements below about unstarted work or blocked reading describe the earlier specification stage.

This is a textual wireframe and interaction specification, not an implemented application. All people and requests in demonstrations are invented. No user-facing localhost preview is provided.

## Patient-facing form wireframe

```text
COMMUNITY CLINIC — SYNTHETIC DEMONSTRATION
Use invented information only. Do not enter real patient details.

If you think this may be an emergency, contact your local emergency
services now. Do not wait for this form or a clinic reply.

Appointment request
This form helps staff decide how to handle an appointment request.
It does not diagnose a condition or confirm an appointment.

1. Are any of the following happening now?
   [Each configured warning: Yes / No / Unsure]
   Examples in this demonstration are illustrative, not a complete list.
   [Choosing Yes or Unsure immediately opens emergency guidance below.]

2. Tell us what you would like help with.
   [Symptom description — multiline; 4,000-character limit]
   When did this start? [Today / Earlier / Unsure; optional detail]
   Is it happening now? [Yes / No / Unsure]

3. How soon do you think you need help?
   ( ) Routine appointment  ( ) Urgent  ( ) Unsure
   Your answer helps routing; it does not override emergency guidance.

4. Which times would you prefer?
   [Date/time windows in the configured clinic timezone]
   [ ] No preference
   Preferences do not change how urgently a request needs attention.

5. Demonstration scope
   Age group [Under 18 / 18–64 / 65+ / Unsure]
   Is this request for you? [Yes / No / Unsure]
   Pregnancy/postpartum context? [Yes / No / Unsure / Prefer not to say]
   Language [configured options / Another language]
   Synthetic person ID [generated; no real name required]

[Review request]  [Submit synthetic request]
Submitting requests staff review. It does not book an appointment.
```

The exact scope questions must be reviewed for relevance, accessibility and cultural fit; this is a deliberately narrow fictional policy. “Prefer not to say” preserves missing/unsupported scope and offers human review rather than blocking access. Do not preselect reassuring answers. The warning questions and demo definitions are in [03](03-demonstration-policy.md).

## Emergency interruption

On a yes/unsure emergency answer, show immediately, without submission:

> Contact your local emergency services now. Do not wait for this form, an automated assessment, or a clinic reply. This service does not contact emergency services for you.
>
> This appeared because you selected “{answer}” for “{exact configured question}.” Demonstration rule E01 triggered this guidance.

For a text/model signal use “Your description may need emergency attention” and identify the actual source of the suggestion without naming a diagnosis. The displayed explanation is a fact about an input and rule, not a declaration that the symptom proves a disease. A valid model-selected emergency with no optional evidence IDs can show its recorded action and E02, but cannot invent a supporting quotation. Supplied invalid IDs invalidate the assessment and invoke H04; independently triggered emergency guidance remains in force.

The alert is in normal document flow near the relevant input, announced accessibly, keyboard reachable and visible without color. It does not trap the user in a modal or require “I agree” before help. Any configured call action is immediately available. Do not hide the persistent notice behind cookies, login, completeness validation, consent to AI or staff availability. A person can stop without submitting. In this synthetic demo there is no active telephone or messaging integration.

No-JavaScript rendering preserves the static notice. A JavaScript-based structured response cannot be promised when JavaScript is unavailable; demonstrate that limitation honestly. The no-JavaScript fallback should advise immediate contact for any listed concern, and the normal structured workflow requires an accessible functional client. During implementation validate client failure, partial render and delayed asset loading explicitly.

## Submission and receipt states

| Actual state | Exact intended meaning / example copy | Forbidden implication |
|---|---|---|
| Editing / not submitted | “Your request has not been sent.” | No staff notification or receipt. |
| Submit pending | “Sending your request…” Emergency notice remains visible. | No success until durable receipt. |
| Save failed | “Your request was not received. Try again or use the configured alternate contact.” | Never “Staff have been notified.” |
| Response lost / receipt unknown | “We cannot yet confirm whether your request was received. Check status or retry safely.” | Do not confidently assert failure or duplicate a request. |
| Received, assessment pending | “Request received. Assessment pending. No appointment is booked.” | Receipt does not equal review. |
| Assessment complete | “Suggested next step: {route label}. Staff review status: {actual status}.” | Automated suggestion does not equal staff approval. |
| Degraded assessment | “Automated assessment unavailable. Human review is needed.” Show actual coverage and delivery status. | A timeout is not a routine assessment. |
| Staff reviewed | “Staff reviewed your request at {time}. {Recorded next step}.” | Review is not booking. |
| Confirmed booking | “Appointment booked for {slot and timezone}.” | Only after a booking record exists. |
| Coverage unavailable | “Clinic review is unavailable now. {Approved alternate care route}.” | No promise of same-day attention or instruction simply to wait. |

If receipt succeeds but a notification fails, say the request was received and accurately show that alert delivery is unconfirmed/failed. Do not expose internal exception text or API keys. In an unconfigured synthetic demo, state “Alternate contact not configured in this demonstration”; a real workflow is blocked until that path exists.

## Transparent suggestion panel

Example for invented non-emergency urgent input:

```text
Suggested next step: Same-day human review
Status: Request received; awaiting staff review; not booked
Mode: Replay — saved synthetic assessment, not a live model call

Why this appeared
• You selected “Urgent.”
• Demo rule H02 requires human review for that answer.
• Your preferred time is stored as a preference and did not lower priority.

Information: Sufficient for the demonstration's routing questions.
Policy: demo-policy-0.1
This is an administrative suggestion, not a diagnosis.
```

Use the same template system for live/degraded/no-AI modes. Show uncertainty explicitly, not as a reassuring percentage. A “why” panel can expand exact field values, validated sentence references and fired rules. The ordering must match execution. Staff-only audit details include raw output, rejected outputs and model versions; patient-facing text stays concise and avoids jargon. Escape all text; never render prompt injections as UI instructions.

## Staff queue and review

The queue separates **suggested action**, **delivery/coverage status**, **review deadline**, **owner**, and **review state**. A routine suggestion with an operational failure must remain visible; a same-day suggestion with no reviewer is an escalation, not a hidden waiting item. Sort by policy priority and deadline, with a defined stable tie-breaker. A preferred appointment date does not influence priority.

Each review screen presents original input first, structured answers, request revision, actual suggestion and rule trace, model/fallback mode, missing/contradictory fields, warning history, and prior staff actions. An expandable section holds probabilities with their actual semantics; no green “clinically safe” badge or probability-of-safety wording. Do not hide the original text behind an AI summary.

Reviewer actions: claim; request clarification; record contact; confirm/correct structured facts; choose an administrative action; escalate; propose/confirm booking; hand off. Clarification never suspends an emergency warning or resets a deadline. A handoff requires receiving ownership or explicit supervisor escalation. Staff absence, lease expiry and overdue tasks are visible.

Override form: selected action, structured reason (`incorrect_input_interpretation`, `new_information`, `policy_exception`, `coverage_issue`, `other`), bounded explanation, relevant corrected fields, actor and expected record version. Do not lower urgency merely because no slot exists. A lower emergency action requires the demo's authorized second review. Preserve the original suggestion and emergency guidance event.

For a concurrent update: “This request changed while you were reviewing it. Your change has not been applied. Review the latest decision before resubmitting.” Show the conflicting decisions; never silently overwrite. A failed save keeps the override draft visibly unsaved.

## Accessibility and comprehension checks

Test keyboard order, labelled inputs/errors, screen-reader announcement of the emergency alert, readable focus, zoom/reflow, reduced motion, understandable plain language, and no reliance on color. Use participant tasks that ask whether a request was received, reviewed or booked. Include users who select routine while describing a warning, or choose next week because work is difficult; verify preferences cannot suppress guidance.

Language scope must be visible. Unsupported language goes to an accessible human route; do not silently translate with an unvalidated model and treat the result as supported. Jurisdiction is an explicit clinic setting; the user's timezone does not configure emergency numbers.
