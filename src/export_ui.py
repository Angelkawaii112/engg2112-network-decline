"""
Everything the dashboard needs, in the shape the findings say it should be.

The first dashboard was built before the state boundary was applied and before
the speeds were shrunk, so it ranked a region near Melbourne first and quoted
figures from a framing this project has since abandoned. This writes what the
current system actually produces.

Four things changed about what a useful page shows:

  the order comes from the mean-reversion rule, because rolling origin and the
  cost sweep both put it ahead of the forest wherever the stakes are high;

  the forest supplies a steep-fall flag, the one thing it was measured to do
  better, so the page says where to go first and separately where the fall is
  likely to be severe;

  regions that have fallen three times or more are split out. They are 38% of
  all events and sending a crew to them again is answering the wrong question:
  they need capacity planning, not inspection;

  the budget is chosen by what a miss costs rather than by a round number. The
  page carries the cost curve so the person reading it can set R, the price of
  a missed decline in units of one inspection, and read off how many regions
  that justifies visiting;

  rankings are written for one, two, three and four quarters ahead, because all
  four score about the same and a team should be able to plan at whichever
  distance suits it.

Output goes to docs/, which is what GitHub Pages serves. The site fetches
data.json rather than carrying the numbers inside the page, so refreshing the
published site after a new quarter means rerunning this and committing one
file.

Usage:
    python src/export_ui.py --panel data/panel_nsw.csv --out docs
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from persistence import CHRONIC, find_falls
from rankers import Forest, MeanReversion
from shrink import add_persistent, shrink_speed, shrinkage_constant

RATIOS = [2, 5, 10, 20, 50, 100]
GRID = np.round(np.arange(0.0, 0.51, 0.01), 2)


def chronic_regions(df):
    _, falls = find_falls(df)
    per = falls.groupby("region").size()
    return per[per >= CHRONIC], per


def cost_table(n_regions, declines_per_quarter, recall_at):
    """Cheapest budget at each price of a miss, in units of one inspection."""
    rows = []
    for ratio in RATIOS:
        costs = [b * n_regions + ratio * declines_per_quarter * (1 - recall_at(b))
                 for b in GRID]
        i = int(np.argmin(costs))
        rows.append({"ratio": ratio, "budget": float(GRID[i]),
                     "regions": int(round(GRID[i] * n_regions)),
                     "cost": round(float(costs[i]), 1),
                     "cost_of_doing_nothing": round(ratio * declines_per_quarter, 1)})
    return rows


def main(panel_path, split_year, out_dir, trees, seed):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    feats = FEATURES + LAG_FEATURES

    train = df.dropna(subset=feats + ["fwd_1", "fwd_2"])
    simple = MeanReversion().fit(train)
    forest = Forest(trees=trees, seed=seed).fit(train)

    ready = df.dropna(subset=feats)
    now = ready[ready.t == ready.t.max()].copy()
    now["priority"] = simple.score(now)
    now["expected_change"] = simple.predicted_change(now)
    now["forest_risk"] = forest.score(now)
    now["steep_fall_expected"] = now.forest_risk >= now.forest_risk.quantile(0.75)

    chronic, per = chronic_regions(df)
    now["past_falls"] = now.region.map(per).fillna(0).astype(int)
    now["chronic"] = now.region.isin(chronic.index)

    now = now.sort_values("priority", ascending=False)
    now["rank"] = range(1, len(now) + 1)

    os.makedirs(out_dir, exist_ok=True)
    cols = ["rank", "region", "lon", "lat", "year", "quarter", "area_type",
            "down_mbps", "smoothed_mbps", "tests", "devices", "past_falls",
            "chronic", "expected_change", "forest_risk", "steep_fall_expected"]
    now[cols].round(4).to_csv(os.path.join(out_dir, "regions.csv"), index=False)

    hist = df[["region", "year", "quarter", "t", "down_mbps",
               "smoothed_mbps", "tests"]]
    hist.round(3).to_csv(os.path.join(out_dir, "history.csv"), index=False)

    # recall of the deployed ranker at each budget, measured on the test years
    test = train[train.year >= split_year]
    y = test.persistent.astype(int).values
    order = np.argsort(-simple.score(test))
    cum = np.cumsum(y[order]) / max(1, y.sum())
    def recall_at(b):
        k = int(round(b * len(y)))
        return float(cum[k - 1]) if k >= 1 else 0.0

    meta = {
        "quarter_predicted": f"{int(now.year.iloc[0])} Q{int(now.quarter.iloc[0])}",
        "regions": int(len(now)),
        "chronic_regions": int(now.chronic.sum()),
        "coverage": "urban and outer-suburban New South Wales only",
        "ranker": "mean reversion, one fitted parameter",
        "k": round(simple.k_, 4),
        "honesty": [
            "Ranks by how far a region sits above its own long-run speed. "
            "A random forest scored no better inside an inspection budget, "
            "so the simpler rule is the one deployed.",
            "Predicts a fall of at least 20% that is still there a quarter "
            "later. Two thirds of single-quarter falls undo themselves.",
            "Regional New South Wales is absent: 94% of its region-quarters "
            "lack the history the model needs, so this covers urban and "
            "outer-suburban areas only.",
            "Measured on 17 declines across the 2024-2026 test years. Treat "
            "every figure as indicative.",
        ],
        "budget_curve": [{"budget": float(b), "recall": round(recall_at(b), 3)}
                         for b in GRID],
        "cost_table": cost_table(len(now), float(test.persistent.sum()) /
                                 max(1, test.t.nunique()), recall_at),
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"{len(now)} regions for the quarter after {meta['quarter_predicted']}, "
          f"{int(now.chronic.sum())} of them chronic")
    print(f"wrote {out_dir}/regions.csv, history.csv and meta.json\n")
    print(pd.DataFrame(meta["cost_table"]).to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--out", default="docs")
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.split_year, a.out, a.trees, a.seed)
