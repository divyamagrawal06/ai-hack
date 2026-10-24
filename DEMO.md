# CareRoute: three-minute demo

Start with `python -X utf8 tools/start_demo.py` or double-click **Start CareRoute.cmd**. Open http://127.0.0.1:8080. Keep the laptop plugged in for GPU inference.

## 1. Show a real local model

Point to the model panel: it reports the installed model and connection to Ollama. Explain: "The request is read on this laptop. There is no cloud model or API key in this flow."

Click **Routine visit**, then edit a few words if desired. The scenario button fills invented inputs; it does not load a saved AI answer. Submit the request. The receipt appears first, then the fresh model result. Show the exact excerpts, model name, token count and measured inference duration.

## 2. Complete the staff workflow

Open **Staff workspace**. Sign in with `reviewer` / `demo-reviewer`. Select the request. Compare the original description, AI-selected excerpts and six structured assessments.

Save a human review with a short reason. Choose a future appointment time and confirm the synthetic booking. Open the audit history to show the actual request, raw model output, policy decision, review and booking events.

The model proposes a handoff; a human completes the booking. No external appointment or notification is created.

## 3. Show a different outcome

Return to intake. Choose **Needs attention** and submit: the request should call for human review under the demo policy. Choose **Immediate concern** to show that the emergency notice appears immediately, before submission or AI inference.

For a model-understanding example, edit an invented description while leaving the selected form answers consistent. The model should assess the new wording afresh. Its output is a prototype suggestion, so show the original text and staff review alongside it.

## 4. Explain failure honestly

The test suite also exercises a disconnected model. CareRoute retains the saved request, labels the AI as unavailable and sends it for staff review. It never substitutes a canned success. The default no-AI baseline, available in advanced controls, demonstrates the difference: ordinary narratives remain unassessed and go to human review.

## Useful answers for judges

- **What is AI here?** A local Qwen3 4B Instruct model performs six structured semantic assessments and selects exact evidence excerpts.
- **What is deterministic?** Input validation, immediate warning checks, routing precedence, excerpt validation, persistence, permissions and booking transitions.
- **Why local?** No hosted inference cost or key is needed for the demo; inputs stay on the laptop in local mode.
- **Can it handle real patients?** This demonstration uses invented records and an illustrative policy. Clinical validation, approved scope, real authentication and operational integration are outside this submission.
- **How is it tested?** Automated API/policy contracts, real Chrome workflows, actual local-model runs and saved failure-inclusive results. See the current submission report for measured outcomes.
