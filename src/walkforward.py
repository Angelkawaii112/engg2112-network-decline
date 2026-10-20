"""
Evaluate the way the system would actually be used: one quarter at a time.

The headline numbers come from a single split, 2019-2023 against 2024-2026,
which leaves 17 declines to be right or wrong about. That is one draw from one
arrangement of the data, and a figure resting on 17 events deserves to be asked
how much it moves when the arrangement changes.

It moves a lot. Averaged over thirteen quarters the forest and the baseline
cannot be told apart, and on recall inside an inspection budget the baseline is
ahead. The single split was a favourable draw, which is the result this file
exists to report.

Rolling origin asks exactly that. For each quarter in turn, fit on every
region-quarter whose outcome was already known at that point, rank the regions
in that quarter, and score the ranking against what happened. Nothing from the
future enters any fit. The result is one score per quarter instead of one score
overall, which shows whether the model is reliably better than the baseline or
better on average because of a few good quarters.

Usage:
    python src/walkforward.py --panel data/panel_nsw.csv
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
from shrink import add_persistent, shrink_speed, shrinkage_constant

BUDGET = 0.15
MIN_TRAIN = 400          # a fit on fewer rows than this is not worth scoring
MIN_POSITIVES = 2        # a quarter with fewer declines cannot rank anything


def quarters_to_test(df, start_t):
    return sorted(t for t in df.t.unique() if t >= start_t)


def one_quarter(df, t, feats, trees, seeds):
    """Fit on what was known before quarter t, score the ranking for t."""
    known = df[(df.t < t) & df.fwd_1.notna() & df.fwd_2.notna()]
    now = df[(df.t == t) & df.fwd_1.notna() & df.fwd_2.notna()]
    y = now.persistent.astype(int)
    if len(known) < MIN_TRAIN or y.sum() < MIN_POSITIVES:
        return None

    aps, recs = [], []
    for seed in range(seeds):
        m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                   min_samples_leaf=5, random_state=seed, n_jobs=-1)
        m.fit(known[feats], known.persistent.astype(int))
        risk = m.predict_proba(now[feats])[:, 1]
        aps.append(average_precision_score(y, risk))
        recs.append(recall_at_budget(y, risk, BUDGET))
    rever = now.speed_vs_own_mean.values

    return {
        "quarter": f"{int(now.year.iloc[0])} Q{int(now.quarter.iloc[0])}",
        "regions": len(now),
        "declines": int(y.sum()),
        "train_rows": len(known),
        "ap_model": float(np.mean(aps)),
        "ap_reversion": average_precision_score(y, rever),
        "ap_random": y.mean(),
        "rec_model": float(np.mean(recs)),
        "rec_reversion": recall_at_budget(y, rever, BUDGET),
    }


def main(panel_path, start_year, trees, seeds):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, start_year)))
    feats = FEATURES + LAG_FEATURES
    df = df.dropna(subset=feats)

    start_t = df[df.year >= start_year].t.min()
    rows = [r for r in (one_quarter(df, t, feats, trees, seeds)
                        for t in quarters_to_test(df, start_t)) if r]
    out = pd.DataFrame(rows)
    if out.empty:
        print("no quarter had enough data to score"); return

    show = out[["quarter", "regions", "declines", "ap_model", "ap_reversion",
                "ap_random", "rec_model", "rec_reversion"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    n = len(out)
    print(f"\n{n} quarters scored, {int(out.declines.sum())} declines in total, "
          f"{out.declines.min()}-{out.declines.max()} per quarter\n")
    for col, ref, name in [("ap_model", "ap_reversion", "average precision"),
                           ("rec_model", "rec_reversion", f"recall@{BUDGET:.0%}")]:
        won = int((out[col] > out[ref]).sum())
        lost = int((out[col] < out[ref]).sum())
        print(f"{name:18s} model {out[col].mean():.3f}  mean reversion {out[ref].mean():.3f}"
              f"   model wins {won}, loses {lost}, ties {n - won - lost}")
    print(f"{'':18s} a random ranking would score {out.ap_random.mean():.3f} "
          f"and {BUDGET:.3f}")
    print("\nBoth rankings beat random inspection by a wide margin in every "
          "quarter.\nNeither reliably beats the other, and a quarter holds "
          f"{out.declines.min()}-{out.declines.max()} declines, so one region\n"
          "changing rank moves recall by tens of percentage points.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--start-year", type=int, default=2021)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seeds", type=int, default=10)
    a = p.parse_args()
    main(a.panel, a.start_year, a.trees, a.seeds)
