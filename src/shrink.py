"""
The fix that made the model worth using: measure before predicting.

A region's speed for a quarter is the median of however many tests people
happened to run there. With 59 tests one quarter and 200 the next, the median
moves on its own, and a "20% decline" built from those two numbers is often
nothing but that movement. The earlier model scored 0.385 against a
mean-reversion baseline's 0.347, which is what chasing sampling noise looks
like: the baseline wins because a bounce is exactly what mean reversion
predicts.

Two changes follow from that diagnosis.

  shrink_speed   pull each quarter's median toward the region's own history,
                 weighted by how many tests stand behind it. A region with
                 many tests keeps its number; a thinly measured one is mostly
                 told what it has usually been.

  add_persistent label a decline only when the region is still down a quarter
                 later. A maintenance team does not want to be sent to a cell
                 that recovered on its own, and a bounce is precisely what the
                 baseline is good at.

The shrinkage constant is the median test count of the training years, so a
typical region trusts this quarter and its own history equally. It is read
from the training split alone and never tuned against the test years.

One more thing has to be kept out of the training set, and was not at first.
A row's label is built from the two quarters after it, so a row from 2023 Q3
is labelled using 2024 Q1 - a quarter the model is about to be tested on. Those
rows have to be dropped. Keeping them lifted average precision from 0.436 to
0.551, and a control that removed the same number of rows at random scored
0.536, so nearly all of that gap was the leak rather than the smaller training
set. A teammate found this while trying to reproduce the figures.

Usage:
    python src/shrink.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score

from compare import BUDGETS, recall_at_budget
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)

DROP = -0.20


def shrinkage_constant(df, split_year):
    """How many tests make this quarter's median as trustworthy as the past."""
    return float(df[df.year < split_year].tests.median())


def shrink_speed(df, c):
    df = df.sort_values(["region", "t"]).copy()
    prior = df.groupby("region").down_mbps.transform(
        lambda s: s.shift(1).expanding().mean())
    prior = prior.fillna(df.down_mbps)          # first quarter has no history
    w = df.tests / (df.tests + c)
    df["smoothed_mbps"] = w * df.down_mbps + (1 - w) * prior
    return df


def purge(train, first_test_t, horizon=2):
    """Drop training rows whose label is built from the test period.

    A row at time t is labelled using t+1 and t+2, so any row within `horizon`
    quarters of the test split is labelled with data the model is about to be
    scored on. This is the standard purge from time-series cross-validation and
    it is not optional: leaving those rows in is how a split that looks honest
    reports a number it has not earned.
    """
    return train[train.t + horizon < first_test_t]


def add_persistent(df, drop=DROP, col="smoothed_mbps"):
    """Down by `drop` next quarter and still down the quarter after."""
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    for k in (1, 2):
        ahead = g[col].shift(-k)
        gap = g.t.shift(-k) - df.t
        df[f"fwd_{k}"] = (ahead / df[col] - 1).where(gap == k)
    df["persistent"] = (df.fwd_1 <= drop) & (df.fwd_2 <= drop)
    return df


def main(panel_path, split_year, trees, seeds):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    c = shrinkage_constant(raw, split_year)

    df = add_persistent(shrink_speed(raw, c))
    # keep the unsmoothed change too, to check the labels describe real declines
    g = df.sort_values(["region", "t"]).groupby("region")
    df["raw_fwd_1"] = (g.down_mbps.shift(-1) / df.down_mbps - 1).where(
        g.t.shift(-1) - df.t == 1)

    feats = FEATURES + LAG_FEATURES
    df = df.dropna(subset=feats + ["fwd_1", "fwd_2", "raw_fwd_1"])
    train, test = df[df.year < split_year], df[df.year >= split_year]
    kept = purge(train, test.t.min())
    dropped = len(train) - len(kept)
    train = kept
    y = test.persistent.astype(int)
    hit = test[test.persistent]

    print(f"shrinkage constant {c:.0f} tests, taken from the training years")
    print(f"{len(train):,} train rows after purging {dropped} whose labels "
          f"reach into the test years")
    print(f"{len(test):,} test rows, {y.sum()} declines, "
          f"base rate {y.mean():.3f}")
    print(f"those declines on the unsmoothed numbers: median "
          f"{hit.raw_fwd_1.median():+.3f}, "
          f"{(hit.raw_fwd_1 <= DROP).mean():.0%} fell at least 20% there too\n")

    scores, imp = [], None
    for seed in range(seeds):
        m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                   min_samples_leaf=5, random_state=seed, n_jobs=-1)
        m.fit(train[feats], train.persistent.astype(int))
        scores.append(m.predict_proba(test[feats])[:, 1])
        imp = m.feature_importances_

    rows = {}
    aps = [average_precision_score(y, s) for s in scores]
    rows[f"random forest ({seeds} seeds)"] = {
        "average_precision": np.mean(aps),
        **{f"recall@{int(b*100)}%": np.mean([recall_at_budget(y, s, b) for s in scores])
           for b in BUDGETS}}
    mr = test.speed_vs_own_mean.values       # above its own mean, so due to fall
    rows["mean reversion"] = {
        "average_precision": average_precision_score(y, mr),
        **{f"recall@{int(b*100)}%": recall_at_budget(y, mr, b) for b in BUDGETS}}
    rows["random inspection"] = {"average_precision": y.mean(),
                                 **{f"recall@{int(b*100)}%": b for b in BUDGETS}}

    print(pd.DataFrame(rows).T.round(3).to_string())
    print(f"\nseed spread on average precision: ±{np.std(aps):.3f}")
    print(f"at a 15% budget the forest finds "
          f"{rows[f'random forest ({seeds} seeds)']['recall@15%'] / 0.15:.1f}x "
          f"what inspecting 15% at random would")

    print("\nmost used features:")
    for f, i in sorted(zip(feats, imp), key=lambda x: -x[1])[:6]:
        print(f"  {f:20s} {i:.3f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seeds", type=int, default=10)
    a = p.parse_args()
    main(a.panel, a.split_year, a.trees, a.seeds)
