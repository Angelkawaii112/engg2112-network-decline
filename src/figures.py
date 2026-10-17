"""
The four figures the report argues from.

Each one carries a claim that is awkward to make in prose: what the ranking
buys at a given budget, why the speeds had to be shrunk, who the pipeline drops,
and why the test years are not the years the model was trained on. They are
drawn in greyscale with differing line styles and hatching, so nothing depends
on colour surviving a printer.

Usage:
    python src/figures.py --panel data/panel_nsw.csv --out figures
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from compare import recall_at_budget
from coverage import AREAS, attrition
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from shrink import add_persistent, shrink_speed, shrinkage_constant

INK, MID, PALE = "#111111", "#777777", "#c8c8c8"

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "savefig.bbox": "tight",
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": MID, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MID, "ytick.color": MID, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "legend.frameon": False, "legend.fontsize": 7.5,
    "grid.color": "#e8e8e8", "grid.linewidth": 0.6,
})


def prepare(panel_path, split_year):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    full = add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    return raw, full


def fit(full, feats, split_year, trees, seed):
    d = full.dropna(subset=feats + ["fwd_1", "fwd_2"])
    train, test = d[d.year < split_year], d[d.year >= split_year].copy()
    m = RandomForestClassifier(n_estimators=trees, class_weight="balanced",
                               min_samples_leaf=5, random_state=seed, n_jobs=-1)
    m.fit(train[feats], train.persistent.astype(int))
    test["risk"] = m.predict_proba(test[feats])[:, 1]
    return test


def fig_budget(risks, test, out):
    """What inspecting the top K% actually finds. The operating claim."""
    y = test.persistent.astype(int)
    budgets = np.arange(0.02, 0.51, 0.01)
    forest = np.mean([[recall_at_budget(y, r, b) for b in budgets] for r in risks], axis=0)
    rever = [recall_at_budget(y, test.speed_vs_own_mean.values, b) for b in budgets]

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    ax.grid(axis="y")
    ax.plot(budgets * 100, budgets * 100, lw=1.5, color=PALE, ls=(0, (1, 2)),
            label="random inspection")
    ax.plot(budgets * 100, np.array(rever) * 100, lw=2, color=MID, ls=(0, (5, 2)),
            label="mean reversion")
    ax.plot(budgets * 100, forest * 100, lw=2, color=INK, label="model")

    r15 = forest[np.argmin(abs(budgets - 0.15))] * 100
    ax.plot([15], [r15], "o", ms=5, color=INK, zorder=5,
            markeredgecolor="white", markeredgewidth=1)
    ax.annotate(f"{r15:.0f}% found\nat a 15% budget", xy=(15, r15),
                xytext=(21, 46), color=INK, va="center",
                arrowprops=dict(arrowstyle="-", color=MID, lw=0.8))

    ax.set_xlabel("regions inspected (% of all region-quarters)")
    ax.set_ylabel("lasting declines found (%)")
    ax.set_xlim(0, 50); ax.set_ylim(0, 104)
    ax.legend(loc="lower right", borderpad=0.2)
    fig.savefig(os.path.join(out, "fig1_budget.pdf")); plt.close(fig)


def fig_noise(raw, out):
    """Why the speeds are shrunk: quarter-on-quarter change is a test-count artefact."""
    d = raw.dropna(subset=["pct_change"]).copy()
    d = d[d.tests.between(50, 3000)]
    d["band"] = pd.cut(d.tests, [50, 100, 200, 400, 800, 3000])
    g = d.groupby("band", observed=True)["pct_change"]
    mid = [iv.mid for iv in g.groups.keys()]
    spread = g.std().values
    share = d.assign(big=d["pct_change"] <= -0.20).groupby("band", observed=True).big.mean().values

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    ax.grid(axis="y")
    ax.plot(mid, spread, lw=2, color=INK, marker="o", ms=5,
            markeredgecolor="white", markeredgewidth=1)
    for x, s, sh in zip(mid, spread, share):
        ax.annotate(f"{sh:.0%}", (x, s), textcoords="offset points",
                    xytext=(0, 8), ha="center", color=MID, fontsize=7)
    ax.set_xscale("log")
    ax.set_xlabel("speed tests behind the quarter (log scale)")
    ax.set_ylabel("spread of measured change (sd)")
    ax.set_ylim(top=max(spread) * 1.12)
    ax.set_title("labelled: share of quarters recorded as a 20% decline",
                 loc="left", color=MID, fontsize=7.5, pad=8)
    fig.savefig(os.path.join(out, "fig2_noise.pdf")); plt.close(fig)


def fig_coverage(full, feats, out):
    """Who survives to be modelled at all."""
    t = attrition(full, feats)
    stages = list(t.index)
    kept = t / t.loc[stages[0]] * 100          # the counts hide this behind urban's scale
    x = np.arange(len(AREAS)); w = 0.26
    hatches = ["", "///", "..."]
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    ax.grid(axis="y")
    for i, st in enumerate(stages):
        ax.bar(x + (i - 1) * w, kept.loc[st, AREAS].values, w * 0.9,
               color=[INK, MID, PALE][i], hatch=hatches[i], edgecolor="white",
               linewidth=0.8, label=st)
        for j, a in enumerate(AREAS):
            ax.annotate(f"{int(t.loc[st, a]):,}", (j + (i - 1) * w, kept.loc[st, a]),
                        textcoords="offset points", xytext=(0, 3), ha="center",
                        fontsize=6.5, color=MID)
    ax.set_xticks(x); ax.set_xticklabels(["urban", "outer suburban", "regional"])
    ax.set_ylabel("% of the area's region-quarters kept")
    ax.set_ylim(0, 112); ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_title("labelled: region-quarters remaining", loc="left",
                 color=MID, fontsize=7.5, pad=8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3,
              columnspacing=1.0, handlelength=1.6, handletextpad=0.5,
              fontsize=7)
    fig.savefig(os.path.join(out, "fig3_coverage.pdf")); plt.close(fig)


def fig_shift(raw, split_year, out):
    """Training years and test years are not the same network."""
    d = raw.dropna(subset=["pct_change"])
    nat = d.groupby(["year", "quarter"])["pct_change"].median().reset_index()
    nat["label"] = nat.year.astype(str) + " Q" + nat.quarter.astype(str)
    train = nat[nat.year < split_year]

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    ax.grid(axis="y")
    ax.axhline(0, color=MID, lw=0.8)
    ax.axvspan(-0.5, len(train) - 0.5, color="#f2f2f2", zorder=0)
    ax.plot(range(len(nat)), nat["pct_change"].values * 100, lw=2, color=INK)
    top = nat["pct_change"].max() * 100
    ax.text(len(train) / 2, top, "trained here", color=MID, ha="center", va="bottom")
    ax.text(len(train) + (len(nat) - len(train)) / 2, top, "tested here",
            color=MID, ha="center", va="bottom")
    ax.set_ylim(top=top * 1.3)
    step = 4
    ax.set_xticks(range(0, len(nat), step))
    ax.set_xticklabels(nat.label[::step], rotation=45, ha="right")
    ax.set_ylabel("median change across regions (%)")
    ax.set_xlim(-0.5, len(nat) - 0.5)
    fig.savefig(os.path.join(out, "fig4_shift.pdf")); plt.close(fig)


def main(panel_path, out, split_year, trees, seed):
    os.makedirs(out, exist_ok=True)
    raw, full = prepare(panel_path, split_year)
    feats = FEATURES + LAG_FEATURES
    test = fit(full, feats, split_year, trees, seed)
    risks = [fit(full, feats, split_year, trees, s).risk.values for s in range(10)]

    fig_budget(risks, test, out)
    fig_noise(raw, out)
    fig_coverage(full, feats, out)
    fig_shift(raw, split_year, out)
    print("wrote " + ", ".join(sorted(os.listdir(out))))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--out", default="figures")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.out, a.split_year, a.trees, a.seed)
