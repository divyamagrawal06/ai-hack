# Five-minute submission demonstration

Use the local app only with invented information. Start it using the README command; no API keys are needed for this demonstration. The model dropdown and audit distinguish no AI, replay and live inference.

1. **Show the boundary.** Point to the synthetic-only banner and permanent emergency instruction. Explain that the software handles appointment requests, makes no diagnosis, and never contacts emergency services.
2. **Demonstrate immediate guidance.** Choose fixture FX-08, or type the invented text “I cannot breathe right now.” Guidance appears before submission. Disable browser networking and choose Yes/Unsure on an emergency check: guidance still appears. No receipt or staff-notified claim is created. Choose **New request** to start a separate scenario.
3. **Show the conservative default.** Load FX-01, choose **Structured intake · no AI**, confirm the invented-data checkbox and submit. Receipt means durable local storage. H05 asks a human to interpret the narrative; information sufficiency is unclear. No appointment is booked and no message is sent.
4. **Show transparent replay.** Start a new request, load FX-01 and select Replay. Submit. The recorded authored assessment produces the routine suggestion with R01; the UI says this is not live AI. Expand the reasons. Editing the text prevents reuse of the old replay result.
5. **Review and book.** Sign into Staff workspace as `reviewer` / `demo-reviewer`. Select a request, claim it, choose an administrative action and enter the actual review reason. Save the review. Choose a future synthetic appointment time and confirm. The audit preserves receipt, input, assessment, rules, staff action and booking separately.
6. **Show an override safeguard.** For an emergency request, propose a lower action with a reason. It remains pending until a different `supervisor` / `demo-supervisor` signs in and approves. Previous emergency guidance remains in the history.
7. **Present the results honestly.** Open the submission report and generated evaluation. Explain why the initial structured baseline made five incorrect routine suggestions and why policy 0.3 trades those for more review. State that replay checks verify wiring, not Jev accuracy; live-model comparisons and human participant testing were not performed.

## Optional failure demonstrations

Use a separate database and port so the ordinary demonstration remains intact:

```sh
CLINIC_TEST_FAIL_SAVES=1 python3 -m clinic.server --test-mode --port 8081 --db var/failure-demo.sqlite3
```

Submit an invented emergency request there. The page reports that the request was not received and retains emergency guidance. No false notification or booking is shown. This flag is honored only with explicit `--test-mode`.

For simulated closed-hours coverage:

```sh
CLINIC_DEMO_OPEN=0 python3 -m clinic.server --port 8082 --db var/closed-demo.sqlite3
```

Requests retain their urgency, but the UI says review is unavailable and no alternate contact is configured. The demonstration provides no actual after-hours care service.

## Submission checklist

- Include the ZIP archive, printable report and source, plus generated JSON/logs and screenshots already included in the archive.
- Do not include `var/`, environment secrets or any real records.
- Present the seven-paper review as literature research; do not present published performance as our measured result.
- Describe this as a tested synthetic prototype. No policy approval, clinical pilot, human usability study or deployment claim is made.
