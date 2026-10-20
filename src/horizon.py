"""
How far ahead this works, and what the answer says about what it is.

The obvious expectation is that accuracy falls away with distance: predicting
next quarter should be easier than predicting four quarters out. It does not
happen. Average precision sits around 0.48 whether the decline starts one
quarter from now or four, and the mean-reversion baseline decays over the same
span, 0.443 down to 0.310, so the model's margin widens with distance rather
than shrinking.

That is not the good news it first appears to be. A model detecting a fault as
it develops would get worse with distance, because the evidence would not exist
yet. One that does equally well at four quarters is not detecting an event at
all; it is recognising a standing condition. A region sitting well above its own
long-run level will come back down, and the model can see that a year before it
happens because the condition is already there.

So the honest description is a triage tool rather than an early warning.
It answers which regions carry the problem, not when the problem will arrive.
A maintenance team can use the horizon to decide how far out to plan, since all
of them are about equally reliable, but nobody should read a four-quarter
prediction as a timetable.

Usage:
    python src/horizon.py --panel data/panel_nsw.csv
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

DROP, BUDGET = -0.20, 0.15
LEADS = (1, 2, 3, 4)
MIN_TRAIN, MIN_POSITIVES = 400, 2


def label_at(df, lead, drop=DROP):
    """A decline that starts `lead` quarters out and is still there after it."""
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    for k in (lead, lead + 1):
        ahead, gap = g.smoothed_mbps.shift(-k), g.t.shift(-k) - df.t
        df[f"h{k}"] = (ahead / df.smoothed_mbps - 1).where(gap == k)
    df["y"] = (df[f"h{lead}"] <= drop) & (df[f"h{lead + 1}"] <= drop)
    return df, [f"h{lead}", f"h{lead + 1}"]


def score_lead(df, cols, feats, start_year, trees, seeds):
    ok = df[cols].notna().all(axis=1)
    rows = []
    for t in sorted(df[df.year >= start_year].t.unique()):
        now = df[(df.t == t) & ok]
        known = purge(df[(df.t < t) & ok], t)
        y = now.y.astype(int)
        if y.sum() < MIN_POSITIVES or len(known) < MIN_TRAIN:
            continue
        aps, recs = [], []
        for seed in range(seeds):
            m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                       min_samples_leaf=5, random_state=seed, n_jobs=-1)
            m.fit(known[feats], known.y.astype(int))
            p = m.predict_proba(now[feats])[:, 1]
            aps.append(average_precision_score(y, p))
            recs.append(recall_at_budget(y, p, BUDGET))
        rev = now.speed_vs_own_mean.values
        rows.append({"events": int(y.sum()), "ap": np.mean(aps),
                     "ap_base": average_precision_score(y, rev),
                     "rec": np.mean(recs),
                     "rec_base": recall_at_budget(y, rev, BUDGET)})
    return pd.DataFrame(rows)


def main(panel_path, start_year, trees, seeds):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    base = shrink_speed(raw, shrinkage_constant(raw, start_year))
    feats = FEATURES + LAG_FEATURES

    print(f"{'quarters ahead':>15}{'scored':>8}{'events':>8}{'AP':>7}{'AP base':>9}"
          f"{'margin':>8}{'recall':>8}{'base':>7}")
    for lead in LEADS:
        labelled, cols = label_at(base, lead)
        r = score_lead(labelled.dropna(subset=feats), cols, feats,
                       start_year, trees, seeds)
        if r.empty:
            print(f"{lead:>15}   nothing scorable"); continue
        print(f"{lead:>15}{len(r):>8}{int(r.events.sum()):>8}{r.ap.mean():>7.3f}"
              f"{r.ap_base.mean():>9.3f}{r.ap.mean() - r.ap_base.mean():>+8.3f}"
              f"{r.rec.mean():>8.3f}{r.rec_base.mean():>7.3f}")

    print("\nAccuracy does not fall away with distance, and the baseline's does,")
    print("so the margin grows. A model detecting a fault as it develops would")
    print("get worse further out. This one is recognising a standing condition,")
    print("which makes it a triage tool and not an early warning: it says which")
    print("regions carry the problem, never when it will arrive.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--start-year", type=int, default=2021)
    p.add_argument("--trees", type=int, default=300)
    p.add_argument("--seeds", type=int, default=3)
    a = p.parse_args()
    main(a.panel, a.start_year, a.trees, a.seeds)
