#!/usr/bin/env python3
"""Build the current submission report from recorded, actually executed checks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def ratio(value):
    return f"{value['numerator']}/{value['denominator']}"


def main():
    tests = read('reports/generated/test-results.json')
    browser = read('reports/generated/browser-results.json')
    live_browser = read('reports/generated/browser-live-results.json')
    probes = read('reports/generated/local-probes.json')
    runtime = read('reports/generated/local-runtime.json')
    if probes.get('state') != 'complete':
        raise SystemExit('Complete the actual semantic probes before building the report.')
    probe_archives = sorted((ROOT/'reports/generated/local-probe-runs').glob('*.json'))
    first_probe = json.loads(probe_archives[0].read_text(encoding='utf-8')) if probe_archives else probes
    iteration_note = (f"The first prompt passed {first_probe['passed_attempts']}/{first_probe['completed_attempts']} "
        f"semantic probes. The prompt was refined using these visible examples, and the current run passed "
        f"{probes['passed_attempts']}/{probes['completed_attempts']}. Earlier attempts remain archived. "
        "Both the original cases and these extra probes informed development; neither set is held out.")
    auxiliary_notes = []
    for row in probes['attempts']:
        fields = row['attempt'].get('assessment') or {}
        if row['id'] == 'LP-06' and fields.get('human_review_indication') is False:
            auxiliary_notes.append('The unsupported-scope probe still had an incorrect additional-review flag.')
        if row['id'] == 'LP-07' and fields.get('contradiction') is False:
            auxiliary_notes.append('The warning-paraphrase probe missed the contradiction with all-no form answers.')
    auxiliary_note = ' '.join(auxiliary_notes) or 'All intermediate judgments remain visible in the raw record for staff verification.'
    runs = sorted((ROOT / 'reports/live').glob('*/results.json'))
    if not runs:
        raise SystemExit('Run the actual local-model evaluation first.')
    path = runs[-1]
    run = json.loads(path.read_text(encoding='utf-8'))
    arm = run['arms']['local_ai']
    rows, metrics = arm['cases'], arm['metrics']
    valid = [r for r in rows if r['attempt']['model_status'] == 'valid']
    scored = [r for r in rows if r['reference_comparison_included']]
    matches = [r for r in scored if r['actual_route'] == r['expected_route']]
    mismatches = [{'id':r['id'],'expected':r['expected_route'],'actual':r['actual_route']} for r in scored if r['actual_route'] != r['expected_route']]
    latency = sorted(r['elapsed_seconds'] for r in valid)
    model = next((r['attempt']['model_version'] for r in valid), 'No successful live inference')
    baseline = run['arms']['no_ai']['metrics']
    summary = {
        'timestamp':datetime.now(timezone.utc).isoformat(), 'source_run':path.relative_to(ROOT).as_posix(),
        'model':model, 'attempted':len(rows), 'valid_inferences':len(valid),
        'runtime':runtime['runtime'], 'gpu':runtime['gpu'],
        'route_agreement':{'matches':len(matches),'compared':len(scored),'mismatches':mismatches},
        'valid_inference_latency_seconds':{'median':statistics.median(latency) if latency else None,
            'p95':latency[min(len(latency)-1,int(len(latency)*.95))] if latency else None},
        'metrics':metrics, 'no_ai_metrics':baseline,
        'unit_tests':tests['tests_run'], 'unit_failures':len(tests['failures'])+len(tests['errors']),
        'browser_checks':browser['passed'], 'browser_failures':browser['failed'],
        'live_browser_checks':live_browser['passed'],
        'semantic_probes':{'passed':probes['passed_attempts'],'attempted':probes['completed_attempts'],
            'failed_case_ids':probes['failed_case_ids']},
        'limits':'Visible invented development cases, no clinical ground truth or held-out performance claim.'}
    (ROOT/'reports/generated/local-ai-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    latency_text = (f"{statistics.median(latency):.2f} seconds median and {latency[min(len(latency)-1,int(len(latency)*.95))]:.2f} seconds p95"
                    if latency else 'No successful latency measurement')
    mismatch_text = ', '.join(r['id'] for r in mismatches) or 'None in this run'
    report = f'''# CareRoute: local AI intake and staff handoff

**Delivered version:** local AI prototype, policy demo-policy-0.3. **Record date:** 25 October 2026. Invented records only.

## What is delivered

CareRoute reads an invented appointment request with a real language model running on the laptop, then gives staff a structured assessment and exact source excerpts. Staff can inspect the original input, record a review, confirm a synthetic appointment and inspect the persisted audit history.

The original build defaulted to no AI and had never executed a live provider call. This version defaults to local inference, provides a model-readiness panel and displays the actual model, duration and output-token count. Scenario buttons fill editable inputs; they do not replay stored assessments. Authored replay remains explicitly labelled in advanced controls.

## Model and architecture

The default model is **{model}**, a roughly 2.5 GB Q4_K_M model served by Ollama {runtime['runtime']['version']}. Real inference was verified on the NVIDIA RTX 4060 Laptop GPU through Vulkan, with the loaded model using {runtime['gpu']['model_vram_bytes']/1024**3:.2f} GiB of GPU memory at an 8,192-token context. Runtime binaries and weights are installed separately and excluded from the source archive.

The browser sends an invented request to the Python standard-library server. SQLite records receipt first. The server asks the local model for JSON conforming to an enum schema, validates the complete response and exact evidence offsets, applies versioned rules, and persists the result. The staff workspace presents the result beside the original description.

The six model assessments are current warning, appointment intent, information sufficiency, contradiction, supported demonstration scope and human-review indication. The handoff is extractive: the model selects up to three exact excerpts rather than producing medical advice. Fabricated quotes, extra fields, invalid labels and incomplete generations are rejected.

Local inference is serialized, has a 90-second deadline and a 512-token output limit. Only loopback Ollama endpoints and installed local GGUF models are accepted. Local mode requires no API key and makes no hosted-model call. Requests remain saved for staff review if the model is busy, missing, offline or invalid.

## Completed workflow

1. Load an invented scenario or enter invented information. Edit the text freely.
2. Submit and receive a durable receipt while the actual AI assessment runs.
3. Inspect model-selected excerpts, provenance and the administrative suggestion.
4. Sign in as the demo reviewer, inspect the original request and record a human review.
5. Select a future time and confirm a synthetic booking. Inspect the audit history.

Immediate warning checks run before validation, persistence or model completion. The model cannot suppress a structured emergency indication. Staff review and appointment booking remain separate actions. Late AI cannot overwrite a human takeover, and an emergency downgrade requires a different supervisor.

## Executed engineering checks

| Check | Recorded result | Meaning |
|---|---|---|
| Automated policy, API, storage and adapter suite | {tests['passed']}/{tests['tests_run']} passed | Includes actual HTTP/SQLite workflows and mocked failure contracts |
| Browser regression checks | {browser['passed']}/{browser['passed']+browser['failed']} passed | Form, emergency checks offline, replay honesty, review, booking, audit, labels and mobile |
| Live-model browser checks | {live_browser['passed']} passed | Real model response through UI, persisted provenance, review and booking, outage fallback, mobile |
| Actual local-model evaluation | {len(valid)}/{len(rows)} valid responses | Fresh inference, raw responses and failures retained |
| Additional semantic probes | {probes['passed_attempts']}/{probes['completed_attempts']} passed | New wording, negation, history, vague input, intent, scope, warning paraphrase and embedded instructions |
| Route agreement on comparable authored references | {len(matches)}/{len(scored)} | Visible development examples; not clinical accuracy |

The successful local inference calls took **{latency_text}** in this run. These measurements include local HTTP handling and generation and reuse an already-loaded model. Cold startup can take longer; these are not latency guarantees. The live browser run separately exercises persistence and human workflow. All records are newly invented.

## Paired comparison with no AI

| Metric | No-AI baseline | Local AI with shared rules |
|---|---|---|
| Emergency-route misses | {ratio(baseline['emergency_route_miss_rate'])} | {ratio(metrics['emergency_route_miss_rate'])} |
| Incorrect routine suggestions / nonroutine references | {ratio(baseline['incorrect_routine_per_reference_nonroutine'])} | {ratio(metrics['incorrect_routine_per_reference_nonroutine'])} |
| Escalations / routine references | {ratio(baseline['unnecessary_escalation_per_reference_routine'])} | {ratio(metrics['unnecessary_escalation_per_reference_routine'])} |
| Execution failures | {baseline['execution_failures']['count']} | {metrics['execution_failures']['count']} |

Comparable route disagreements: **{mismatch_text}**. Five fixtures with AI-fault/output-specific references are excluded from input-disposition comparisons, with their reasons retained in the raw evaluation. They remain in execution totals. FX-31 represents failed initial persistence and is tested in the API/browser suite instead of this model runner.

This evaluation uses visible, authored development examples. It does not establish clinical safety, a held-out accuracy score, calibration or measured staff-time savings. Source research and the pre-local-AI report remain available as historical material; they are not substituted for this implementation's evidence.

The warning-paraphrase probe intentionally falls outside the immediate phrase matcher. If recognized by the model, its warning appears only after inference. This is an explicit coverage/timing limit; the model does not make pre-submit detection universal. Semantic probe failures: {', '.join(probes['failed_case_ids']) or 'none in this run'}.

Probe pass criteria cover the final route, selected warning/intent fields and exact excerpts, not every intermediate judgment. {auxiliary_note} Raw outputs are retained, and shared rules apply independently of the model's auxiliary flags.

{iteration_note}

## Reproduce and run

On this machine, double-click Start CareRoute.cmd. On a fresh Windows checkout, run the setup script, then the launcher:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_local_ai.ps1
python -X utf8 tools/start_demo.py
```

Open http://127.0.0.1:8080. Demo staff credentials are reviewer / demo-reviewer; supervisor / demo-supervisor is for second review. Python 3.11 or later is required. No third-party Python package is needed to run the app. Browser checks and PDF rendering use Playwright with installed Chrome/Edge or Chromium.

```powershell
python -X utf8 tools/run_checks.py
python -X utf8 tools/browser_check.py
python -X utf8 tools/browser_live_check.py
python -X utf8 tools/evaluate_live.py --execute --arms local_ai
python -X utf8 tools/probe_local_ai.py --execute
python -X utf8 tools/summarize_local_run.py
python -X utf8 tools/render_report.py
python -X utf8 tools/build_submission.py
```

The submission ZIP includes source, scripts, reports and a verified SHA-256 manifest. It excludes databases, credentials, caches, downloaded model weights and runtime binaries. The original research and specification snapshots are preserved.

## Limits and sources

CareRoute is a local hackathon demonstration. It is not a medical service and must use invented records. Its narrow example scope and emergency phrases are illustrative, not approved clinical policy. Real authentication, clinical validation, deployment operations, notifications and health-system integration are outside this submission. All appointments and coverage are simulated.

- [Recorded test results](generated/test-results.json) and [browser regression results](generated/browser-results.json).
- [Live browser evidence](generated/browser-live-results.json) and [local-model summary](generated/local-ai-summary.json).
- [Semantic probes](generated/local-probes.json) and [runtime/GPU evidence](generated/local-runtime.json).
- [Actual model run]({path.relative_to(ROOT/'reports').as_posix()}) with every input identifier, raw response, decision and failure.
- [Ollama model card](https://ollama.com/library/qwen3:4b-instruct) and [structured chat API](https://docs.ollama.com/api/chat).
- [Original report before local AI](iterations/pre-local-ai-submission.md) and [demo walkthrough](../DEMO.md).
'''
    (ROOT/'reports/submission-report.md').write_text(report,encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
