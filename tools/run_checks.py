#!/usr/bin/env python3
"""Run the actual unit/API suite and persist a machine-readable result."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default=str(ROOT / 'reports/generated'))
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    stream = io.StringIO()
    start = time.monotonic()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    (output / 'tests.log').write_text(log)
    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'policy_version': __import__('clinic.config', fromlist=['POLICY_VERSION']).POLICY_VERSION,
        'scope': 'Local policy, mocked provider contracts, actual HTTP and SQLite integration; no live model calls',
        'tests_run': result.testsRun,
        'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        'failures': [{'test': str(test), 'detail': detail} for test, detail in result.failures],
        'errors': [{'test': str(test), 'detail': detail} for test, detail in result.errors],
        'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
        'duration_seconds': round(time.monotonic()-start, 3),
        'live_model_calls': 0,
    }
    (output / 'test-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(log)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
