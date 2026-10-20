"""
What the device counts say, and the bar any population data has to clear.

Ookla reports how many distinct devices it saw in a tile as well as how many
tests were run there. Neither has been used as a feature so far, and both are
proxies for the thing a congestion story needs: how much demand a cell is
carrying. The ratio of the two is the most useful of them, since a region
running many tests per device is a region where people keep re-testing a
connection that is not satisfying them.

This exists mostly so that the figure quoted to anyone adding external
population data is reproducible. Census population may still help, because
device counts say how many Ookla users a region has today while population
growth says the region is expanding, and a new estate whose towers have not
caught up is exactly the case of interest. But it has to beat this, not the
plain model.

Usage:
    python src/demand.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score

from compare import recall_at_budget
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import add_persistent, purge, shrink_speed, shrinkage_constant

DEMAND = ["devices", "devices_chg", "devices_per_tile",
          "devices_growth_4q", "tests_per_device"]


def add_demand(df):
    """Everything the tile already tells us about how loaded it is."""
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    prev = g.devices.shift(1)
    df["devices_chg"] = (df.devices - prev) / prev
    df["devices_per_tile"] = df.devices / df.n_tiles
    back4 = g.devices.shift(4)
    df["devices_growth_4q"] = (df.devices / back4 - 1).where(g.t.shift(4) - df.t == -4)
    df["tests_per_device"] = df.tests / df.devices
    return df


def score(train, test, feats, trees, seeds):
    y = test.persistent.astype(int)
    aps, rec = [], []
    model = None
    for seed in range(seeds):
        model = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                       min_samples_leaf=5, random_state=seed, n_jobs=-1)
        model.fit(train[feats].fillna(-99), train.persistent.astype(int))
        p = model.predict_proba(test[feats].fillna(-99))[:, 1]
        aps.append(average_precision_score(y, p))
        rec.append(recall_at_budget(y, p, 0.15))
    return np.array(aps), np.array(rec), model


def main(panel_path, split_year, trees, seeds):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_demand(add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year))))

    base = FEATURES + LAG_FEATURES
    df = df.dropna(subset=base + ["fwd_1", "fwd_2"])
    train, test = df[df.year < split_year], df[df.year >= split_year]
    train = purge(train, test.t.min())
    print(f"{len(train):,} train rows after purging, {len(test):,} test rows, "
          f"{int(test.persistent.sum())} declines\n")

    for name, feats in [("current features", base), ("+ demand proxies", base + DEMAND)]:
        aps, rec, model = score(train, test, feats, trees, seeds)
        print(f"{name:20s} AP {aps.mean():.3f} ± {aps.std():.3f}   "
              f"recall@15% {rec.mean():.3f} ± {rec.std():.3f}")

    order = sorted(zip(base + DEMAND, model.feature_importances_), key=lambda x: -x[1])
    print("\nwhere the demand proxies ranked:")
    for i, (f, v) in enumerate(order, 1):
        if f in DEMAND:
            print(f"  #{i:>2}  {f:20s} {v:.3f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seeds", type=int, default=10)
    a = p.parse_args()
    main(a.panel, a.split_year, a.trees, a.seeds)
