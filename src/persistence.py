"""
What happens after a region falls, which decides whether to send anyone.

Everything else here predicts who will fall. Nobody had asked what happens
next, and the answer changes the operational advice more than any model
comparison does.

Three results, all of them from following every 20% fall forward:

  Most falls undo themselves. 68% of them are back above the line within two
  quarters. Dispatching on a single bad quarter would waste two visits in
  three, which is the measured justification for the persistence rule that was
  until now only argued for.

  The ones that survive two quarters are permanent. The share still down runs
  32%, 30%, 34%, 29%, 30% at two through six quarters out: flat. The two
  quarter test is close to a perfect sieve, and waiting longer than that buys
  nothing.

  A fifth of the affected regions produce two fifths of the events. 23 regions
  fell three or more times, one of them five times, and they account for 38% of
  all falls. Sending a crew to the same place five times is the wrong response
  to a region that needs upgrading rather than inspecting.

Usage:
    python src/persistence.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from model import add_area_type, add_history, add_lags, add_target
from shrink import shrink_speed, shrinkage_constant

DROP = -0.20
HORIZON = 6
CHRONIC = 3          # falls before a region is a standing problem, not an event


def find_falls(df, drop=DROP):
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    ahead, gap = g.smoothed_mbps.shift(-1), g.t.shift(-1) - df.t
    df["next_change"] = (ahead / df.smoothed_mbps - 1).where(gap == 1)
    return df, df[df.next_change <= drop].copy()


def follow(df, falls, horizon=HORIZON, drop=DROP):
    """For each fall, is the region still down k quarters after it started?"""
    level = df.set_index(["region", "t"]).smoothed_mbps
    rows = []
    for k in range(1, horizon + 1):
        key = pd.MultiIndex.from_arrays([falls.region, falls.t + k])
        later = level.reindex(key).values
        observed = ~np.isnan(later)
        down = (later / falls.smoothed_mbps.values - 1) <= drop
        rows.append({"quarters later": k,
                     "still observed": int(observed.sum()),
                     "still down": int((down & observed).sum()),
                     "share": (down & observed).sum() / max(1, observed.sum())})
    return pd.DataFrame(rows)


def main(panel_path, split_year, horizon):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df, falls = find_falls(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    print(f"{len(falls)} quarters where speed fell at least {abs(DROP):.0%}, "
          f"across {falls.region.nunique()} regions\n")

    table = follow(df, falls, horizon)
    print(table.to_string(index=False,
                          formatters={"share": lambda v: f"{v:.0%}"}))

    two = table.iloc[1]
    print(f"\n{1 - two['share']:.0%} of falls undo themselves within two quarters.")
    print("After that the share still down stops changing, so a fall that "
          "survives two\nquarters is permanent as far as this data reaches.")

    per = falls.groupby("region").size()
    chronic = per[per >= CHRONIC]
    print(f"\nrepeat offenders")
    print(f"  fell once               {int((per == 1).sum()):>4}")
    print(f"  fell twice              {int((per == 2).sum()):>4}")
    print(f"  fell {CHRONIC} times or more  {len(chronic):>4}   most often: {int(per.max())}")
    print(f"\nThose {len(chronic)} regions produce {int(chronic.sum())} of "
          f"{len(falls)} falls ({chronic.sum() / len(falls):.0%}). They are a "
          f"standing problem\nrather than an event, and repeat inspection is "
          f"the wrong response to them.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--horizon", type=int, default=HORIZON)
    a = p.parse_args()
    main(a.panel, a.split_year, a.horizon)
