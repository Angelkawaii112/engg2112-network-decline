"""
Do the declines sit next to each other, or scatter?

If a lasting decline is a real fault it should sometimes be a shared one.
Cells lean on the same backhaul, the same power, the same upgrade programme,
and a region whose neighbours are falling at the same time is a different
proposition from one falling alone. If instead the events scatter across the
state with no regard for each other, that is what independent measurement noise
looks like, and the case for a maintenance ranking weakens.

The test is a permutation. Within each quarter, take the regions that declined
and measure how far each sits from the nearest other decline in that same
quarter. Then shuffle which regions declined, keeping the count per quarter
fixed, and measure again. Shuffling preserves everything about the geography
and the number of events, and destroys only the association between a region
and its outcome, so the gap between the real statistic and the shuffled
distribution is the clustering that the geography alone does not explain.

Distances are great-circle kilometres between region centroids.

Usage:
    python src/clustering.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from model import add_area_type, add_history, add_lags, add_target
from shrink import add_persistent, shrink_speed, shrinkage_constant

EARTH_KM = 6371.0


def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


def nearest_other(lon, lat, picked):
    """Mean distance from each picked region to the nearest other picked one."""
    if picked.sum() < 2:
        return np.nan
    x, y = lon[picked], lat[picked]
    d = haversine(x[:, None], y[:, None], x[None, :], y[None, :])
    np.fill_diagonal(d, np.inf)
    return d.min(axis=1).mean()


def statistic(groups):
    """Average, over quarters, of the mean nearest-decline distance."""
    vals = [nearest_other(lon, lat, picked) for lon, lat, picked in groups]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else np.nan


def main(panel_path, split_year, shuffles, seed):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    df = df[df.fwd_1.notna() & df.fwd_2.notna()]

    groups, counts = [], []
    for t, q in df.groupby("t"):
        if q.persistent.sum() < 2:
            continue
        groups.append((q.lon.values, q.lat.values, q.persistent.values))
        counts.append((int(q.persistent.sum()), len(q)))

    if not groups:
        print("no quarter holds two declines"); return
    observed = statistic(groups)
    events = sum(c for c, _ in counts)
    print(f"{len(groups)} quarters with at least two declines, {events} declines\n")

    rng = np.random.default_rng(seed)
    null = np.empty(shuffles)
    for i in range(shuffles):
        shuffled = []
        for lon, lat, picked in groups:
            fake = np.zeros(len(picked), bool)
            fake[rng.choice(len(picked), picked.sum(), replace=False)] = True
            shuffled.append((lon, lat, fake))
        null[i] = statistic(shuffled)

    p = (null <= observed).mean()
    print(f"mean distance to the nearest other decline in the same quarter")
    print(f"  observed              {observed:8.1f} km")
    print(f"  shuffled, mean        {null.mean():8.1f} km")
    print(f"  shuffled, 5th pct     {np.percentile(null, 5):8.1f} km")
    print(f"  closer than observed  {p:8.3f}  ({shuffles} shuffles)")

    verdict = ("closer together than chance" if p < 0.05 else
               "no closer together than chance")
    print(f"\nDeclines are {verdict}.")
    if p >= 0.05:
        print("Each one has to be justified on its own evidence; a neighbour\n"
              "falling at the same time is not, on this data, a reason to\n"
              "believe a region more.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--shuffles", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.split_year, a.shuffles, a.seed)
