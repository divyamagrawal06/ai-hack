"""Opt-in live extraction checks on the five disclosed, invented reports."""
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic import reports
from clinic.storage import StoreError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Send five synthetic reports to OpenAI (billable API calls).')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'fixtures/report-cases.json').read_text())['cases']
    if not args.execute:
        print('Dry run: five disclosed synthetic reports; pass --execute to call OpenAI.')
        return
    results = []
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = ROOT / 'reports/generated/report-extraction-runs' / stamp
    destination.mkdir(parents=True)
    for case in cases:
        path = ROOT / 'static/samples' / case['file']
        row = {'file': path.name, 'expected': case['expected']}
        try:
            result = reports.extract({'filename': path.name, 'data_base64': base64.b64encode(path.read_bytes()).decode(), 'synthetic': True, 'send_to_openai': True})
            row['result'] = result
            facts = result['extraction']['facts']
            corpus = ' '.join(f['value'] + ' ' + f['quote'] for f in facts).lower()
            expected = case['expected']
            checks = {'document_type': result['extraction']['document_type'] == expected['document_type']}
            checks.update({'contains_' + word: word.lower() in corpus for word in expected['required_values']})
            checks.update({'excludes_' + word: word.lower() not in corpus for word in expected['forbidden_values']})
            if expected.get('historical_required'):
                checks['preserves_historical_context'] = any(f['time_context'] == 'historical' for f in facts)
            checks['source_handling'] = bool(facts) and all(f['quote_verification'] == ('visual_review_required' if path.suffix == '.png' else 'normalized_text_match') for f in facts)
            row.update(checks=checks, passed=all(checks.values()))
        except StoreError as error:
            row.update(passed=False, error=str(error))
        results.append(row)
        (destination / (path.name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
        print(('PASS ' if row['passed'] else 'FAIL ') + path.name, flush=True)
    summary = {'timestamp': stamp, 'scope': 'Five disclosed assistant-authored development examples. Checks selected expected facts, units, historical context, source quotes and one embedded-instruction example. Not clinical accuracy or a held-out benchmark.', 'live_provider': 'openai', 'model': reports.status()['model'], 'cases_run': len(results), 'passed': sum(r['passed'] for r in results), 'results': results}
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (ROOT / 'reports/generated/report-extraction-results.json').write_text(json.dumps(summary, indent=2) + '\n')
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)


if __name__ == '__main__':
    main()
