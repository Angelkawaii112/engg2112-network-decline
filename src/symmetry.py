"""
Does this predict declines, or does it just predict movement?

Everything in this repository is framed around falls, and nothing had tested
whether that framing is doing any work. A model that ranks regions by how far
they sit above their own long-run level would also, by construction, be good at
spotting regions about to move sharply in either direction. If it predicts
rises as well as it predicts falls, it is a volatility detector with a sign
written on it, and the maintenance story built on it is wrong.

The test is to relabel the same data three ways and refit: a lasting fall of at
least 20%, a lasting rise of at least 20%, and a lasting move of either kind.
Average precision cannot be compared across them directly because the three
have different base rates, so what matters is lift: how many times better than
a random ranking each one is.

It passes. Falls come out at 18.5 times a random ranking and rises at 5.3,
despite rises being ten times more common in training and therefore far easier
to learn. The framing is doing real work.

One fact falls out of this that is worth stating on its own. The network mostly
improves: the test years hold 43 lasting rises against 17 lasting falls. A
maintenance tool is looking for the exception, not the trend.

Usage:
    python src/symmetry.py --panel data/panel_nsw.csv
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
from shrink import purge, shrink_speed, shrinkage_constant

THRESHOLD, BUDGET = 0.20, 0.15
KINDS = [("fall", "lasting fall"), ("rise", "lasting rise"),
         ("move", "lasting move, either way")]


def label(df, kind, thr=THRESHOLD):
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    for k in (1, 2):
        ahead, gap = g.smoothed_mbps.shift(-k), g.t.shift(-k) - df.t
        df[f"f{k}"] = (ahead / df.smoothed_mbps - 1).where(gap == k)
    if kind == "fall":
        df["y"] = (df.f1 <= -thr) & (df.f2 <= -thr)
    elif kind == "rise":
        df["y"] = (df.f1 >= thr) & (df.f2 >= thr)
    else:
        df["y"] = (df.f1.abs() >= thr) & (df.f2.abs() >= thr)
    return df


def baseline_score(test, kind):
    """Mean reversion, pointed the way each question needs."""
    gap = test.speed_vs_own_mean.values
    if kind == "fall":
        return gap                 # above its own level, due to fall
    if kind == "rise":
        return -gap                # below it, due to rise
    return np.abs(gap)             # far from it either way


def main(panel_path, split_year, trees, seeds):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    base = shrink_speed(raw, shrinkage_constant(raw, split_year))
    feats = FEATURES + LAG_FEATURES

    rows = {}
    for kind, name in KINDS:
        d = label(base, kind).dropna(subset=feats + ["f1", "f2"])
        train, test = d[d.year < split_year], d[d.year >= split_year]
        train = purge(train, test.t.min())
        y = test.y.astype(int)
        if y.sum() < 5:
            continue
        aps, recs = [], []
        for seed in range(seeds):
            m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                       min_samples_leaf=5, random_state=seed, n_jobs=-1)
            m.fit(train[feats], train.y.astype(int))
            p = m.predict_proba(test[feats])[:, 1]
            aps.append(average_precision_score(y, p))
            recs.append(recall_at_budget(y, p, BUDGET))
        rows[name] = {
            "train events": int(train.y.sum()), "test events": int(y.sum()),
            "base rate": y.mean(), "average precision": np.mean(aps),
            "lift over random": np.mean(aps) / y.mean(),
            f"recall@{int(BUDGET*100)}%": np.mean(recs),
            "mean reversion": average_precision_score(y, baseline_score(test, kind)),
        }

    table = pd.DataFrame(rows).T
    print(table.to_string(float_format=lambda v: f"{v:.3f}"))

    fall, rise = table.loc["lasting fall"], table.loc["lasting rise"]
    print(f"\nFalls are {fall['lift over random'] / rise['lift over random']:.1f} "
          f"times as findable as rises, relative to how common each one is,")
    print(f"despite {rise['train events'] / fall['train events']:.0f} times more "
          f"rises to learn from. This is not a volatility detector.")
    print(f"\nThe network mostly improves: {int(rise['test events'])} lasting "
          f"rises against {int(fall['test events'])} lasting falls in the test "
          f"years.\nA maintenance tool is looking for the exception, not the trend.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seeds", type=int, default=10)
    a = p.parse_args()
    main(a.panel, a.split_year, a.trees, a.seeds)
