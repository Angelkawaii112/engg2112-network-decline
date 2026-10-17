"""
Score every region for the next quarter and write the files the dashboard reads.

The model is the one from shrink.py: speeds are shrunk toward each region's own
history before anything is computed, and the label is a decline that is still
there a quarter later. Ranking by its predicted probability is what a
maintenance team can act on, because it answers which cells to visit first
rather than how many crossed a threshold.

Two files come out:

  predictions.csv   one row per region, ranked worst first
  history.csv       the download speed of every region in every quarter

Usage:
    python src/export_predictions.py --panel data/panel_nsw.csv --out ui
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


def main(panel_path, out_dir, trees, seed):
    df = pd.read_csv(panel_path)
    df = add_area_type(add_lags(add_history(add_target(df))))
    c = shrinkage_constant(df, split_year=2024)
    df = add_persistent(shrink_speed(df, c))

    feats = FEATURES + LAG_FEATURES
    ready = df.dropna(subset=feats)

    # train on every region-quarter whose outcome is already known
    train = ready.dropna(subset=["fwd_1", "fwd_2"])
    model = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                   min_samples_leaf=5, random_state=seed, n_jobs=-1)
    model.fit(train[feats], train.persistent.astype(int))

    # score the latest quarter, the one whose outcome is still unknown
    latest = ready.t.max()
    now = ready[ready.t == latest].copy()
    now["risk"] = model.predict_proba(now[feats])[:, 1]
    now = now.sort_values("risk", ascending=False)
    now["rank"] = range(1, len(now) + 1)

    cols = ["rank", "region", "lon", "lat", "year", "quarter", "down_mbps",
            "lat_ms", "tests", "n_tiles", "area_type", "pct_change",
            "smoothed_mbps", "risk"]
    os.makedirs(out_dir, exist_ok=True)
    now[cols].round(4).to_csv(os.path.join(out_dir, "predictions.csv"), index=False)

    hist = df[["region", "year", "quarter", "t", "down_mbps",
               "smoothed_mbps", "tests"]]
    hist.round(3).to_csv(os.path.join(out_dir, "history.csv"), index=False)

    q = f"{int(now.year.iloc[0])} Q{int(now.quarter.iloc[0])}"
    print(f"shrinkage constant {c:.0f} tests")
    print(f"trained on {len(train):,} region-quarters, "
          f"{train.persistent.sum()} of them declines")
    print(f"scored {len(now):,} regions for the quarter after {q}")
    print(f"risk score: median {now.risk.median():.3f}, highest {now.risk.max():.3f}")
    print(f"\nwrote {out_dir}/predictions.csv and {out_dir}/history.csv")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--out", default="ui")
    p.add_argument("--trees", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.out, a.trees, a.seed)
