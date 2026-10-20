"""Validate committed aggregates against their ten-seed results, without fitting."""
from pathlib import Path
import numpy as np
import pandas as pd

folder = Path(__file__).resolve().parents[1] / 'results'
summary = pd.read_csv(folder / 'comparison.csv')
seeds = pd.read_csv(folder / 'per_seed_metrics.csv')
paired = pd.read_csv(folder / 'paired_seed_differences.csv')
assert set(seeds.sklearn_version) == set(summary.sklearn_version) == {'1.9.1'}
for row in summary.itertuples():
    group = seeds[(seeds.protocol == row.protocol) & (seeds.model == row.model)]
    assert sorted(group.seed) == list(range(10))
    for column, prefix in [('average_precision', 'ap'), ('recall_at_15', 'recall15')]:
        np.testing.assert_allclose(group[column].mean(), getattr(row, prefix + '_mean'), atol=1e-14)
        np.testing.assert_allclose(group[column].std(ddof=0), getattr(row, prefix + '_std'), atol=1e-14)
for protocol, group in seeds.groupby('protocol'):
    table = group.pivot(index='seed', columns='model', values='average_precision')
    expected = table.plus_population_growth - table.baseline_devices
    np.testing.assert_allclose(expected, paired[paired.protocol == protocol].sort_values('seed').ap_delta, atol=1e-14)
    assert expected.mean() < 0
old = pd.read_csv(folder / 'version_1.6.1_per_seed.csv')
assert set(old.sklearn_version) == {'1.6.1'}
assert round(old[old.feature_set == 'devices_baseline'].ap.mean(), 3) == 0.598
print('Six aggregates, paired differences, version labels and older baseline verified.')
