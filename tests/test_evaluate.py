"""Scoring helper tests. These are NOT model accuracy results."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
from build_dataset import validate_rows  # noqa: E402
from evaluate import majority_predictions, score  # noqa: E402


class HelpersTest(unittest.TestCase):
    def setUp(self):
        self.gold = [dict(id='a-zh', language='zh', expected={'search': 'no'}, questions={'search': {'criteria': {'yes': '', 'no': ''}}}),
                     dict(id='b-en', language='en', expected={'search': 'yes'}, questions={'search': {'criteria': {'yes': '', 'no': ''}}})]

    def test_missing_prediction_rejected(self):
        with self.assertRaises(ValueError):
            score(self.gold, [dict(id='a-zh', predicted={'search': 'no'})])

    def test_error_counted_as_wrong(self):
        result = score(self.gold, [dict(id='a-zh', predicted={'search': 'no'}), dict(id='b-en', predicted={})])
        self.assertEqual(result['heads']['search']['accuracy'], .5)
        self.assertEqual(result['heads']['search']['per_label']['yes']['recall'], 0)

    def test_macro_does_not_hide_positive_miss(self):
        result = score(self.gold, [dict(id=r['id'], predicted={'search': 'no'}) for r in self.gold])
        self.assertAlmostEqual(result['heads']['search']['macro_f1_supported'], 1 / 3)

    def test_majority_uses_training_only(self):
        pred = majority_predictions(self.gold, [self.gold[1], self.gold[1], self.gold[0]])
        self.assertTrue(all(p['predicted']['search'] == 'yes' for p in pred))

    def test_family_leak_rejected(self):
        base = dict(group_id='a', family_id='shared', state=dict(message='a', recent_context='', reference_text='', attachments=[], candidate_executors=[]))
        rows = [base | dict(id='a-zh', split='train'), base | dict(id='a-en', split='test')]
        with self.assertRaises(ValueError):
            validate_rows(rows)


if __name__ == '__main__':
    unittest.main()
