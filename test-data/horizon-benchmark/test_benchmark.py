"""Offline math/protocol regression checks, no GPU and no production imports."""
import unittest

from common import HERE, average_precision, load, metrics, windows
from optimize import AGGREGATIONS, THRESHOLDS, calculate, candidates


class BenchmarkTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(len(THRESHOLDS), 18)
        self.assertEqual((THRESHOLDS[0], THRESHOLDS[-1]), (.1, .95))

    def test_categories(self):
        spec = load(HERE / 'hypotheses.json')['categories']
        self.assertEqual(len(spec), 12)
        for category in spec.values():
            self.assertEqual(len(category['hypotheses']), 8)
            self.assertEqual([h['polarity'] for h in category['hypotheses']].count('exclude'), 2)

    def test_windows(self):
        self.assertEqual([len(w) for w in windows('x' * 1900)], [900, 900, 300])
        self.assertEqual(list(windows('')), [''])
        with self.assertRaises(ValueError):
            list(windows('x', 10, 10))

    def test_metrics(self):
        m = metrics([True, False, True, False], [True, True, False, False])
        self.assertEqual([m[k] for k in ('TP', 'FP', 'FN', 'TN')], [1, 1, 1, 1])
        self.assertEqual(m['F1'], .5)

    def test_ap(self):
        self.assertEqual(average_precision([1, 0], [.9, .1]), 1)
        self.assertEqual(average_precision([1, 0], [.5, .5]), .5)
        self.assertEqual(average_precision([0, 0], [.9, .1]), 0)

    def test_local_exclusion(self):
        cfg = dict(hypotheses=['h0', 'h6'], combine='product', aggregation='max')
        self.assertAlmostEqual(calculate([[.9, .9], [.8, .1]], [('c', 'h0'), ('c', 'h6')], 'c', cfg), .72)

    def test_candidate_grid(self):
        self.assertEqual(len(list(candidates())), 76)
        self.assertEqual(len(AGGREGATIONS), 4)

    def test_all_modes(self):
        order = [('c', f'h{i}') for i in range(8)]
        for cfg in candidates():
            for agg in AGGREGATIONS:
                score = calculate([[.5] * 8, [.2] * 8], order, 'c', dict(**cfg, aggregation=agg))
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 1)


if __name__ == '__main__':
    unittest.main()