"""Checks for release-date leakage, missing-data handling and split purging."""
from settings import ROOT, SOURCE, check_source
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import prepare_population
from evaluate import training_mask



class TemporalIntegrity(unittest.TestCase):
    def test_release_asof_and_unmatched_rows_are_preserved(self):
        panel = pd.DataFrame({"region": ["a", "a", "a", "b"],
                              "year": [2022, 2022, 2023, 2023], "quarter": [2, 3, 3, 3]})
        mapping = pd.DataFrame({"region": ["a", "b"], "sa2": ["101021007", None],
                                "match_status": ["matched", "unmatched"]})
        population = pd.DataFrame({"sa2": ["101021007"] * 3, "sa2_name": ["Example"] * 3,
                                   "published": ["2022-07-26", "2023-08-31", "2024-03-26"],
                                   "growth_rate": [0.02, 0.03, 99.0], "vintage": ["initial", "revised", "future"]})
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            target = Path(temp)
            (target / "data/derived").mkdir(parents=True)
            (target / "results").mkdir()
            with patch.object(prepare_population, "ROOT", target):
                result = prepare_population.join_available_population(panel, mapping, population)
        self.assertEqual(len(result), len(panel))
        self.assertTrue(pd.isna(result.iloc[0].growth_rate))
        self.assertEqual(result.iloc[0].population_missing_reason, "no_historical_release_available")
        self.assertAlmostEqual(result.iloc[1].growth_rate, 0.02)
        self.assertAlmostEqual(result.iloc[2].growth_rate, 0.03)
        self.assertEqual(result.iloc[3].population_missing_reason, "no_unique_sa2_match")
        self.assertNotIn("future", result.vintage.dropna().values)

    def test_purged_training_removes_boundary_crossing_outcomes(self):
        frame = pd.DataFrame({"year": [2023] * 4 + [2024],
                              "t": [2023 * 4 + q for q in range(1, 5)] + [2024 * 4 + 1]})
        cutoff = 2024 * 4 + 1
        self.assertEqual(training_mask(frame, "original", cutoff).tolist(), [True] * 4 + [False])
        mask = training_mask(frame, "horizon_purged", cutoff)
        self.assertEqual(mask.tolist(), [True, True, False, False, False])
        self.assertTrue(((frame.loc[mask, "t"] + 2) < cutoff).all())


if __name__ == "__main__":
    unittest.main()
