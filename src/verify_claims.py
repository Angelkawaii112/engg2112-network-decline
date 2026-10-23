"""
Re-derive the figures RESULTS.md publishes, and fail if any of them has moved.

A results file full of measured numbers rots the moment a default changes, and this
one has forty of them. Checking by hand found exactly that: walkforward.py
defaulted to a start year the documented command did not use, so running it
bare produced a different figure from the one published. Nothing was wrong with
either number, but anyone reproducing the work would have concluded otherwise.

It also now asserts the purge, because that correction is worth more than the
figures it changed: if a future edit drops it, the numbers go back up and the
file says so.

So the claims are asserted here instead. Each entry names a figure in the
README and the computation behind it. Tolerances are deliberately tight, since
every pipeline in this project is seeded; a figure that drifts has changed
because the code changed, which is exactly what should fail.

This takes a few minutes, most of it in the threshold sweep.

Usage:
    python src/verify_claims.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score

import anatomy
import clustering
import costs
import persistence
import walkforward
from compare import recall_at_budget
from coverage import attrition
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import (add_persistent, purge, shrink_speed, shrinkage_constant)

SPLIT, START = 2024, 2021


def build(panel_path, split_year):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    return raw, add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))


def headline(df, feats):
    d = df.dropna(subset=feats + ["fwd_1", "fwd_2"])
    train, test = d[d.year < SPLIT], d[d.year >= SPLIT]
    leaked = len(train)
    train = purge(train, test.t.min())
    y = test.persistent.astype(int)
    aps, recs = [], []
    for seed in range(10):
        m = RandomForestClassifier(n_estimators=400, class_weight="balanced",
                                   min_samples_leaf=5, random_state=seed, n_jobs=-1)
        m.fit(train[feats], train.persistent.astype(int))
        p = m.predict_proba(test[feats])[:, 1]
        aps.append(average_precision_score(y, p))
        recs.append(recall_at_budget(y, p, 0.15))
    rev = test.speed_vs_own_mean.values
    return {"declines": int(y.sum()), "ap": np.mean(aps), "rec": np.mean(recs),
            "ap_rev": average_precision_score(y, rev),
            "purged": leaked - len(train), "train": len(train)}


def main(panel_path):
    feats = FEATURES + LAG_FEATURES
    raw, df = build(panel_path, SPLIT)
    checks = []

    def check(claim, got, want, tol):
        checks.append((claim, got, want, abs(got - want) <= tol))

    panel = pd.read_csv(panel_path)
    check("panel is 5,085 region-quarters", len(panel), 5085, 0)
    check("455 New South Wales regions", panel.region.nunique(), 455, 0)
    check("shrinkage constant is 125 tests",
          shrinkage_constant(raw, SPLIT), 125, 0)

    h = headline(df, feats)
    check("17 declines in the test years", h["declines"], 17, 0)
    check("234 leaking rows are purged", h["purged"], 234, 0)
    check("1,978 training rows remain", h["train"], 1978, 0)
    check("average precision 0.436", h["ap"], 0.436, 0.01)
    check("recall at a 15% budget 0.765", h["rec"], 0.765, 0.01)
    check("mean reversion 0.331", h["ap_rev"], 0.331, 0.005)

    att = attrition(df, feats)
    check("regional starts at 603 region-quarters",
          att.loc["in the panel", "regional"], 603, 0)
    check("regional ends at 39", att.loc["outcome also known", "regional"], 39, 0)

    wf = pd.DataFrame([r for r in (
        walkforward.one_quarter(df.dropna(subset=feats), t, feats, 400, 10)
        for t in sorted(df[df.year >= START].t.unique())) if r])
    check("13 quarters are scorable", len(wf), 13, 0)
    check("rolling-origin recall 0.811", wf.rec_model.mean(), 0.811, 0.01)
    check("the baseline's rolling recall 0.863", wf.rec_reversion.mean(), 0.863, 0.01)
    check("the model wins recall in 3 quarters",
          int((wf.rec_model > wf.rec_reversion).sum()), 3, 0)

    _, falls = persistence.find_falls(df)
    table = persistence.follow(df, falls)
    check("210 falls of at least 20%", len(falls), 210, 0)
    check("68% undo themselves within two quarters",
          1 - table.iloc[1]["share"], 0.68, 0.01)
    per = falls.groupby("region").size()
    check("23 regions fell three times or more", int((per >= 3).sum()), 23, 0)

    an = anatomy.add_next_quarter_changes(df)
    hit = an[an.persistent & an.d_down_mbps.notna() & an.fwd_1.notna()]
    check("upload fell too in 86% of declines",
          anatomy.signatures(hit)["upload fell as well"].mean(), 0.86, 0.01)
    check("devices grew in 30% of declines",
          anatomy.signatures(hit)["devices grew, congestion"].mean(), 0.30, 0.01)

    width = max(len(c) for c, _, _, _ in checks)
    bad = 0
    for claim, got, want, ok in checks:
        bad += not ok
        mark = "ok" if ok else "MOVED"
        print(f"  {mark:>5}  {claim:<{width}}  got {got:>9.3f}  want {want:>9.3f}")
    print(f"\n{len(checks) - bad} of {len(checks)} published figures reproduce.")
    return 1 if bad else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    a = p.parse_args()
    sys.exit(main(a.panel))
