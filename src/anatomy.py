"""
What the declines actually are, which nobody had asked.

The project spent its effort on predicting these events and none on checking
whether they are worth predicting. A fall in a crowdsourced download median
could be a degraded cell, or it could be the same cell measured by different
people on different plans with different handsets. Those call for completely
different responses, and only one of them justifies sending a crew.

Ookla reports upload and latency alongside download, and they discriminate
between the two stories. A cell in trouble degrades the whole link: upload
falls with download and latency rises. A change in who is testing moves
download without moving the rest.

The answer is clear and it is the good one. Upload falls alongside download in
86% of these events against 31% of everything else, and the download and upload
medians fall by almost the same proportion, 38% and 35%. Whatever these are,
they are not an artefact of which handsets showed up.

Congestion is not the mechanism, which is worth stating because it is the
intuitive one. Device counts grow in 30% of declines and in 30% of everything
else: identical. If anything users leave rather than arrive.

One result argues against the project. In a quarter of these events the number
of speed tests halves, against 4% of other region-quarters. That is either the
consequence of a bad cell or part of its cause, and this data cannot separate
them. Shrinking by test count limits the damage without ending the argument.

Usage:
    python src/anatomy.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from model import add_area_type, add_history, add_lags, add_target
from shrink import add_persistent, shrink_speed, shrinkage_constant

MOVED = [("down_mbps", "download speed"), ("up_mbps", "upload speed"),
         ("lat_ms", "latency, up is worse"), ("tests", "speed tests run"),
         ("devices", "devices seen")]


def add_next_quarter_changes(df):
    df = df.sort_values(["region", "t"]).copy()
    g = df.groupby("region")
    for col, _ in MOVED:
        ahead, gap = g[col].shift(-1), g.t.shift(-1) - df.t
        df[f"d_{col}"] = (ahead / df[col] - 1).where(gap == 1)
    return df


def signatures(frame):
    """Did this move the way a failing link would, or the way a changed sample would?"""
    return {
        "upload fell as well": frame.d_up_mbps <= -0.10,
        "latency got worse": frame.d_lat_ms >= 0.10,
        "both, a whole-link fault": (frame.d_up_mbps <= -0.10) & (frame.d_lat_ms >= 0.10),
        "devices grew, congestion": frame.d_devices >= 0.10,
        "devices fell, users left": frame.d_devices <= -0.10,
        "testing halved": frame.d_tests <= -0.50,
    }


def main(panel_path, split_year):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_next_quarter_changes(
        add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year))))

    comparable = df.d_down_mbps.notna() & df.fwd_1.notna()
    hit, rest = df[df.persistent & comparable], df[~df.persistent & comparable]
    print(f"{len(hit)} lasting declines, {len(rest)} other region-quarters\n")

    print(f"{'median change next quarter':<30}{'declines':>10}{'others':>10}")
    for col, name in MOVED:
        print(f"  {name:<28}{hit[f'd_{col}'].median():>+10.3f}"
              f"{rest[f'd_{col}'].median():>+10.3f}")

    print(f"\n{'how often it looked like':<30}{'declines':>10}{'others':>10}")
    a, b = signatures(hit), signatures(rest)
    for name in a:
        print(f"  {name:<28}{a[name].mean():>9.0%}{b[name].mean():>10.0%}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    a = p.parse_args()
    main(a.panel, a.split_year)
