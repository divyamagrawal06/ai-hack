#!/usr/bin/env python3
"""Check the local demo; optionally warm it with one invented request."""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.assessors import _local_endpoint


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--warm-up', action='store_true', help='Create one invented routine request and run fresh inference')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    base = f'http://127.0.0.1:{args.port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(url, body=None, headers=None):
        data = json.dumps(body).encode('utf-8') if body is not None else None
        metadata = {'Content-Type': 'application/json'} if data is not None else {}
        metadata.update(headers or {})
        with opener.open(urllib.request.Request(url, data=data, headers=metadata), timeout=8) as response:
            return json.load(response)

    try:
        health = request(base + '/api/health')
        if health.get('status') != 'ok' or health.get('synthetic_only') is not True:
            raise ValueError('This endpoint is not the synthetic CareRoute demo')
        config = request(base + '/api/config')
        status = request(base + '/api/ai/status')
        print(f"App: {base} - healthy; policy {config['policy_version']}", flush=True)
        print(f"Local AI: {status['message']}", flush=True)
        if not status['available'] or status.get('local') is not True:
            return 1
        if args.warm_up:
            fixtures = request(base + '/api/fixtures')['cases']
            inputs = next(row['inputs'] for row in fixtures if row['id'] == 'FX-01')
            saved = request(base + '/api/requests', {'synthetic': True, 'inputs': inputs, 'variant': 'local_ai'},
                            {'Idempotency-Key': 'demo-warmup-' + uuid.uuid4().hex})
            rid = saved['request']['id']
            receipt_url = base + '/api/requests/' + rid + '?receipt=' + urllib.parse.quote(saved['receipt_token'], safe='')
            print('Warming the model with one newly saved invented routine request...', flush=True)
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                item = request(receipt_url)['request']
                if item['ai']['status'] != 'pending':
                    break
                time.sleep(0.5)
            if item['ai']['status'] != 'valid' or item['mode'] != 'live_model' or not item['ai'].get('completion_tokens'):
                raise ValueError('Warm-up did not produce valid live inference: ' + str(item['ai'].get('error') or item['ai']['status']))
            if item['route'] != 'routine_appointment':
                raise ValueError('The invented warm-up received an unexpected route: ' + item['route'])
            print(f"Fresh inference passed: {item['ai']['latency_ms'] / 1000:.1f}s, {item['ai']['completion_tokens']} output tokens; request {rid[:8]}", flush=True)
        resident = request(_local_endpoint() + '/api/ps').get('models', [])
        loaded = next((m for m in resident if m.get('name', m.get('model')) == status['model']), None)
        if loaded:
            print(f"Model loaded: {status['model']}; GPU memory reported by Ollama: {loaded.get('size_vram', 0) / 1024**3:.2f} GiB")
        else:
            print('Model is installed but currently idle/unloaded. The next request loads it; use --warm-up before judging.')
        print('Keep the app terminal open and laptop awake. Each submission runs fresh inference; no background thinking loop is required.')
        return 0
    except (OSError, ValueError, KeyError, StopIteration) as error:
        print('Demo check failed: ' + str(error), file=sys.stderr)
        print('Open Start Final Demo.cmd. If local AI is missing, follow the setup instructions in README.md.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
