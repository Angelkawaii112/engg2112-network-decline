"""
Who the system can see, and who it drops before the model is ever trained.

Reporting one accuracy figure for New South Wales hides the thing that matters
most about this dataset. Ookla's tiles exist where people ran speed tests, so
a region with few users produces few tests, and a region with few tests cannot
support the history the model reads. The places with the worst service are the
places the system knows least about.

This counts, at each stage of the pipeline, how many region-quarters survive in
each kind of area, and then asks what a 15% inspection budget actually visits.
The answer belongs in the report next to the headline recall, not underneath
it.

Usage:
    python src/coverage.py --panel data/panel.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import add_persistent, shrink_speed, shrinkage_constant

AREAS = ["urban", "outer", "regional"]


def attrition(full, feats):
    """How many region-quarters each stage of the pipeline leaves behind."""
    stages = {
        "in the panel": full,
        "has every feature": full.dropna(subset=feats),
        "outcome also known": full.dropna(subset=feats + ["fwd_1", "fwd_2"]),
    }
    return pd.DataFrame({name: d.area_type.value_counts() for name, d in stages.items()}).T[AREAS]


def why_dropped(full, feats):
    """What regional areas are missing, in the terms the model needs."""
    rows = {}
    for a in AREAS:
        s = full[full.area_type == a]
        if s.empty:
            continue
        rows[a] = {
            "regions": s.region.nunique(),
            "median tests": s.tests.median(),
            "median quarters per region": s.groupby("region").size().median(),
            "share missing a feature": s[feats].isna().any(axis=1).mean(),
        }
    return pd.DataFrame(rows).T


def who_gets_inspected(full, feats, split_year, budget, trees, seed):
    df = full.dropna(subset=feats + ["fwd_1", "fwd_2"])
    train, test = df[df.year < split_year], df[df.year >= split_year].copy()
    m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                               min_samples_leaf=5, random_state=seed, n_jobs=-1)
    m.fit(train[feats], train.persistent.astype(int))
    test["risk"] = m.predict_proba(test[feats])[:, 1]

    k = int(round(budget * len(test)))
    test["inspected"] = test.risk.rank(ascending=False, method="first") <= k

    rows = {}
    for a in AREAS:
        s = test[test.area_type == a]
        pos = int(s.persistent.sum())
        rows[a] = {
            "region-quarters": len(s),
            "declines": pos,
            "found": (s[s.persistent].inspected.sum() / pos) if pos else float("nan"),
            "share of the budget": s.inspected.sum() / k if k else float("nan"),
        }
    return pd.DataFrame(rows).T, k, len(test)


def main(panel_path, split_year, budget, trees, seed):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    full = add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    feats = FEATURES + LAG_FEATURES

    print("Region-quarters surviving each stage\n")
    print(attrition(full, feats).to_string())

    print("\n\nWhat each kind of area brings to the model\n")
    print(why_dropped(full, feats).round(2).to_string())

    table, k, n = who_gets_inspected(full, feats, split_year, budget, trees, seed)
    print(f"\n\nWhere a {budget:.0%} budget goes ({k} of {n} region-quarters)\n")
    print(table.round(3).to_string())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--budget", type=float, default=0.15)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.split_year, a.budget, a.trees, a.seed)
