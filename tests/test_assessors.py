"""Adapter contract tests use explicit mocks, never live model inference."""
import copy
import json
import math
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import urllib.error

from clinic import assessors as a

CASES = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/synthetic-cases.json').read_text())['cases']


def choice(labels, selected):
    return {'type': 'choice', 'choice': selected, 'confidence': 1.0,
            'probabilities': {key: float(key == selected) for key in labels}}


def direct_response(selected='defer'):
    return {'model': 'mock-model', 'answers': {'route': choice(a.DIRECT_LABELS, selected)}, 'usage': {}}


class AssessorContracts(unittest.TestCase):
    def setUp(self):
        self.inputs = copy.deepcopy(CASES[0]['inputs'])

    def test_no_ai_makes_no_network_call(self):
        with patch.object(a, '_post_json') as post:
            result = a.assess(self.inputs, 'no_ai')
        post.assert_not_called()
        self.assertEqual(result['mode'], 'no_ai')
        self.assertIsNone(result['assessment'])

    def test_missing_credentials_degrade_without_call(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(a, '_post_json') as post:
            for variant in ['jev_direct', 'jev_decomposed', 'llm']:
                result = a.assess(self.inputs, variant)
                self.assertEqual(result['mode'], 'degraded')
                self.assertEqual(result['model_status'], 'unavailable')
        post.assert_not_called()

    def test_exact_replay_is_labelled(self):
        result = a.assess(self.inputs, 'replay', 'FX-01')
        self.assertEqual(result['mode'], 'replay')
        self.assertEqual(result['model_version'], 'authored-fixture-not-a-model')

    def test_changed_replay_never_reuses_saved_assessment(self):
        self.inputs['symptom_text'] += ' This text was changed.'
        result = a.assess(self.inputs, 'replay', 'FX-01')
        self.assertEqual(result['mode'], 'degraded')
        self.assertIsNone(result['assessment'])

    def test_replay_direct_retains_its_arm(self):
        case = next(c for c in CASES if c['variant'] == 'direct_replay')
        result = a.assess(case['inputs'], 'replay', case['id'])
        self.assertEqual(result['policy_variant'], 'direct_replay')

    def test_failure_replay_remains_degraded(self):
        case = next(c for c in CASES if c['id'] == 'FX-19')
        result = a.assess(case['inputs'], 'replay', case['id'])
        self.assertEqual(result['mode'], 'degraded')
        self.assertIsNone(result['assessment'])

    def test_direct_adapter_records_request_and_raw_response(self):
        raw = direct_response()
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key-not-real', 'CLINIC_JEV_MODEL': 'test-version'}), patch.object(a, '_post_json', return_value=raw) as post:
            result = a.assess(self.inputs, 'jev_direct')
        self.assertEqual(result['assessment'], {'direct_route': 'defer'})
        self.assertEqual(result['raw_output'], raw)
        self.assertEqual(result['requested_model'], 'test-version')
        self.assertEqual(post.call_args.args[0], 'https://api.typesafe.ai/v1/systemone')
        self.assertEqual(set(post.call_args.args[1]['questions']), {'route'})
        self.assertNotIn('test-key-not-real', json.dumps(result))

    def test_decomposition_normalizes_only_known_fields(self):
        values = {'warning': 'absent', 'intent': 'appointment_request', 'information_sufficiency': 'sufficient', 'contradiction': 'no', 'scope': 'supported', 'human_review_indication': 'no'}
        raw = {'model': 'mock', 'answers': {k: choice(a.FIELDS[k], v) for k, v in values.items()}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key'}), patch.object(a, '_post_json', return_value=raw):
            result = a.assess(self.inputs, 'jev_decomposed')
        self.assertEqual(result['model_status'], 'valid')
        self.assertIs(result['assessment']['contradiction'], False)
        self.assertIs(result['assessment']['human_review_indication'], False)

    def test_malformed_distributions_and_labels_rejected(self):
        bad = []
        for value in [math.nan, math.inf, -0.1, 1.1, True, '0.5']:
            item = direct_response()
            item['answers']['route']['probabilities']['defer'] = value
            bad.append(item)
        item = direct_response(); item['answers']['route']['choice'] = 'diagnosis'; bad.append(item)
        item = direct_response(); item['answers']['route']['probabilities']['extra'] = 0; bad.append(item)
        item = direct_response(); item['answers']['route']['probabilities']['defer'] = .9; bad.append(item)
        item = direct_response(); item['answers']['route']['confidence'] = False; bad.append(item)
        for raw in bad:
            with self.subTest(raw=repr(raw)), patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key'}), patch.object(a, '_post_json', return_value=raw):
                result = a.assess(self.inputs, 'jev_direct')
                self.assertEqual(result['model_status'], 'malformed')
                json.dumps(result, allow_nan=False)  # invalid outputs must still be auditable

    def test_choice_probability_disagreement_is_rejected(self):
        raw = direct_response('defer')
        raw['answers']['route']['choice'] = 'routine_appointment'
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key'}), patch.object(a, '_post_json', return_value=raw):
            self.assertEqual(a.assess(self.inputs, 'jev_direct')['model_status'], 'malformed')

    def test_missing_answers_extra_answers_and_model_identity_rejected(self):
        for raw in [{'model': 'mock', 'answers': {}}, {'model': 'mock', 'answers': dict(direct_response()['answers'], extra={})}, {'answers': direct_response()['answers']}]:
            with self.subTest(raw=raw), patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key'}), patch.object(a, '_post_json', return_value=raw):
                self.assertEqual(a.assess(self.inputs, 'jev_direct')['model_status'], 'malformed')

    def test_provider_http_error_not_exposed(self):
        err = urllib.error.HTTPError('https://api.typesafe.ai/v1/systemone', 401, 'sensitive diagnostic', {}, None)
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key'}), patch.object(a, '_post_json', side_effect=err):
            result = a.assess(self.inputs, 'jev_direct')
        self.assertEqual(result['mode'], 'degraded')
        self.assertNotIn('sensitive diagnostic', json.dumps(result))

    def test_wall_deadline_discards_late_result(self):
        def slow():
            time.sleep(.15)
            return {'mode': 'live_model'}
        start = time.monotonic()
        with patch.object(a, 'DEADLINE_SECONDS', .02):
            result = a._bounded_call(slow)
        self.assertLess(time.monotonic() - start, .12)
        self.assertEqual(result['model_status'], 'timeout')

    def test_llm_requires_exact_bounded_json(self):
        parsed = {k: v[0] for k, v in a.FIELDS.items()}
        raw = {'model': 'mock-llm', 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(parsed)}}]}
        with patch.dict(os.environ, {'CLINIC_LLM_API_KEY': 'test-key', 'CLINIC_LLM_MODEL': 'test-model'}), patch.object(a, '_post_json', return_value=raw):
            result = a.assess(self.inputs, 'llm')
        self.assertEqual(result['model_status'], 'valid')
        self.assertNotIn('probabilities', result['assessment'])

    def test_llm_refusal_and_extra_medical_prose_rejected(self):
        for message in [{'refusal': 'cannot assess', 'content': None}, {'content': json.dumps({'diagnosis': 'invented'})}]:
            raw = {'model': 'mock-llm', 'choices': [{'finish_reason': 'stop', 'message': message}]}
            with patch.dict(os.environ, {'CLINIC_LLM_API_KEY': 'test-key', 'CLINIC_LLM_MODEL': 'test-model'}), patch.object(a, '_post_json', return_value=raw):
                self.assertEqual(a.assess(self.inputs, 'llm')['model_status'], 'malformed')

    def test_unknown_variant_degrades(self):
        self.assertEqual(a.assess(self.inputs, 'unknown')['mode'], 'degraded')

    def test_rejected_raw_json_retains_text_and_question_provenance(self):
        raw_text = '{"answers": {invalid synthetic response'
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-key'}), patch.object(a, '_post_json', side_effect=a.InvalidModelOutput(raw_text)):
            result = a.assess(self.inputs, 'jev_direct')
        self.assertEqual(result['model_status'], 'malformed')
        self.assertEqual(result['raw_response_text'], raw_text)
        self.assertEqual(len(result['questions_hash']), 64)
        self.assertEqual(result['raw_request']['state']['inputs'], self.inputs)


if __name__ == '__main__':
    unittest.main()
