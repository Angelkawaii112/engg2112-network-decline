"""Local controlled bootstrap diagnostic; never edits repository or installed packages."""
from settings import ROOT, SOURCE, check_source
from contextlib import contextmanager
import inspect
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import _forest
from sklearn.utils import check_random_state, compute_sample_weight

OUT = ROOT / 'results/baseline_investigation'
sys.path.insert(0, str(SOURCE / 'src'))
from demand import DEMAND, add_demand, score
from model import FEATURES, LAG_FEATURES, add_area_type, add_lags, add_history, add_target
from shrink import add_persistent, shrink_speed, shrinkage_constant


def uniform_weighted_trees(tree, bootstrap, X, y, sample_weight, tree_idx, n_trees,
                           verbose=0, class_weight=None, n_samples_bootstrap=None,
                           missing_values_in_feature_mask=None):
    """Uniform bootstrap; class weights multiply the sampled counts at tree fitting."""
    if bootstrap:
        n_samples = X.shape[0]
        indices = check_random_state(tree.random_state).randint(0, n_samples, n_samples_bootstrap)
        counts = np.bincount(indices, minlength=n_samples)
        weights = np.ones(n_samples, dtype=np.float64) if sample_weight is None else sample_weight.copy()
        weights *= counts
        if class_weight == 'balanced_subsample':
            weights *= compute_sample_weight('balanced', y, indices=indices)
    else:
        weights = sample_weight
    tree._fit(X, y, sample_weight=weights, check_input=False,
              missing_values_in_feature_mask=missing_values_in_feature_mask)
    return tree


@contextmanager
def bootstrap_mode(mode):
    original = _forest._parallel_build_trees
    if mode == 'uniform_bootstrap_weighted_fit':
        _forest._parallel_build_trees = uniform_weighted_trees
    try:
        yield
    finally:
        _forest._parallel_build_trees = original


def build_frame(panel='panel_nsw.csv'):
    raw = pd.read_csv(ROOT / 'data/network' / panel)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    c = shrinkage_constant(raw, 2024)
    df = add_demand(add_persistent(shrink_speed(raw, c)))
    return df.dropna(subset=FEATURES + LAG_FEATURES + ['fwd_1', 'fwd_2'])


if __name__ == '__main__':
    if sklearn.__version__ != '1.9.1':
        raise RuntimeError('Bootstrap diagnostic requires scikit-learn 1.9.1')
    OUT.mkdir(exist_ok=True)
    (OUT / 'installed_bootstrap_source.txt').write_text(
        'Installed scikit-learn: ' + sklearn.__version__ + '\n\n' +
        inspect.getsource(_forest._generate_sample_indices) + '\n' +
        inspect.getsource(_forest._parallel_build_trees), encoding='utf-8')
    df = build_frame()
    train, test = df[df.year < 2024], df[df.year >= 2024]
    rows = []
    for mode in ['installed', 'uniform_bootstrap_weighted_fit']:
        with bootstrap_mode(mode):
            for name, features in [('network_history', FEATURES + LAG_FEATURES),
                                    ('devices_baseline', FEATURES + LAG_FEATURES + DEMAND)]:
                aps, recalls, _ = score(train, test, features, 400, 10)
                for seed, (ap, recall) in enumerate(zip(aps, recalls)):
                    rows.append(dict(sklearn_version=sklearn.__version__, mode=mode, feature_set=name, seed=seed,
                                     ap=float(ap), recall15=float(recall)))
                print(mode, name, f'AP {aps.mean():.9f} +/- {aps.std():.9f}; recall {recalls.mean():.9f} +/- {recalls.std():.9f}', flush=True)
                pd.DataFrame(rows).to_csv(OUT / 'bootstrap_per_seed.csv', index=False)
    summaries = []
    for (mode, feature_set), values in pd.DataFrame(rows).groupby(['mode', 'feature_set'], sort=False):
        summaries.append(dict(mode=mode, feature_set=feature_set, ap_mean=values.ap.mean(),
                              ap_std=values.ap.std(ddof=0), recall15_mean=values.recall15.mean(),
                              recall15_std=values.recall15.std(ddof=0)))
    (OUT / 'bootstrap_summary.json').write_text(json.dumps(dict(
        sklearn_version=sklearn.__version__, train_rows=len(train), test_rows=len(test),
        test_positives=int(test.persistent.sum()), results=summaries,
        intervention='Only _forest._parallel_build_trees was replaced in memory within a try/finally context; package and original source files were not edited.'), indent=2), encoding='utf-8')
