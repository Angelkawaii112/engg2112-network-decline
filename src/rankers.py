"""
The two rankers, behind one interface, because the evaluation could not
separate them.

Rolling origin put the forest slightly ahead on average precision and slightly
behind on recall inside an inspection budget, in every threshold tested. When
the evidence does not favour the more complicated thing, the simpler thing
wins: MeanReversion has one fitted number, cannot drift, retrains in
microseconds and can be explained to an operations team in a sentence. It is
the default the pipeline deploys.

The forest is kept, and not out of politeness. It was shown to be the better
of the two on the largest moves, where it is 27% closer and right four times in
five, so the sensible arrangement is to order the inspection list with the
simple rule and let the forest mark the regions it expects to fall furthest.
That is what `combined` does.

Both expose fit/score so the evaluation scripts can treat them alike:

    ranker = MeanReversion().fit(train)
    order  = ranker.score(test)          # larger means inspect sooner

Usage:
    python src/rankers.py --panel data/panel_nsw.csv
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

FEATURE = "speed_vs_own_mean"      # how far a region sits above its own history


class MeanReversion:
    """Rank by how far a region has risen above its own long-run level.

    One parameter, fitted by least squares on the training outcomes. Its sign
    comes from the mechanism rather than the fit: a region above its own
    long-run level is expected to fall back, so k is negative. Its magnitude
    changes nothing about the ordering, and is fitted only so the score can
    also be read as a predicted change rather than an arbitrary number.
    """

    name = "mean reversion"

    def fit(self, df, target="fwd_1"):
        x = df[[FEATURE]].values
        y = df[target].values
        self.k_ = float(np.linalg.lstsq(x, y, rcond=None)[0][0])
        return self

    def score(self, df):
        return df[FEATURE].values          # larger gap, sooner a fall

    def predicted_change(self, df):
        return self.k_ * df[FEATURE].values


class Forest:
    """The random forest, for the magnitude of the fall rather than the order."""

    name = "random forest"

    def __init__(self, trees=400, seed=0):
        self.trees, self.seed = trees, seed
        self.features = FEATURES + LAG_FEATURES

    def fit(self, df, target="persistent"):
        self.model_ = RandomForestClassifier(
            n_estimators=self.trees, class_weight="balanced",
            min_samples_leaf=5, random_state=self.seed, n_jobs=-1)
        self.model_.fit(df[self.features], df[target].astype(int))
        return self

    def score(self, df):
        return self.model_.predict_proba(df[self.features])[:, 1]


def combined(simple, forest, df, flag_top=0.25):
    """Order by the simple rule; mark what the forest thinks will fall hardest."""
    out = pd.DataFrame({"order": simple.score(df), "forest_risk": forest.score(df)},
                       index=df.index)
    cut = out.forest_risk.quantile(1 - flag_top)
    out["steep_fall_expected"] = out.forest_risk >= cut
    return out.sort_values("order", ascending=False)


def main(panel_path, split_year, trees):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    feats = FEATURES + LAG_FEATURES
    df = df.dropna(subset=feats + ["fwd_1", "fwd_2"])
    train, test = df[df.year < split_year], df[df.year >= split_year]
    train = purge(train, test.t.min())
    y = test.persistent.astype(int)

    simple = MeanReversion().fit(train)
    forest = Forest(trees=trees).fit(train)
    print(f"mean reversion fitted k = {simple.k_:+.3f}\n")

    rows = {}
    for r in (simple, forest):
        s = r.score(test)
        rows[r.name] = {"average_precision": average_precision_score(y, s),
                        **{f"recall@{int(b*100)}%": recall_at_budget(y, s, b)
                           for b in (0.10, 0.15, 0.20)}}
    print(pd.DataFrame(rows).T.round(3).to_string())

    latest = test[test.t == test.t.max()]
    order = combined(simple, forest, latest)
    flagged = int(order.steep_fall_expected.head(max(1, int(0.15 * len(order)))).sum())
    print(f"\nlatest quarter: {len(order)} regions ordered by the simple rule, "
          f"{flagged} of the top 15% also flagged by the forest")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--trees", type=int, default=400)
    a = p.parse_args()
    main(a.panel, a.split_year, a.trees)
