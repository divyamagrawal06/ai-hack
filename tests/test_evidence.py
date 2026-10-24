"""Evidence provenance is an application property, not generated reasoning."""
import unittest
from clinic.policy import decide, segment_text


class EvidenceTests(unittest.TestCase):
    def test_unicode_offsets_round_trip_original_text(self):
        text = 'Invented café example. Now I cannot breathe!\nAnother sentence.'
        segments = segment_text(text)
        self.assertEqual(len({s['id'] for s in segments}), len(segments))
        for segment in segments:
            self.assertEqual(text[segment['start']:segment['end']], segment['text'])

    def test_local_warning_preserves_original_text_without_fabricated_model_spans(self):
        text = 'I cannot breathe right now.'
        result = decide({'symptom_text': text}, variant='no_ai')
        self.assertEqual(result['primary_rule'], 'E02')
        evidence = next(x for x in result['explanations'] if x['rule']=='E02')['evidence']
        self.assertEqual(evidence['original_text'], text)
        self.assertEqual(result['selected_evidence_ids'], [])
        self.assertIsNone(evidence['assessment_warning'])


if __name__ == '__main__':
    unittest.main()
