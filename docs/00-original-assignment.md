# Original assignment and dataset scope

The following is the assignment text the user supplied in the earlier project chat, **Research modern medical triage AI**. It is retained here to separate the assignment from the team's later design decisions.

## Question 4: Medical Appointment Triage and Routing

> Scenario: A community clinic receives appointment requests describing symptoms, preferred appointment times, and whether the request is routine or urgent. Staff need a tool to organise requests for human review without making an automated diagnosis. Design an AI-assisted intake and routing prototype using synthetic patient records only.
>
> Your challenge: Design and implement an AI-based solution that addresses the scenario. Your prototype should meet these requirements:
>
> - Classify requests into administrative categories such as routine appointment, same-day human review, or emergency guidance based on a predefined policy supplied by the team.
> - Show the reason for each routing suggestion and allow staff to override it.
> - Include a safe fallback for unclear or high-risk descriptions and avoid generating a diagnosis.
>
> Expected deliverables: A prototype intake form, transparent routing rules/model, test cases, and a safety note. The prototype must direct emergencies to local emergency services rather than delay care.

## What this means for the dataset

This supplied statement provides no dataset, dataset link, fixed benchmark, or numerical accuracy target. It explicitly asks for synthetic records and test cases. It also leaves the routing policy to the team. This conclusion covers the text above; no separate organizer rubric has been supplied here.

The repository's 44 original fixtures are assistant-authored examples under an illustrative policy, not organizer data. Additional semantic probes and challenge cases are also assistant-authored. The candidate local model was not queried to generate the challenge labels; this does not make them independently clinician-validated ground truth. Their expected actions express the stated policy, not clinical ground truth. Related paraphrases must stay together when creating development and test splits.

## How results should be described

- **Engineering checks:** passing tests establish the tested application's behavior, including persistence, override and fallback contracts.
- **Development route agreement:** matching authored labels measures conformance on examples used during development.
- **Frozen challenge agreement:** fresh examples authored and labelled before a frozen model run provide a stronger generalization check. They are still a small synthetic sample, not clinical validation.
- **100% on a finite suite:** report the numerator, denominator, dataset provenance and actual model version. Do not describe it as universal accuracy.

## Deliverable map

| Assignment requirement | Implementation and evidence |
|---|---|
| Prototype intake form | `static/index.html`, desktop/mobile browser checks |
| AI-based administrative routing | Local Qwen3 model, validated assessments, versioned `clinic/policy.py` |
| Transparent reasons | Exact description excerpts, evaluated policy rules and persisted model records |
| Staff override | Review workspace, version checks, override reason and audit events |
| Unclear/high-risk fallback | Human-review fallback and independent immediate emergency checks |
| No generated diagnosis | Bounded labels and source excerpts; no free-form medical answer |
| Synthetic test cases | Original fixtures, semantic probes and separately recorded challenge results |
| Safety note | [Safety and delivery snapshot](07-safety-delivery.md) and [current report](../reports/submission-report.md) |

The original statement does not require training a model from scratch. This implementation uses pretrained local inference with a transparent team-defined policy.
