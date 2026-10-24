#!/usr/bin/env python3
"""Paired live-model runner for invented fixtures. Dry-run by default.

Actual requests require --execute and configured credentials. These visible
development cases are not a held-out or clinically adjudicated benchmark.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clinic.assessors import assess
from clinic.config import POLICY_VERSION
from clinic.policy import decide
from tools.evaluate import route_metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Explicitly authorize billable API requests for invented fixtures')
    parser.add_argument('--arms', nargs='+', choices=['jev_direct','jev_decomposed','llm'], default=['jev_direct','jev_decomposed','llm'])
    parser.add_argument('--limit', type=int, default=43)
    parser.add_argument('--output-dir', default=str(ROOT/'reports/live'))
    args=parser.parse_args()
    if not 1 <= args.limit <= 43:
        parser.error('--limit must be 1 through 43')
    data=(ROOT/'fixtures/synthetic-cases.json').read_bytes()
    cases=[c for c in json.loads(data)['cases'] if c['expected']['route'] is not None][:args.limit]
    assert all(c['synthetic'] is True for c in cases)
    plan={'mode':'dry_run' if not args.execute else 'live_requested', 'policy_version':POLICY_VERSION,
          'arms':args.arms,'case_ids':[c['id'] for c in cases], 'maximum_requests':len(cases)*len(args.arms),
          'fixture_sha256':hashlib.sha256(data).hexdigest(),
          'warning':'Authored visible development cases only; no clinical or held-out performance claim. Actual calls may incur vendor charges.'}
    print(json.dumps(plan,indent=2))
    if not args.execute:
        print('No model calls made. Add --execute only after configuring keys and reviewing this plan.')
        return
    missing=[]
    if any(a.startswith('jev_') for a in args.arms) and not (os.getenv('TYPESAFE_API_KEY') or os.getenv('JEV_API_KEY')):
        missing.append('TYPESAFE_API_KEY (or JEV_API_KEY)')
    if 'llm' in args.arms:
        missing.extend(name for name in ['CLINIC_LLM_API_KEY','CLINIC_LLM_MODEL'] if not os.getenv(name))
    if missing:
        parser.error('Missing configuration names: '+', '.join(missing)+'. Supply values securely; no calls were made.')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out=Path(args.output_dir)/run_id; out.mkdir(parents=True,exist_ok=False)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    arms={name:[] for name in ['no_ai']+args.arms}
    with (out/'attempts.jsonl').open('x') as log:
        for case in cases:
            failure_ref=case['expected']['primary_rule']=='H04'
            output_ref=case['variant']=='direct_replay' and case['expected']['primary_rule']=='H05'
            for arm in arms:
                started=time.monotonic()
                attempt=assess(case['inputs'],arm)
                decision=decide(case['inputs'],assessment=attempt.get('assessment'),
                                model_status=attempt['model_status'],variant=arm)
                row={'id':case['id'],'expected_route':case['expected']['route'],'actual_route':decision['route'],
                     'reference_comparison_included':not(failure_ref or output_ref),
                     'exclusion_reason':'AI-fault/output-specific reference; not independent input disposition' if failure_ref or output_ref else None,
                     'save_state':'succeeded', 'save_scope':'Evaluation assumption only; this runner does not exercise persistence',
                     'elapsed_seconds':round(time.monotonic()-started,4),
                     'error':attempt.get('error'), 'mode':attempt['mode'],
                     'raw_direct_route':(attempt.get('assessment') or {}).get('direct_route'),
                     'attempt':attempt,'decision':decision}
                arms[arm].append(row)
                log.write(json.dumps({'arm':arm,**row},allow_nan=False)+'\n'); log.flush()
    report={'run_id':run_id,**plan,'arms':{arm:{'metrics':route_metrics(rows),'cases':rows} for arm,rows in arms.items()},
            'limits':['No clinical ground truth','Not held-out data','No real reviewer minutes or UI timing','Provider errors remain in denominators','No automatic winner selection']}
    (out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Saved actual attempts and results to',out)


if __name__=='__main__': main()
