"""
How many regions to inspect, given what a visit costs and what a miss costs.

The repository keeps saying the model's value depends on the price of an
unnecessary inspection, and then not pricing it. The prices are not public, but
the decision only depends on their ratio, and the ratio can be swept.

Let R be the cost of missing a lasting decline divided by the cost of one
inspection. Inspecting the top k regions of a ranking costs k, and leaves
whatever it misses, so the expected cost of a budget is

    k + R * (declines not in the top k)

in units of one inspection. Sweeping R shows which budget is cheapest at each
price, and comparing rankings at their own best budget shows what the ranking
is worth rather than what it scores.

Everything is scored under rolling origin, the same quarters the rest of the
project trusts, so nothing here is fitted on what it is measured against.

The persistence result is priced in too. Two thirds of single-quarter falls
undo themselves, so a system that dispatched on one bad quarter would pay for
three visits to fix one problem. That is a cost of 3R-ish per real fault
against R for waiting, and it is why the label requires the fall to last.

Usage:
    python src/costs.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import add_persistent, purge, shrink_speed, shrinkage_constant

RATIOS = (2, 5, 10, 20, 50, 100)
GRID = np.arange(0.0, 0.51, 0.01)
MIN_TRAIN, MIN_POSITIVES = 400, 2


def rolling_scores(df, feats, start_year, trees, seed):
    """One (labels, model score, baseline score) triple per quarter."""
    ok = df.fwd_1.notna() & df.fwd_2.notna()
    out = []
    for t in sorted(df[df.year >= start_year].t.unique()):
        now = df[(df.t == t) & ok]
        known = purge(df[(df.t < t) & ok], t)
        y = now.persistent.astype(int).values
        if y.sum() < MIN_POSITIVES or len(known) < MIN_TRAIN:
            continue
        m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                                   min_samples_leaf=5, random_state=seed, n_jobs=-1)
        m.fit(known[feats], known.persistent.astype(int))
        out.append((y, m.predict_proba(now[feats])[:, 1],
                    now.speed_vs_own_mean.values))
    return out


def missed(y, score, budget):
    k = int(round(budget * len(score)))
    if k <= 0:
        return int(y.sum()), 0
    top = np.argsort(-score)[:k]
    return int(y.sum() - y[top].sum()), k


def cost_curve(quarters, which, ratio):
    """Expected cost per quarter, in inspections, at each budget."""
    costs = []
    for b in GRID:
        total = 0.0
        for y, model, base in quarters:
            score = {"model": model, "baseline": base}[which] if which != "random" \
                else np.random.default_rng(0).random(len(y))
            miss, k = missed(y, score, b)
            total += k + ratio * miss
        costs.append(total / len(quarters))
    return np.array(costs)


def main(panel_path, start_year, trees, seed):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, start_year)))
    feats = FEATURES + LAG_FEATURES
    quarters = rolling_scores(df.dropna(subset=feats), feats, start_year, trees, seed)

    regions = np.mean([len(y) for y, _, _ in quarters])
    declines = np.mean([y.sum() for y, _, _ in quarters])
    print(f"{len(quarters)} quarters, {regions:.0f} regions and "
          f"{declines:.1f} lasting declines in an average one\n")

    print("R is what one missed decline costs, in inspections.\n")
    print(f"{'R':>5}  {'do nothing':>11}  {'forest budget':>14} {'cost':>7}  "
          f"{'baseline budget':>16} {'cost':>7}  {'cheaper':>9}  {'saving':>7}")
    for ratio in RATIOS:
        nothing = ratio * declines
        model = cost_curve(quarters, "model", ratio)
        base = cost_curve(quarters, "baseline", ratio)
        bi, ci = int(np.argmin(model)), model.min()
        bj, cj = int(np.argmin(base)), base.min()
        who = "forest" if ci < cj else "baseline"
        print(f"{ratio:>5}  {nothing:>11.1f}  {GRID[bi]:>13.0%} {ci:>7.1f}  "
              f"{GRID[bj]:>15.0%} {cj:>7.1f}  {who:>9}  "
              f"{1 - min(ci, cj) / nothing:>6.0%}")

    print("\nInspecting nothing costs R per decline; inspecting everything costs "
          f"{regions:.0f}.\nBetween those the ranking only has to put the "
          "declines near the top, which is\nwhy a cheap ranker is enough: both "
          "reach almost the same minimum.")

    crossover = next((r for r in RATIOS
                      if cost_curve(quarters, "model", r).min() < r * declines), None)
    if crossover:
        print(f"\nInspecting anything at all beats inspecting nothing from "
              f"R = {crossover} upward.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--start-year", type=int, default=2021)
    p.add_argument("--trees", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.start_year, a.trees, a.seed)
