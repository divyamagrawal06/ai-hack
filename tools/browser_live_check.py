#!/usr/bin/env python3
"""Real local-model browser integration, including review, booking and outage.

Requires an installed local Ollama model. No authored assessment or mock replaces
inference in the successful request. All input records are invented fixtures.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.assessors import LOCAL_PROMPT_VERSION, local_status
from clinic.config import POLICY_VERSION
from clinic.policy import detect_local_warning
from clinic.server import make_server
from tools.browser_runtime import browser_launch_options


def assert_grounded_evidence(request):
    """Offsets and quotes must match their declared original input field."""
    evidence = request['ai']['evidence']
    assert evidence, 'A successful handoff should retain source excerpts'
    for span in evidence:
        field = span.get('field', 'symptom_text')
        assert field in {'symptom_text', 'onset', 'onset_currentness'}, span
        source = request['inputs'].get(field, '')
        start, end = span['start'], span['end']
        assert type(start) is int and type(end) is int and 0 <= start < end <= len(source), span
        assert source[start:end] == span['quote'], span


def main():
    from playwright.sync_api import sync_playwright, expect
    status = local_status()
    if not status['available']:
        raise SystemExit('A live local model is required: ' + status['message'])
    screenshots = ROOT / 'reports/screenshots'
    screenshots.mkdir(exist_ok=True)
    results, errors = [], []
    with tempfile.TemporaryDirectory(prefix='careroute-live-') as folder, sync_playwright() as p:
        server = make_server(0, Path(folder) / 'live.db')
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        browser = p.chromium.launch(**browser_launch_options())
        try:
            context = browser.new_context(viewport={'width':1440, 'height':1000})
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            base = 'http://127.0.0.1:' + str(server.server_port)
            page.goto(base)
            page.wait_for_function("() => document.querySelector('#fixture-select').options.length === 45")
            expect(page.locator('#ai-status')).to_have_text('Connected', timeout=10000)
            expect(page.locator('#assessment-mode')).to_have_value('local_ai')
            page.screenshot(path=str(screenshots / 'intake-desktop.png'))

            page.locator('[data-scenario="FX-01"]').click()
            expect(page.locator('#assessment-mode')).to_have_value('local_ai')
            started = time.monotonic()
            with page.expect_response(lambda r: r.url.endswith('/api/requests') and r.request.method == 'POST') as received:
                page.locator('#submit-request').click()
            receipt = received.value.json()
            rid, token = receipt['request']['id'], receipt['receipt_token']
            expect(page.locator('#receipt-panel .live-badge')).to_be_visible(timeout=100000)
            saved = context.request.get(f'{base}/api/requests/{rid}?receipt={token}').json()['request']
            assert saved['mode'] == 'live_model' and saved['ai']['status'] == 'valid', saved
            assert saved['ai']['completion_tokens'] > 0 and saved['ai']['local'] is True
            assert_grounded_evidence(saved)
            assert saved['route'] == 'routine_appointment', saved['decision']
            results.append({'name':'Fresh local inference through browser submission and persisted receipt', 'passed':True,
                            'elapsed_seconds':round(time.monotonic()-started,3), 'ai':saved['ai']})
            page.locator('#receipt-panel').screenshot(path=str(screenshots / 'live-ai-result.png'))

            page.locator('[data-view="staff"]').click()
            page.locator('#password').fill('demo-reviewer')
            page.locator('#login-form button[type=submit]').click()
            page.locator('.queue-card').first.click()
            expect(page.locator('#staff-detail .ai-fields')).to_be_visible()
            page.locator('#review-comment').fill('Reviewed the original invented text and local AI excerpts. Confirmed the demonstration routine route.')
            page.locator('#review-reason').select_option('other')
            page.locator('#review-form button[type=submit]').click()
            expect(page.locator('#booking-form button')).to_be_enabled()
            page.locator('#booking-slot').fill((datetime.now()+timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'))
            page.locator('#booking-form button[type=submit]').click()
            expect(page.locator('#staff-message')).to_contain_text('booking saved')
            page.locator('#audit-details summary').click()
            expect(page.locator('#audit-content')).to_contain_text('assessment completed')
            expect(page.locator('#audit-content')).to_contain_text('synthetic booking confirmed')
            booked = context.request.get(f'{base}/api/requests/{rid}').json()['request']
            assert booked['booking']['state'] == 'booked' and booked['review_state'] == 'reviewed'
            assert booked['assessment']['raw_output']['eval_count'] > 0
            assert booked['assessment']['prompt_version'] == LOCAL_PROMPT_VERSION
            assert booked['decision']['policy_version'] == POLICY_VERSION
            page.locator('#audit-details summary').click()
            page.evaluate('window.scrollTo(0, 0)')
            page.screenshot(path=str(screenshots / 'staff-workspace.png'))
            results.append({'name':'Human review, synthetic booking, raw inference and audit persisted', 'passed':True})

            page.locator('[data-view="intake"]').click()
            page.locator('[data-scenario="FX-24"]').click()
            with page.expect_response(lambda r: r.url.endswith('/api/requests') and r.request.method == 'POST') as received:
                page.locator('#submit-request').click()
            second_receipt = received.value.json()
            expect(page.locator('#receipt-panel .live-badge')).to_be_visible(timeout=100000)
            expect(page.locator('#receipt-panel .suggestion')).to_contain_text('Same-day human review')
            second = context.request.get(f"{base}/api/requests/{second_receipt['request']['id']}?receipt={second_receipt['receipt_token']}").json()['request']
            assert second['ai']['status'] == 'valid' and second['ai']['completion_tokens'] > 0
            assert second['assessment']['prompt_version'] == LOCAL_PROMPT_VERSION
            assert second['inputs']['self_reported_urgency'] == 'routine'
            assert_grounded_evidence(second)
            results.append({'name':'A different narrative gets a fresh AI assessment and human-review route', 'passed':True,
                            'ai':second['ai']})

            # Exercise source attribution across the narrative and separate onset field.
            challenge = json.loads((ROOT / 'fixtures/blind-challenge-v1.json').read_text(encoding='utf-8'))
            conflict = next(case for case in challenge['cases'] if case['id'] == 'BC-18')['inputs']
            page.locator('[data-scenario="FX-01"]').click()
            page.locator('#symptom-text').fill(conflict['symptom_text'])
            page.locator('#onset').fill(conflict['onset'])
            page.locator('#age').fill(str(conflict['age_years']))
            page.locator('#preferred-times').fill('; '.join(conflict['preferred_times']))
            page.locator('#currentness').select_option(conflict['onset_currentness'])
            with page.expect_response(lambda r: r.url.endswith('/api/requests') and r.request.method == 'POST') as received:
                page.locator('#submit-request').click()
            conflict_receipt = received.value.json()
            expect(page.locator('#receipt-panel .live-badge')).to_be_visible(timeout=100000)
            cross_field = context.request.get(f"{base}/api/requests/{conflict_receipt['request']['id']}").json()['request']
            assert cross_field['ai']['status'] == 'valid' and cross_field['route'] == 'same_day_human_review'
            assert cross_field['assessment']['assessment']['contradiction'] is True
            assert cross_field['assessment']['prompt_version'] == LOCAL_PROMPT_VERSION
            assert cross_field['inputs']['onset'] == conflict['onset']
            assert_grounded_evidence(cross_field)
            assert any(span.get('field') == 'onset' for span in cross_field['ai']['evidence'])
            page.locator('#receipt-panel .evidence-details summary').click()
            expect(page.locator('#receipt-panel .evidence-details')).to_contain_text('Description')
            expect(page.locator('#receipt-panel .evidence-details')).to_contain_text('When it started')
            results.append({'name':'Conflicting narrative and structured onset retain exact field-labelled source excerpts',
                            'passed':True, 'case_id':'BC-18', 'ai':cross_field['ai']})

            # Real primary inference, then an explicitly injected verifier failure.
            probes = json.loads((ROOT/'fixtures/local-ai-probes.json').read_text(encoding='utf-8'))
            warning = next(case for case in probes['cases'] if case['id'] == 'LP-07')['inputs']
            assert detect_local_warning(warning['symptom_text']) == 'none'
            page.locator('[data-scenario="FX-01"]').click()
            page.locator('#symptom-text').fill(warning['symptom_text'])
            page.locator('#onset').fill('Now')
            expect(page.locator('#immediate-guidance')).not_to_be_visible()
            with patch('clinic.assessors._verification_step', side_effect=TimeoutError('Injected verifier failure for browser check')):
                with page.expect_response(lambda r: r.url.endswith('/api/requests') and r.request.method == 'POST') as received:
                    page.locator('#submit-request').click()
                partial_receipt = received.value.json()
                expect(page.locator('#receipt-panel .ai-result.partial')).to_be_visible(timeout=100000)
                expect(page.locator('#receipt-panel .suggestion')).to_contain_text('Emergency guidance')
                expect(page.locator('#receipt-panel .ai-result.partial')).to_contain_text('do not wait for staff review')
                assert page.locator('#receipt-panel .live-badge').count() == 0
                partial = context.request.get(f"{base}/api/requests/{partial_receipt['request']['id']}").json()['request']
                assert partial['mode'] == 'degraded' and partial['ai']['status'] == 'partial'
                assert partial['route'] == 'emergency_guidance'
                assert partial['assessment']['raw_output']['eval_count'] > 0
                assert partial['assessment']['prompt_version'] == LOCAL_PROMPT_VERSION
            results.append({'name':'Real primary model warning survives injected verifier failure and is visibly incomplete',
                            'passed':True, 'fault_injection':'Verifier TimeoutError after actual primary inference', 'ai':partial['ai']})

            with patch.dict(os.environ, {'CLINIC_OLLAMA_URL':'http://127.0.0.1:9'}):
                page.locator('[data-view="intake"]').click()
                page.locator('[data-scenario="FX-01"]').click()
                page.locator('#submit-request').click()
                expect(page.locator('#receipt-panel .ai-result.unavailable')).to_be_visible(timeout=15000)
                expect(page.locator('#receipt-panel')).to_contain_text('Same-day human review')
                assert page.locator('#receipt-panel .live-badge').count() == 0
                page.locator('[data-scenario="FX-03"]').click()
                expect(page.locator('#immediate-guidance')).to_be_visible()
                assert not page.locator('#receipt-panel').is_visible()
            results.append({'name':'Unavailable model retains human fallback and immediate pre-submit guidance', 'passed':True})

            mobile = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True)
            q = mobile.new_page()
            q.goto(base)
            expect(q.locator('#ai-status')).to_have_text('Connected', timeout=10000)
            assert q.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
            q.screenshot(path=str(screenshots / 'intake-mobile.png'))
            mobile.close()
            assert not errors, errors
            results.append({'name':'Mobile layout and no uncaught browser errors', 'passed':True})
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
            worker.join()
    report = {'timestamp':datetime.now(timezone.utc).isoformat(), 'model_status':status,
              'prompt_version':LOCAL_PROMPT_VERSION, 'policy_version':POLICY_VERSION,
              'scope':'Real local inference plus browser, HTTP, SQLite and staff workflow on invented inputs; not clinical validation',
              'checks':results, 'passed':len(results), 'browser_errors':errors}
    (ROOT / 'reports/generated/browser-live-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
