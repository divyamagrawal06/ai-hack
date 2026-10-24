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
from clinic.assessors import local_status
from clinic.server import make_server
from tools.browser_runtime import browser_launch_options


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
            assert saved['ai']['evidence'] and all(x['quote'] in saved['inputs']['symptom_text'] for x in saved['ai']['evidence'])
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
            assert second['inputs']['self_reported_urgency'] == 'routine'
            results.append({'name':'A different narrative gets a fresh AI assessment and human-review route', 'passed':True,
                            'ai':second['ai']})

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
              'scope':'Real local inference plus browser, HTTP, SQLite and staff workflow on invented inputs; not clinical validation',
              'checks':results, 'passed':len(results), 'browser_errors':errors}
    (ROOT / 'reports/generated/browser-live-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
