"""
The whole thing as one command, which is also the shape of the deployed system.

Each stage below is a thing that would run on a schedule rather than a thing
somebody does by hand, and the reason they are written as separate stages is
that they fail differently and would be monitored differently:

  collect    read the quarter Ookla published and aggregate tiles into regions.
             Runs once a quarter, a few minutes after the release. Fails loudly
             and is simply retried; nothing downstream can run without it.
  measure    shrink each region's median toward its own history by how many
             tests stand behind it. Deterministic, no model, no training.
  label      mark the declines that lasted, which can only be done for quarters
             old enough to have two quarters after them. This is what makes the
             training set grow by one quarter each time.
  learn      refit on everything whose outcome is known. Cheap enough to redo
             from scratch each quarter, which avoids a stale model drifting
             quietly away from the network it describes.
  rank       score the newest quarter, whose outcome nobody knows yet, and
             write the ranking an inspection team works from.

The watch item is in `learn`: the model is refit on a window that keeps moving,
so the check that matters in production is not accuracy on a fixed test set but
whether this quarter's ranking resembles last quarter's. A ranking that
reshuffles completely means the data changed, not that the network did.

Usage:
    python src/pipeline.py                      # from the stored panel
    python src/pipeline.py --refresh-panel      # rebuild the panel from Ookla first
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import add_persistent, shrink_speed, shrinkage_constant

BUDGET = 0.15


def stage(name, n=None):
    print(f"  {name:<34}" + (f"{n:>8,} rows" if n is not None else ""))


def collect(panel_path, refresh):
    if refresh:
        from build_panel import build
        build(out=panel_path)
    df = pd.read_csv(panel_path)
    stage("collect   region-quarters", len(df))
    return df


def measure(df, split_year):
    df = add_area_type(add_lags(add_history(add_target(df))))
    c = shrinkage_constant(df, split_year)
    df = shrink_speed(df, c)
    stage(f"measure   shrunk toward history (c={c:.0f})", len(df))
    return df


def label(df):
    df = add_persistent(df)
    known = df.fwd_1.notna() & df.fwd_2.notna()
    stage("label     outcome known", int(known.sum()))
    return df


def learn(df, feats, trees, seed):
    train = df.dropna(subset=feats + ["fwd_1", "fwd_2"])
    model = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                   min_samples_leaf=5, random_state=seed, n_jobs=-1)
    model.fit(train[feats], train.persistent.astype(int))
    stage(f"learn     fitted on {int(train.persistent.sum())} declines", len(train))
    return model


def rank(df, model, feats, out_dir, budget):
    ready = df.dropna(subset=feats)
    now = ready[ready.t == ready.t.max()].copy()
    now["risk"] = model.predict_proba(now[feats])[:, 1]
    now = now.sort_values("risk", ascending=False)
    now["rank"] = range(1, len(now) + 1)
    k = max(1, int(round(budget * len(now))))
    now["inspect"] = now["rank"] <= k

    os.makedirs(out_dir, exist_ok=True)
    cols = ["rank", "inspect", "region", "lon", "lat", "year", "quarter",
            "down_mbps", "smoothed_mbps", "tests", "area_type", "risk"]
    path = os.path.join(out_dir, "inspection_list.csv")
    now[cols].round(4).to_csv(path, index=False)
    stage(f"rank      flagged for inspection", k)
    return now, path


def main(panel_path, out_dir, split_year, trees, seed, budget, refresh):
    started = time.time()
    feats = FEATURES + LAG_FEATURES
    print("stage")
    df = collect(panel_path, refresh)
    df = measure(df, split_year)
    df = label(df)
    model = learn(df, feats, trees, seed)
    now, path = rank(df, model, feats, out_dir, budget)

    q = f"{int(now.year.iloc[0])} Q{int(now.quarter.iloc[0])}"
    top = now.head(5)
    print(f"\nranking for the quarter after {q}, written to {path}")
    print(f"\n{'rank':>4}  {'region':<14} {'area':<9} {'Mbps':>7} {'risk':>6}")
    for _, r in top.iterrows():
        print(f"{int(r['rank']):>4}  {int(r.region):<14} {r.area_type:<9} "
              f"{r.down_mbps:>7.0f} {r.risk:>6.2f}")
    covered = now[now.inspect].area_type.value_counts(normalize=True)
    print("\ninspections by area: " +
          ", ".join(f"{a} {covered.get(a, 0):.0%}" for a in ["urban", "outer", "regional"]))
    print(f"finished in {time.time() - started:.1f}s")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel.csv")
    p.add_argument("--out", default="ui")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--budget", type=float, default=BUDGET)
    p.add_argument("--refresh-panel", action="store_true")
    a = p.parse_args()
    main(a.panel, a.out, a.split_year, a.trees, a.seed, a.budget, a.refresh_panel)
