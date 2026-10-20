"""Reproduce the baseline with the active environment, without package patching."""
from settings import ROOT, SOURCE
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
sys.path.insert(0, str(SOURCE / 'src'))
import numpy as np
import pandas as pd
import sklearn
from demand import DEMAND, add_demand, score
from model import FEATURES, LAG_FEATURES, add_area_type, add_lags, add_history, add_target
from shrink import add_persistent, shrink_speed, shrinkage_constant


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--panel', type=Path, default=ROOT / 'data/network/panel_nsw.csv')
    args = parser.parse_args()
    raw = pd.read_csv(args.panel)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    constant = shrinkage_constant(raw, 2024)
    frame = add_demand(add_persistent(shrink_speed(raw, constant)))
    frame = frame.dropna(subset=FEATURES + LAG_FEATURES + ['fwd_1', 'fwd_2'])
    train, test = frame[frame.year < 2024], frame[frame.year >= 2024]
    rows = []
    for name, features in [('network_history', FEATURES + LAG_FEATURES),
                           ('devices_baseline', FEATURES + LAG_FEATURES + DEMAND)]:
        aps, recalls, _ = score(train, test, features, 400, 10)
        for seed, (ap, recall) in enumerate(zip(aps, recalls)):
            rows.append(dict(sklearn_version=sklearn.__version__, feature_set=name,
                             seed=seed, ap=ap, recall15=recall))
        print(sklearn.__version__, name, float(aps.mean()), float(aps.std()), flush=True)
    pd.DataFrame(rows).to_csv(ROOT / 'results/baseline_version_per_seed.csv', index=False)
    matrix = train[FEATURES + LAG_FEATURES + DEMAND].fillna(-99).to_csv(index=False, float_format='%.17g').encode()
    metadata = dict(sklearn_version=sklearn.__version__, numpy_version=np.__version__,
                    pandas_version=pd.__version__, python=platform.python_version(),
                    train_matrix_sha256=hashlib.sha256(matrix).hexdigest(),
                    train_rows=len(train), test_rows=len(test), shrinkage_constant=constant)
    (ROOT / 'results/baseline_version_environment.json').write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
