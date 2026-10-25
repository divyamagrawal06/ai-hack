"""Report upload, provider contract, source verification and request provenance."""
import base64
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from clinic import reports
from clinic.storage import StoreError, token_hash
import test_api


TEXT = 'Invented note. Report date: 2026-10-01. Age: 34. Dry skin for three weeks.'


def payload(name='note.txt', data=TEXT.encode()):
    return {'filename': name, 'data_base64': base64.b64encode(data).decode(), 'synthetic': True, 'send_to_openai': True}


def extracted():
    return {'document_type': 'clinic_note', 'facts': [{'field': 'symptoms', 'value': 'Dry skin', 'quote': 'Dry skin for three weeks.', 'page': None, 'time_context': 'at_report'}], 'issues': []}


def response(value=None):
    return {'status': 'completed', 'id': 'synthetic-response-id', 'model': reports.DEFAULT_MODEL, 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value or extracted())}]}]}


class ReportTests(unittest.TestCase):
    def test_consent_is_required_before_any_provider_call(self):
        with patch.object(reports, 'call_openai') as provider:
            for field in ['synthetic', 'send_to_openai']:
                body = payload(); body[field] = False
                with self.assertRaises(StoreError): reports.extract(body)
            provider.assert_not_called()

    def test_file_boundaries(self):
        cases = [payload('../note.txt'), payload('note.exe'), payload(data=b''), payload(data=b'\xff'), payload(data=b'\x00'), payload(data=b'x'*20001), payload('note.pdf', b'not a pdf'), payload('note.png', b'not png'), payload('note.jpg', b'not jpeg')]
        body = payload(); body['data_base64'] = '!invalid!'; cases.append(body)
        for body in cases:
            with self.subTest(filename=body['filename'], length=len(body['data_base64'])):
                with self.assertRaises(StoreError): reports.prepare_file(body)

    def test_pdf_page_and_encryption_bounds(self):
        from pypdf import PdfWriter
        for count, encrypted in [(0, False), (9, False), (1, True)]:
            writer = PdfWriter()
            for _ in range(count): writer.add_blank_page(width=400, height=400)
            if encrypted: writer.encrypt('example-password')
            stream = io.BytesIO(); writer.write(stream)
            with self.assertRaises(StoreError): reports.prepare_file(payload('note.pdf', stream.getvalue()))

    def test_source_quote_validation_preserves_words_and_units(self):
        result = reports.validate_result(extracted(), [TEXT.replace('Dry skin', 'Dry\n skin')], True)
        self.assertEqual(result['facts'][0]['quote_verification'], 'normalized_text_match')
        value = extracted(); value['facts'][0]['quote'] = 'Severe pain.'
        with self.assertRaises(ValueError): reports.validate_result(value, [TEXT], True)

    def test_visual_sources_are_not_claimed_as_machine_verified(self):
        value = extracted(); value['facts'][0]['page'] = 1
        for pages in [None, ['']]:
            result = reports.validate_result(copy.deepcopy(value), pages)
            self.assertEqual(result['facts'][0]['quote_verification'], 'visual_review_required')

    def test_page_numbers_cannot_be_invented(self):
        for pages, is_text, page in [(None, False, 2), ([TEXT], True, 1), ([TEXT], False, None), ([TEXT], False, 2), (None, False, True)]:
            value = extracted(); value['facts'][0]['page'] = page
            with self.subTest(pages=pages, is_text=is_text, page=page):
                with self.assertRaises(ValueError): reports.validate_result(value, pages, is_text)

    def test_missing_key_does_not_call_provider(self):
        with patch.object(reports, 'api_key', return_value=''), patch.object(reports, 'call_openai') as provider:
            with self.assertRaises(StoreError) as error: reports.extract(payload())
            self.assertEqual(error.exception.status, 503)
            provider.assert_not_called()

    def test_structured_request_and_provenance(self):
        with patch.object(reports, 'api_key', return_value='test-secret'), patch.object(reports, 'call_openai', return_value=response()) as provider:
            result = reports.extract(payload())
            body, key = provider.call_args.args
            self.assertFalse(body['store'])
            self.assertTrue(body['text']['format']['strict'])
            self.assertEqual(key, 'test-secret')
            self.assertNotIn('test-secret', json.dumps(result))
            self.assertNotIn('data_base64', result)
            self.assertTrue(result['review_required'])
            self.assertFalse(result['local'])
            self.assertEqual(len(result['file_sha256']), 64)

    def test_incomplete_refused_malformed_output_never_imports(self):
        refusal = response(); refusal['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'No'}]
        malformed = response(); malformed['output'] = [None]
        fabricated = extracted(); fabricated['facts'][0]['quote'] = 'not in source'
        for raw in [[], {'status': 'incomplete'}, refusal, malformed, response(fabricated)]:
            with patch.object(reports, 'api_key', return_value='test-secret'), patch.object(reports, 'call_openai', return_value=raw):
                with self.assertRaises(StoreError): reports.extract(payload())
        self.assertTrue(reports.LOCK.acquire(blocking=False)); reports.LOCK.release()

    def test_busy_returns_without_calling_provider(self):
        reports.LOCK.acquire()
        try:
            with patch.object(reports, 'api_key', return_value='test-secret'), patch.object(reports, 'call_openai') as provider:
                with self.assertRaises(StoreError) as error: reports.extract(payload())
                self.assertEqual(error.exception.status, 429)
                provider.assert_not_called()
        finally: reports.LOCK.release()

    def test_credentials_are_not_forwarded_to_redirects(self):
        self.assertIsNone(reports.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))


class ReportApiTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    request = test_api.ApiTests.request

    def upload(self):
        with patch.object(reports, 'api_key', return_value='test-secret'), patch.object(reports, 'call_openai', return_value=response()):
            code, data, _ = self.request('POST', '/api/reports/extract', payload())
        self.assertEqual(code, 200, data)
        return data

    def test_status_never_exposes_credentials(self):
        with patch.object(reports, 'api_key', return_value='test-secret'):
            code, data, _ = self.request('GET', '/api/reports/status')
        self.assertEqual(code, 200)
        self.assertTrue(data['configured'])
        self.assertNotIn('test-secret', json.dumps(data))

    def test_review_and_server_provenance_required(self):
        upload = self.upload()
        body = {'synthetic': True, 'variant': 'no_ai', 'inputs': copy.deepcopy(test_api.FIXTURE), 'report_id': upload['report_id']}
        self.assertEqual(self.request('POST', '/api/requests', body, {'Idempotency-Key': 'review'})[0], 422)
        body.update(report_reviewed=True, report_extraction={'model': 'spoofed'})
        code, saved, _ = self.request('POST', '/api/requests', body, {'Idempotency-Key': 'review'})
        self.assertEqual(code, 201, saved)
        rid = saved['request']['id']
        actual = self.server.store.get(rid, staff=True)
        self.assertEqual(actual['inputs'], body['inputs'])
        self.assertEqual(actual['report_extraction'], upload['report'])
        events = self.server.store.audit(rid)
        self.assertEqual(sum(e['event_type'] == 'report_extraction_review_confirmed' for e in events), 1)

    def test_report_tokens_are_hashed_and_unknown_tokens_rejected(self):
        upload = self.upload()
        with self.server.store.connect() as db:
            row = dict(db.execute('SELECT * FROM report_extractions').fetchone())
        self.assertEqual(row['token_hash'], token_hash(upload['report_id']))
        self.assertNotIn('data_base64', row['data'])
        with self.assertRaises(StoreError): self.server.store.get_report('z'*43)

    def test_large_upload_limit_is_isolated_from_intake(self):
        body = {'extra': 'x'*70000}
        self.assertEqual(self.request('POST', '/api/requests', body)[0], 413)
        self.assertEqual(self.request('POST', '/api/reports/extract', body)[0], 422)

    def test_samples_are_public_and_secret_file_is_not(self):
        self.assertEqual(self.request('GET', '/samples/embedded-instructions.txt')[0], 200)
        self.assertEqual(self.request('GET', '/var/openai-api-key.txt')[0], 404)


if __name__ == '__main__': unittest.main()
