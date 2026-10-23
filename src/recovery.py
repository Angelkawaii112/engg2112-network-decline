"""
Once a region has fallen, will it come back on its own?

Two thirds of 20% falls undo themselves within a quarter, which means most of
the alarms a naive system would raise are alarms about nothing. The useful
question at the moment a fall is first seen is not whether it happened but
whether it will stay, and that is the question a crew dispatcher actually has.

So every fall becomes a row, described by what was known the quarter it was
first seen, and labelled by whether the region was back within 20% of its
pre-fall level one quarter later. Rows whose outcome closes inside the period
being scored are purged from training, as everywhere else in this project.

It is predictable, and it is the one task here where the forest earns its
place outright. Scored year by year over 2022-2025, 96 falls, the forest reaches
average precision 0.800 against 0.743 for the obvious rule - small falls
recover - and 0.562 for guessing, and it beats the rule in every one of the
four years. Predicting falls, it never managed that against mean reversion.

The asymmetry is the finding. Whether a region falls is mostly one number, how
far it sits above its own long-run level, so a one-parameter rule is enough.
Whether it recovers depends on several things at once - how far it fell, how
volatile it has been, latency, the two quarters before - and that is the shape
of problem a tree ensemble is for.

Operationally this is the other half of the inspection list: the falls a crew
should not be sent to. Among the third of falls the forest is most confident
will recover, 84% do.

Usage:
    python src/recovery.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score

from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import shrink_speed, shrinkage_constant

DROP = -0.20
YEARS = range(2021, 2026)
MIN_TEST, MIN_TRAIN = 6, 30


def falls_with_outcomes(df, feats, drop=DROP):
    """One row per fall, described as it looked the quarter it was first seen."""
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    after, gap1 = g.smoothed_mbps.shift(-1), g.t.shift(-1) - df.t
    later, gap2 = g.smoothed_mbps.shift(-2), g.t.shift(-2) - df.t

    df["fall"] = ((after / df.smoothed_mbps - 1) <= drop) & (gap1 == 1)
    df["recovered"] = ((later / df.smoothed_mbps - 1) > drop).where(gap2 == 2)
    falls = df[df.fall & df.recovered.notna()].copy()

    # the decision is taken a quarter after the fall began, with that quarter's data
    seen = g[feats].shift(-1)
    for col in feats:
        falls[col] = seen.loc[falls.index, col]
    falls["fall_size"] = (after / df.smoothed_mbps - 1).loc[falls.index]
    return falls.dropna(subset=feats + ["fall_size"])


def by_year(falls, feats, trees, seeds):
    rows = []
    for year in YEARS:
        test = falls[falls.year == year]
        if len(test) < MIN_TEST or test.recovered.nunique() < 2:
            continue
        train = falls[falls.t + 2 < test.t.min()]      # outcomes closed before
        if len(train) < MIN_TRAIN:
            continue
        y = test.recovered.astype(int).values
        probs = []
        for seed in range(seeds):
            m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                       min_samples_leaf=3, random_state=seed, n_jobs=-1)
            m.fit(train[feats], train.recovered.astype(int))
            probs.append(m.predict_proba(test[feats])[:, 1])
        p = np.mean(probs, axis=0)
        rule = test.fall_size.values                  # smaller fall, likelier to recover
        k = max(1, len(test) // 3)
        rows.append({
            "year": year, "falls": len(test), "trained on": len(train),
            "recovered": y.mean(),
            "AP forest": average_precision_score(y, p),
            "AP rule": average_precision_score(y, rule),
            "top third, forest": y[np.argsort(-p)[:k]].mean(),
            "top third, rule": y[np.argsort(-rule)[:k]].mean(),
        })
    return pd.DataFrame(rows)


def main(panel_path, start_year, trees, seeds):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = shrink_speed(raw, shrinkage_constant(raw, start_year))
    base = FEATURES + LAG_FEATURES
    falls = falls_with_outcomes(df, base)
    feats = base + ["fall_size"]

    print(f"{len(falls)} falls of at least {abs(DROP):.0%} with a known outcome; "
          f"{falls.recovered.mean():.0%} recovered within one more quarter\n")

    r = by_year(falls, feats, trees, seeds)
    print(r.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    w = r.falls
    mean = lambda c: np.average(r[c], weights=w)
    print(f"\n{len(r)} years, {int(w.sum())} falls scored, weighted by falls per year")
    print(f"  average precision   forest {mean('AP forest'):.3f}   rule "
          f"{mean('AP rule'):.3f}   guessing {mean('recovered'):.3f}   "
          f"forest ahead in {int((r['AP forest'] > r['AP rule']).sum())} of {len(r)}")
    print(f"  top third recovered forest {mean('top third, forest'):.0%}     rule "
          f"{mean('top third, rule'):.0%}")
    print("\nWhether a region falls is mostly one number, so one rule is enough.")
    print("Whether it recovers depends on several at once, which is what a forest is for.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--start-year", type=int, default=2021)
    p.add_argument("--trees", type=int, default=300)
    p.add_argument("--seeds", type=int, default=10)
    a = p.parse_args()
    main(a.panel, a.start_year, a.trees, a.seeds)
