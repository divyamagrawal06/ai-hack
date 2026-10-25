#!/usr/bin/env python3
"""Build the current submission report from recorded, actually executed checks."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.assessors import LOCAL_PROMPT_VERSION


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
    challenge_path = ROOT/'reports/generated/blind-challenge-results.json'
    challenge = read('reports/generated/blind-challenge-results.json') if challenge_path.exists() else None
    regression_path = ROOT/'reports/generated/challenge-regression-results.json'
    regression = read('reports/generated/challenge-regression-results.json') if regression_path.exists() else None
    fresh_path = ROOT/'reports/generated/fresh-temporal-results.json'
    fresh = read('reports/generated/fresh-temporal-results.json') if fresh_path.exists() else None
    fresh_retest_path = ROOT/'reports/generated/fresh-temporal-regression-results.json'
    fresh_retest = read('reports/generated/fresh-temporal-regression-results.json') if fresh_retest_path.exists() else None
    challenge_section = ''
    if challenge:
        if challenge.get('state') != 'complete':
            raise SystemExit('Finish the frozen challenge run before building the final report.')
        result = challenge['summary']
        failures = ', '.join(row['id'] for row in result['mismatches']) or 'none'
        challenge_emergencies = [row for row in challenge['attempts'] if row['expected']['route'] == 'emergency_guidance']
        challenge_misses = sum(row['decision']['route'] != 'emergency_guidance' for row in challenge_emergencies)
        challenge_section = f'''## Frozen synthetic challenge

A separate assistant authored and froze 28 newly invented cases and policy labels across eight scenario families before the pipeline was evaluated. The candidate local model was not queried during authoring or label selection. The tuning agent did not inspect the cases before freezing its adapter. The author had previously seen the initial v1 adapter while setting up the runtime, but did not inspect the current tuning prompt when authoring the challenge. This is a small independent authoring check, not a blinded clinical study.

| Challenge measure | Result |
|---|---|
| Route agreement | {result['matched']}/{result['total']} ({100*result['matched']/result['total']:.1f}%) |
| Valid local-model inference | {result['valid_inferences']}/{result['total']} |
| Route, valid inference and selected semantic fields all agree | {result['strict_matches']}/{result['total']} |
| Emergency-route misses | {challenge_misses}/{len(challenge_emergencies)} |

The dataset was frozen at {challenge['dataset_frozen_at']}. This first run used prompt `{challenge['prompt_version']}` and policy `{challenge['policy_version']}`. Dataset, adapter, policy, model and prompt hashes are retained in [the complete challenge record](generated/blind-challenge-results.json). Route disagreements: {failures}. Every case, raw response, semantic disagreement and failure remains in the denominator. The challenge is disclosed after this run and must be treated as development material for subsequent tuning.

Results measure agreement with authored policy labels, not universal accuracy or clinical safety. See [the frozen cases](../fixtures/blind-challenge-v1.json) and [the freeze record](../fixtures/blind-challenge-v1.freeze.json).

All eight authored emergency challenge descriptions fall outside the fixed phrase guard and have negative structured warning answers. Their expected emergency route therefore tests model-added semantic detection. Successful detection still occurs after inference; it does not remove the documented immediate-detection coverage gap.

'''
    regression_section = ''
    if regression:
        if regression.get('state') != 'complete':
            raise SystemExit('Finish the disclosed regression run before building the final report.')
        result = regression['summary']
        regression_section = f'''## Retest after challenge-driven fixes

The first challenge exposed a missed conflict between structured onset and the description, two verifier quote-capitalization errors, and two incorrect auxiliary flags. The next pipeline supplies both onset sources to the timeline check, asks it to select source IDs mapped to exact text, and reconciles known scope/completeness from trusted form facts. A validated primary emergency warning is retained if a later verification step fails; a partial result can never establish routine eligibility. The v6 retest had 28 valid outputs but still missed one timing conflict (27/28 routes). The final refinement requires source-linked timing claims before comparing episodes; the earlier retest remains archived.

The same 28 cases were then rerun with their labels unchanged. This is a disclosed development regression, not another blind score. It does not replace the original 27/28 result.

The v9 retest also scored 27/28: a current warning followed by an embedded demand for a routine label was incorrectly routed as routine. That semantic failure is retained in [the v9 retest archive](generated/challenge-regression-runs/20261025T041618.299682Z.json). The final trusted instruction after the source index separates factual corrections from output commands: a demand to hide earlier text or choose a label cannot negate reported events. A preceding attempt with only a system-level reminder failed and remains archived. This addresses an observed failure; it does not establish immunity to prompt injection.

The v11 retest correctly handled every emergency case but falsely marked a 64-year-old as outside the stated 18-64 scope, scoring 27/28. [That result is also preserved](generated/challenge-regression-runs/20261025T042712.108025Z.json). The final correction makes deterministic form facts authoritative for scope in both directions. It preserves the original model output and every separate warning, uncertainty or human-review flag. The model prompt is unchanged by this code correction.

| Retest measure | Result |
|---|---|
| Route agreement | {result['matched']}/{result['total']} ({100*result['matched']/result['total']:.1f}%) |
| Valid local-model inference | {result['valid_inferences']}/{result['total']} |
| Route, valid inference and selected semantic fields all agree | {result['strict_matches']}/{result['total']} |

All raw calls, unchanged references and original/current policy fingerprints are preserved in [the disclosed retest record](generated/challenge-regression-results.json). Any 100% result here means agreement on these finite, now-visible examples.

'''
    fresh_section = ''
    if fresh:
        if fresh.get('state') != 'complete':
            raise SystemExit('Finish the targeted fresh check before building the final report.')
        result = fresh['summary']
        fresh_section = f'''## Targeted fresh temporal check

After the earlier failures, a separate assistant authored and froze eight new temporal contrast cases and policy labels, including consistent histories and separate concerns as well as true conflicts. The candidate local model was not queried during authoring or labelling. The final tuning agent did not see these case texts before freezing its pipeline. This is a targeted generalization check informed by the earlier error category, not an unbiased clinical benchmark.

The frozen run achieved **{result['matched']}/{result['total']} route agreement**, **{result['valid_inferences']}/{result['total']} valid inferences**, and **{result['strict_matches']}/{result['total']} agreement on route plus selected semantic fields**. Two routine examples fell back to human review because their primary model evidence failed validation: FT-03 changed capitalization, and FT-08 selected text from the onset field when only narrative quotations were accepted. Their raw semantic labels agreed with the references, but the complete pipeline failed, so both remain failures in this score.

The prompt version, pre-run data hash, timestamps and every response are in [the fresh temporal record](generated/fresh-temporal-results.json). These small synthetic results do not establish universal accuracy.

'''
    fresh_retest_section = ''
    if fresh_retest:
        if fresh_retest.get('state') != 'complete':
            raise SystemExit('Finish the disclosed temporal retest before building the final report.')
        result = fresh_retest['summary']
        fresh_retest_section = f'''## Retest after primary evidence repair

The final adapter also uses source IDs for primary evidence selection. The application retrieves exact original text and offsets from the declared field; it does not repair approximate quotations or substitute authored responses. A final prompt clarification requires human review when a person explicitly cannot describe a change in a named concern. These eight cases are now disclosed development material.

On the unchanged labels, the final retest records **{result['matched']}/{result['total']} route agreement**, **{result['valid_inferences']}/{result['total']} valid inferences**, and **{result['strict_matches']}/{result['total']} agreement on route plus selected fields**. [Every retest response is retained](generated/fresh-temporal-regression-results.json). This result does not replace or relabel the original 6/8 fresh result. No new unseen-performance claim is made for this final repair.

'''
    extra_result_rows = ''
    for label, record, meaning in (
        ('First frozen challenge, v5', challenge, 'Unseen during v5 tuning; original result preserved'),
        ('Disclosed challenge retest', regression, 'Labels unchanged; cases informed development'),
        ('First fresh temporal check, v7', fresh, 'Targeted cases unseen during v7 tuning'),
        ('Disclosed temporal retest', fresh_retest, 'Labels unchanged; cases informed the evidence repair'),
    ):
        if record:
            result = record['summary']
            extra_result_rows += f"| {label} | {result['matched']}/{result['total']} routes | {meaning} |\n"
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
    full_evaluation_prompt_version = next((r['attempt'].get('prompt_version') for r in valid), None)
    prompt_version = LOCAL_PROMPT_VERSION
    captured_replay = None
    if full_evaluation_prompt_version != prompt_version:
        captured_replay = read('reports/generated/v12-captured-replay.json')
        if (captured_replay['adapter_version'] != prompt_version
                or captured_replay['captured_prompt_version'] != full_evaluation_prompt_version
                or captured_replay['prior_live_report_canonical_sha256'] != hashlib.sha256(json.dumps(run, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
                or not captured_replay['summary']['all_request_payloads_identical']):
            raise SystemExit('The latest broad live run needs a matching, explicitly labelled captured replay.')
        for name, expected in captured_replay['source_hashes'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
                raise SystemExit('Captured replay source is stale: ' + name)
    # Historical first-run scores stay separate; current retests must describe
    # the same frozen pipeline as the current development and browser runs.
    for name, record in [('challenge retest', regression), ('temporal retest', fresh_retest)]:
        if record and (record.get('prompt_version') != prompt_version or record.get('policy_version') != run['policy_version']):
            raise SystemExit(f'Stale {name}: rerun it with the current frozen pipeline before publishing.')
    if probes.get('prompt_versions') != [prompt_version] or probes.get('policy_version') != run['policy_version']:
        raise SystemExit('Semantic probes do not match the current pipeline.')
    if live_browser.get('prompt_version') != prompt_version or live_browser.get('policy_version') != run['policy_version']:
        raise SystemExit('Live browser evidence does not match the current pipeline.')
    baseline = run['arms']['no_ai']['metrics']
    summary = {
        'timestamp':datetime.now(timezone.utc).isoformat(), 'source_run':path.relative_to(ROOT).as_posix(),
        'model':model, 'prompt_version':prompt_version, 'policy_version':run['policy_version'], 'attempted':len(rows), 'valid_inferences':len(valid),
        'full_evaluation_prompt_version':full_evaluation_prompt_version,
        'broad_metrics_scope':'The attempted count, broad route agreement, latency and paired metrics describe full_evaluation_prompt_version; current challenge and temporal results are separate.',
        'captured_replay':captured_replay['summary'] if captured_replay else None,
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
        'blind_challenge':challenge['summary'] if challenge else None,
        'disclosed_challenge_retest':regression['summary'] if regression else None,
        'fresh_temporal_check':fresh['summary'] if fresh else None,
        'disclosed_temporal_retest':fresh_retest['summary'] if fresh_retest else None,
        'limits':'Invented development cases and a separately reported frozen synthetic challenge; no clinical ground truth or universal accuracy claim.'}
    (ROOT/'reports/generated/local-ai-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    latency_text = (f"{statistics.median(latency):.2f} seconds median and {latency[min(len(latency)-1,int(len(latency)*.95))]:.2f} seconds p95"
                    if latency else 'No successful latency measurement')
    mismatch_text = ', '.join(r['id'] for r in mismatches) or 'None in this run'
    report = f'''# CareRoute: local AI intake and staff handoff

**Delivered version:** local AI prototype, policy {run['policy_version']}. **Record date:** 25 October 2026. Invented records only.

## What is delivered

CareRoute reads an invented appointment request with a real language model running on the laptop, then gives staff a structured assessment and exact source excerpts. Staff can inspect the original input, record a review, confirm a synthetic appointment and inspect the persisted audit history.

The original submission defaulted to no AI and included no recorded live provider run. This version defaults to local inference, provides a model-readiness panel and displays the actual model, duration and output-token count. Scenario buttons fill editable inputs; they do not replay stored assessments. Authored replay remains explicitly labelled in advanced controls.

The interface is organized as an intake workspace and a staff inbox. A compact navigation rail, continuous form, progress summary and restrained color system replace the former promotional header and stacked panels. Advanced demonstration settings remain available without leading the intake flow.

## Assignment and dataset

The original Question 4 statement requests synthetic records, a prototype intake form, transparent rules/model, test cases, staff overrides and a safety note. It supplies no dataset or dataset link and sets no numerical accuracy target. The team defines the illustrative policy. The supplied statement is preserved in [Original assignment and dataset scope](../docs/00-original-assignment.md).

The original 44 fixtures and semantic probes are invented development examples. A passing test or a matching route has a precise denominator; neither should be advertised as universal or clinical accuracy. Fresh challenge results, when available, are reported separately from examples used to refine the prompts.

## Model and architecture

The default model is **{model}**, a roughly 2.5 GB Q4_K_M model served by Ollama {runtime['runtime']['version']}. This run uses prompt pipeline **{prompt_version}**. Real inference was verified on the NVIDIA RTX 4060 Laptop GPU through Vulkan, with the loaded model using {runtime['gpu']['model_vram_bytes']/1024**3:.2f} GiB of GPU memory at an 8,192-token context. Runtime binaries and weights are installed separately and excluded from the source archive.

The browser sends an invented request to the Python standard-library server. SQLite records receipt first. The server asks the local model for JSON conforming to an enum schema, validates the complete response and exact evidence offsets, applies versioned rules, and persists the result. The staff workspace presents the result beside the original description.

The six model assessments are current warning, appointment intent, information sufficiency, contradiction, supported demonstration scope and human-review indication. The handoff is extractive: the model selects source excerpts rather than producing medical advice. The application validates their exact input fields and offsets. Fabricated quotes, extra fields, invalid labels and incomplete generations are rejected.

The main assessment is followed by a focused timeline-consistency call that compares narrative statements with structured onset. The verifier selects source IDs that map to exact original text; each excerpt identifies its input field. Known form scope and missing information are reconciled from authoritative form facts. If the model alone raises an emergency signal, source attribution distinguishes actual concerns from explicitly fictional material. When both kinds occur, the actual excerpts receive another assessment. A disputed model warning can become human review, never routine, and independent emergency checks always retain precedence. A later verifier failure cannot erase a validated primary warning; partial results remain visibly degraded and cannot establish routine eligibility. Primary findings, each verification response and the final reconciliation remain in the audit.

Local inference is serialized with a 90-second deadline for the entire pipeline. Main and attributed-assessment outputs are capped at 512 tokens each; timeline claim extraction and conditional source attribution have 768-token caps. Token counts and latency include every call, not just the first. Completed responses and failures are retained; late responses after the outer deadline are discarded and are not claimed audited. Only loopback Ollama endpoints and installed local GGUF models are accepted. Local mode requires no API key and makes no hosted-model call. Requests remain saved for staff review if the model is busy, missing, offline or invalid.

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
| Live-model browser checks | {live_browser['passed']} passed | Real inference, review and booking, field-labelled evidence, retained warning after verifier failure, outage and mobile |
| Latest broad live evaluation, {full_evaluation_prompt_version} | {len(valid)}/{len(rows)} valid responses | Fresh inference on that version; raw responses and failures retained |
| Additional semantic probes | {probes['passed_attempts']}/{probes['completed_attempts']} passed | New wording, negation, history, vague input, intent, scope, warning paraphrase and embedded instructions |
| Broad live route agreement, {full_evaluation_prompt_version} | {len(matches)}/{len(scored)} | Visible development examples; not clinical accuracy |
{extra_result_rows}

The broad live evaluation above used **{full_evaluation_prompt_version}**. Its completed assessment pipelines took **{latency_text}**. These measurements include all model calls within each assessment, local HTTP handling and generation, and reuse an already-loaded model. Cold startup can take longer; these are not latency guarantees. The current adapter is **{prompt_version}**, whose live challenge, probe and browser results are separately recorded. All records are newly invented.

The final scope correction leaves model prompts unchanged. [A captured-response regression](generated/v12-captured-replay.json) passed all 43 responses through the final adapter, verified every model-request payload was identical, and retained all 38 matching comparable routes. This made **zero new model calls** and is not fresh performance evidence; the original live record remains unchanged.

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

{challenge_section}
{regression_section}
{fresh_section}
{fresh_retest_section}
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
