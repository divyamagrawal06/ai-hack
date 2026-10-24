#!/usr/bin/env python3
"""Actual local browser checks. Requires Playwright plus Chromium; no model calls."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.server import make_server
from clinic.policy import detect_local_warning
from tools.browser_runtime import browser_launch_options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default=str(ROOT / 'reports/generated'))
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright, expect
    results, timings, errors = [], [], []
    cases = json.loads((ROOT / 'fixtures/synthetic-cases.json').read_text(encoding="utf-8"))['cases']

    def check(name, fn):
        started = time.monotonic()
        try:
            fn()
            results.append({'name': name, 'status': 'passed', 'duration_seconds': round(time.monotonic()-started, 3)})
        except Exception as exc:
            results.append({'name': name, 'status': 'failed', 'error': str(exc), 'duration_seconds': round(time.monotonic()-started, 3)})
        print(results[-1]['status'].upper(), name, flush=True)

    with tempfile.TemporaryDirectory(prefix='clinic-browser-') as tmp, sync_playwright() as p:
        server = make_server(0, Path(tmp) / 'browser.db')
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        browser = p.chromium.launch(**browser_launch_options())
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base)
        page.wait_for_function("() => document.querySelector('#fixture-select').options.length === 45")

        def static_guidance():
            other = browser.new_context(java_script_enabled=False)
            q = other.new_page(); q.goto(base)
            expect(q.locator('.emergency-banner')).to_contain_text('local emergency services now')
            expect(q.locator('.noscript-warning')).to_be_visible()
            other.close()
        check('Emergency notice available with JavaScript disabled', static_guidance)

        def parity():
            for case in cases:
                actual = page.evaluate('(text) => window.CareRoute.detectLocalWarning(text)', case['inputs']['symptom_text'])
                assert actual == detect_local_warning(case['inputs']['symptom_text']), case['id']
        check('Client/server text-guard parity across 44 invented descriptions', parity)

        def structured_offline():
            context.set_offline(True)
            for i in range(1, 7):
                for answer in ['yes', 'unsure']:
                    page.locator('#new-request').click()
                    result = page.evaluate('''({id,answer}) => {
                        const start=performance.now();
                        const input=document.querySelector(`input[name="${id}"][value="${answer}"]`);
                        input.checked=true; input.dispatchEvent(new Event('input',{bubbles:true}));
                        return {visible:!document.querySelector('#immediate-guidance').hidden, ms:performance.now()-start};
                    }''', {'id': f'CHECK-{i:02d}', 'answer': answer})
                    assert result['visible'], (i, answer)
                    timings.append(result['ms'])
                    assert not page.locator('#receipt-panel').is_visible()
            context.set_offline(False)
        check('All 12 Yes/Unsure structured signals show guidance synchronously offline before submit', structured_offline)

        def text_offline():
            context.set_offline(True)
            for cid in ['FX-08', 'FX-09', 'FX-38']:
                page.locator('#new-request').click()
                text = next(c for c in cases if c['id']==cid)['inputs']['symptom_text']
                result = page.evaluate('''(text) => { const start=performance.now(); const el=document.querySelector('#symptom-text');
                    el.value=text; el.dispatchEvent(new Event('input',{bubbles:true}));
                    return {visible:!document.querySelector('#immediate-guidance').hidden,ms:performance.now()-start}; }''', text)
                assert result['visible'], cid
                timings.append(result['ms'])
            context.set_offline(False)
        check('Three previous model-dependent examples now trigger bounded local guidance offline', text_offline)

        def contexts():
            for text, wanted in [
                ('Years ago I had chest pain. I do not have it now.', 'none'),
                ('Last year I was healthy but now I cannot breathe.', 'current_explicit_demo_warning'),
                ('I do not have severe chest pain.', 'none'),
            ]:
                assert page.evaluate('(text) => CareRoute.detectLocalWarning(text)', text) == wanted, text
        check('Negated/history examples and current warning after historical clause', contexts)

        def load(cid):
            context.set_offline(False)
            page.locator('#fixture-select').select_option(cid)
            page.locator('#synthetic-confirm').check()

        def replay():
            load('FX-01')
            page.locator('#assessment-mode').select_option('replay')
            page.locator('#submit-request').click()
            expect(page.locator('#receipt-panel')).to_be_visible()
            page.wait_for_function("() => document.querySelector('#receipt-panel').textContent.includes('Replay — authored')")
            expect(page.locator('#receipt-panel')).to_contain_text('Routine appointment')
            expect(page.locator('#receipt-panel')).to_contain_text('No messages were sent')
            expect(page.locator('#receipt-panel')).to_contain_text('Not booked')
        check('Actual persisted replay receipt, route, mode and unbooked status', replay)

        def edited_replay():
            load('FX-01')
            page.locator('#assessment-mode').select_option('replay')
            page.locator('#symptom-text').fill('A different newly invented request.')
            page.locator('#submit-request').click()
            expect(page.locator('#form-error')).to_contain_text('unchanged synthetic scenario')
            assert not page.locator('#receipt-panel').is_visible()
        check('Edited text cannot masquerade as an unchanged assessment replay', edited_replay)

        def staff_workflow():
            page.locator('[data-view="staff"]').click()
            page.locator('#password').fill('demo-reviewer')
            page.locator('#login-form button[type=submit]').click()
            expect(page.locator('#staff-workspace')).to_be_visible()
            page.locator('.queue-card').first.click()
            expect(page.locator('#review-form')).to_be_visible()
            page.locator('#review-comment').fill('Synthetic review: checked the original description and confirmed the demonstration route.')
            page.locator('#review-reason').select_option('other')
            page.locator('#review-form button[type=submit]').click()
            page.wait_for_function("() => document.querySelector('#booking-form button').disabled === false")
            future = (datetime.now()+timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
            page.locator('#booking-slot').fill(future)
            page.locator('#booking-form button[type=submit]').click()
            expect(page.locator('#staff-message')).to_contain_text('booking saved')
            page.locator('#audit-details summary').click()
            expect(page.locator('#audit-content')).to_contain_text('request received')
            expect(page.locator('#audit-content')).to_contain_text('booking')
        check('Staff login, human review, booking and actual audit trail', staff_workflow)

        def failure():
            failed = make_server(0, Path(tmp)/'failed.db', fail_saves=True)
            thread = threading.Thread(target=failed.serve_forever, daemon=True); thread.start()
            q = context.new_page()
            try:
                q.goto('http://127.0.0.1:'+str(failed.server_port))
                q.wait_for_function("() => document.querySelector('#fixture-select').options.length === 45")
                q.locator('#fixture-select').select_option('FX-03')
                q.locator('#synthetic-confirm').check()
                q.locator('#submit-request').click()
                expect(q.locator('#form-error')).to_contain_text('not received')
                expect(q.locator('#immediate-guidance')).to_be_visible()
                assert not q.locator('#receipt-panel').is_visible()
            finally:
                q.close(); failed.shutdown(); failed.server_close(); thread.join()
        check('Real failed-persistence response never shows receipt and keeps emergency guidance', failure)

        def mobile():
            mobile_context = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True)
            q = mobile_context.new_page(); q.goto(base)
            assert q.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
            expect(q.locator('.emergency-banner')).to_be_visible()
            mobile_context.close()
        check('390px mobile layout has no horizontal overflow and retains emergency notice', mobile)

        def semantics():
            q = context.new_page(); q.goto(base)
            unlabelled = q.evaluate('''() => [...document.querySelectorAll('input,textarea,select')]
                .filter(el=>!el.labels?.length && !el.getAttribute('aria-label')).map(el=>el.id||el.name)''')
            assert not unlabelled, unlabelled
            assert q.locator('#immediate-guidance').get_attribute('role') == 'alert'
            q.keyboard.press('Tab')
            assert q.evaluate("() => document.activeElement.classList.contains('skip-link')")
            q.close()
        check('Basic label, alert and keyboard skip-link semantics (not a screen-reader audit)', semantics)
        check('No uncaught browser JavaScript errors', lambda: (_ for _ in ()).throw(AssertionError(errors)) if errors else None)
        browser.close()
        server.shutdown(); server.server_close(); worker.join()
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'scope': 'Local synthetic browser integration; not clinical or live-model validation',
              'browser': 'Chromium via Playwright', 'checks': results, 'passed':sum(r['status']=='passed' for r in results),
              'failed':sum(r['status']=='failed' for r in results), 'synchronous_emergency_handler_ms':timings,
              'timing_limitations':'In-process input-event to DOM-state measurement, not human comprehension or universal detection. No clinical latency target established.'}
    (output/'browser-results.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
