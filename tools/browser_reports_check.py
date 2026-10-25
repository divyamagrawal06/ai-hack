"""Live report extraction through a browser, then local AI and staff review.

--execute sends one invented PDF to OpenAI and one incomplete intake to Ollama.
Uses an isolated database; does not modify the user's demo queue.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.server import make_server
from tools.browser_runtime import browser_launch_options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print('Pass --execute for one live OpenAI extraction and local model intake.')
        return
    from playwright.sync_api import sync_playwright, expect
    checks, errors = [], []
    output = ROOT / 'reports/generated/report-feature-checks'
    output.mkdir(parents=True, exist_ok=True)
    screenshots = ROOT / 'reports/screenshots'
    data = {'timestamp': datetime.now(timezone.utc).isoformat(), 'scope': 'Live PDF upload, explicit cloud consent, source review, separate current answers, local Qwen routing, saved provenance and staff review. Isolated temporary database.', 'checks': checks}
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
            server = make_server(0, Path(tmp)/'report-browser.sqlite3')
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            browser = p.chromium.launch(**browser_launch_options())
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.wait_for_function("() => document.querySelector('#fixture-select').options.length === 45")
                page.locator('#symptom-text').fill('Existing invented draft')
                page.locator('#age').fill('60')
                page.locator('#report-import summary').click()
                page.locator('#report-file').set_input_files(str(ROOT/'static/samples/routine-clinic-note.pdf'))
                page.locator('#report-extract').click()
                expect(page.locator('#report-message')).to_contain_text('consent')
                expect(page.locator('#report-preview')).to_be_hidden()
                checks.append('No extraction without explicit consent')
                page.locator('#report-consent').check()
                page.locator('#report-extract').click()
                expect(page.locator('#report-preview')).to_be_visible(timeout=90000)
                expect(page.locator('#report-provenance')).to_contain_text('OpenAI')
                expect(page.locator('#report-facts')).to_contain_text('dry skin')
                expect(page.locator('#symptom-text')).to_have_value('Existing invented draft')
                expect(page.locator('#age')).to_have_value('60')
                checks.append('Live OpenAI PDF extraction shows evidence without changing intake')
                page.locator('#report-apply').click()
                expect(page.locator('#report-message')).to_contain_text('confirm your review')
                checks.append('Import requires human review confirmation')
                page.locator('#report-reviewed').check()
                page.locator('#report-import').scroll_into_view_if_needed()
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=str(screenshots/'report-extraction-desktop.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow'
                page.screenshot(path=str(screenshots/'report-extraction-mobile.png'), full_page=True)
                checks.append('Report preview fits 390px and 1440px widths')
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.locator('#report-reviewed').check()
                page.locator('#report-apply').click()
                expect(page.locator('#report-attached')).to_be_visible()
                expect(page.locator('#age')).to_have_value('')
                assert page.locator('input[name="urgency"]:checked').count() == 0
                assert page.locator('input[name^="CHECK-"]:checked').count() == 0
                expect(page.locator('#assessment-mode')).to_have_value('local_ai')
                checks.append('Reviewed notes create a new local-AI request without inferring current answers')
                page.locator('#submit-request').click()
                expect(page.locator('#receipt-panel')).to_be_visible()
                page.wait_for_function("() => document.querySelector('#receipt-panel').textContent.includes('Live inference')", timeout=180000)
                expect(page.locator('#receipt-panel')).to_contain_text('Same-day human review')
                items = server.store.queue()
                assert len(items) == 1
                item = server.store.get(items[0]['id'], staff=True)
                data['request'] = item
                assert item['assessment_state'] == 'complete', item['assessment_state']
                assert item['ai']['model'] == 'qwen3:4b-instruct', item['ai']
                assert item['report_extraction']['provider'] == 'openai'
                checks.append('Actual local Qwen assessment routes incomplete current information to human review')
                page.locator('[data-view="staff"]').click()
                page.locator('#password').fill('demo-reviewer')
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#staff-workspace')).to_be_visible()
                page.locator('.queue-card').first.click()
                page.locator('#staff-report summary').click()
                expect(page.locator('#staff-report')).to_contain_text('dry skin')
                page.locator('#review-comment').fill('Reviewed invented report excerpts and missing current information; retain human review.')
                page.locator('#review-reason').select_option('other')
                page.locator('#review-form button[type=submit]').click()
                page.wait_for_function("() => document.querySelector('#booking-form button').disabled === false")
                audit = server.store.audit(item['id'])
                assert any(e['event_type'] == 'report_extraction_review_confirmed' for e in audit)
                checks.append('Staff can inspect report provenance and save a review with an immutable audit event')
                assert not errors, errors
                checks.append('No browser JavaScript errors')
                data['passed'] = True
            finally:
                browser.close(); server.shutdown(); server.server_close(); worker.join(timeout=3)
    except Exception as error:
        data.update(passed=False, error=str(error))
    data.update(duration_seconds=round(time.monotonic()-started, 2), browser_errors=errors)
    (output/'report-browser-results.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({k:v for k,v in data.items() if k != 'request'}, indent=2))
    raise SystemExit(0 if data.get('passed') else 1)


if __name__ == '__main__': main()
