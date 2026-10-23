"""
Likelihood is half of risk. Where would a decline matter most?

Everything in O1 ranks regions by how likely a lasting decline is. An engineer
ranks by risk, which is likelihood times consequence, and a decline beside a
stretch of road where people are hurt every month is worth more attention than
the same decline in an empty paddock. Road crashes are a measurable stand-in
for one consequence that matters: someone needing to call for help.

Consequence here is crash exposure, from Transport for NSW's open crash data,
2021-2025: every crash with coordinates, placed exactly into its ~8 km region
because region ids are zoom-12 quadkeys. Three versions are built:

  casualty    fatal and injury crashes per year
  severity    the same with each fatal crash counted ten times
  rural fast  casualty crashes outside urban areas on roads of 80 km/h or more,
              where a phone is often the only way to call for help

Likelihood comes from the deployed rule, turned into a probability by fitting
a logistic curve to it on training rows only, so the order of regions by
likelihood is exactly the rule's order. Risk is

    risk = P(lasting decline) x (1 + crashes) ^ alpha

alpha = 0 is the existing likelihood-only ranking; alpha = 1 weights fully by
crashes. The +1 keeps a region with no recorded crashes rankable on likelihood.

The test is what each alpha catches inside a 15% budget, under the same purged
rolling origin as everything else: how many lasting declines, and how much of
the crash exposure behind them. A risk ranking should give up a little of the
first to gain a lot of the second; how much is the result.

Crashes do not cause declines and are not predicted. This weights where to
look; it does not change what is found. The crash years overlap the scored
quarters, which is acceptable for a measure of where roads are dangerous - a
geography that barely moves in five years - and is stated rather than hidden.

Source: Transport for NSW, NSW Road Crash Data 2021-2025, CC BY 3.0 AU.
https://opendata.transport.nsw.gov.au/dataset/nsw-crash-data

Usage:
    python src/impact.py --panel data/panel_nsw.csv
"""
import argparse
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from compare import recall_at_budget
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from quadkey import lonlat_to_tile, tile_to_quadkey
from shrink import add_persistent, purge, shrink_speed, shrinkage_constant

CRASH_FILE = "data/crashes_2021_2025.xlsx"
CRASH_URL = ("https://opendata.transport.nsw.gov.au/data/dataset/"
             "06f9cf3d-0a9d-4098-b0f0-fa9efbdd3921/resource/"
             "5accfb16-ef51-4b07-b2de-e46761fac721/download/"
             "nsw_road_crash_data_2021-2025_crash.xlsx")
ZOOM = 12
YEARS = 5
ALPHAS = (0.0, 0.25, 0.5, 1.0)
BUDGET = 0.15
MIN_TRAIN, MIN_POSITIVES = 400, 2
FAST_KMH = 80


def fetch_crashes(path=CRASH_FILE):
    if not os.path.exists(path):
        urllib.request.urlretrieve(CRASH_URL, path)


def region_impact(path=CRASH_FILE):
    """Crash exposure per region, per year, three ways."""
    cols = ["Degree of crash", "Latitude", "Longitude", "Urbanisation", "Speed limit"]
    c = pd.read_excel(path, usecols=cols).dropna(subset=["Latitude", "Longitude"])
    c["region"] = [int(tile_to_quadkey(*lonlat_to_tile(lo, la, ZOOM), ZOOM))
                   for lo, la in zip(c.Longitude, c.Latitude)]
    casualty = c["Degree of crash"].isin(["Fatal", "Injury"])
    fatal = c["Degree of crash"].eq("Fatal")
    kmh = pd.to_numeric(c["Speed limit"].astype(str).str.extract(r"(\d+)")[0],
                        errors="coerce")
    rural = c.Urbanisation.astype(str).str.startswith("Country non-urban")
    c["casualty"] = casualty.astype(int)
    c["severity"] = casualty.astype(int) + 9 * fatal.astype(int)
    c["rural_fast"] = (casualty & rural & (kmh >= FAST_KMH)).astype(int)
    c["fatal"] = fatal.astype(int)
    out = c.groupby("region")[["casualty", "severity", "rural_fast", "fatal"]].sum() / YEARS
    out["crashes_total"] = c.groupby("region").size()
    return out


def calibrated(train, test):
    """The rule's score as a probability, fitted on training rows only."""
    m = LogisticRegression().fit(train[["speed_vs_own_mean"]], train.persistent.astype(int))
    return m.predict_proba(test[["speed_vs_own_mean"]])[:, 1]


def top_k(score, budget):
    k = max(1, int(round(budget * len(score))))
    return np.argsort(-score)[:k]


def evaluate(df, impact, measure, start_year):
    feats = FEATURES + LAG_FEATURES
    d = df.dropna(subset=feats).copy()
    d["exposure"] = d.region.map(impact[measure]).fillna(0.0)
    d["has_fatal"] = d.region.map(impact["fatal"]).fillna(0) > 0
    ok = d.fwd_1.notna() & d.fwd_2.notna()
    rows = []
    for t in sorted(d[d.year >= start_year].t.unique()):
        now = d[(d.t == t) & ok]
        known = purge(d[(d.t < t) & ok], t)
        y = now.persistent.astype(int).values
        if y.sum() < MIN_POSITIVES or len(known) < MIN_TRAIN:
            continue
        p = calibrated(known, now)
        w = now.exposure.values
        for a in ALPHAS:
            score = p * (1 + w) ** a
            top = top_k(score, BUDGET)
            caught = np.zeros(len(y), bool)
            caught[top] = True
            harm = (w * y).sum()
            rows.append({
                "alpha": a, "t": t,
                "declines": int(y.sum()),
                "caught": int((caught & (y == 1)).sum()),
                "harm_total": harm,
                "harm_caught": (w * y * caught).sum(),
                "fatal_regions_inspected": int((caught & now.has_fatal.values).sum()),
                "inspected": len(top),
            })
    r = pd.DataFrame(rows)
    g = r.groupby("alpha").agg(quarters=("t", "nunique"), declines=("declines", "sum"),
                               caught=("caught", "sum"), harm_total=("harm_total", "sum"),
                               harm_caught=("harm_caught", "sum"),
                               fatal_regions=("fatal_regions_inspected", "sum"),
                               inspected=("inspected", "sum"))
    g["recall"] = g.caught / g.declines
    g["harm-weighted recall"] = g.harm_caught / g.harm_total
    g["inspections at a fatal-crash region"] = g.fatal_regions / g.inspected
    return g


def main(panel_path, start_year):
    fetch_crashes()
    impact = region_impact()
    raw = pd.read_csv(panel_path)
    regions = set(raw.region.unique())
    covered = impact[impact.index.isin(regions)]
    print(f"{int(impact.crashes_total.sum()):,} crashes placed in "
          f"{len(impact):,} regions; {len(covered)} of {len(regions)} panel regions "
          f"have at least one, holding {int(covered.crashes_total.sum()):,} crashes\n")

    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, start_year)))

    for measure in ("casualty", "severity", "rural_fast"):
        g = evaluate(df, impact, measure, start_year)
        print(f"consequence = {measure}, purged rolling origin, "
              f"{int(g.quarters.iloc[0])} quarters, {int(g.declines.iloc[0])} lasting declines")
        show = g[["recall", "harm-weighted recall", "inspections at a fatal-crash region"]]
        show.index = [f"alpha {a:g}" + (" (likelihood only)" if a == 0 else "") for a in show.index]
        print(show.round(3).to_string(), "\n")

    print("alpha 0 ranks by likelihood alone. Higher alpha gives up some declines "
          "found\nto catch more of the ones beside dangerous roads.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--start-year", type=int, default=2021)
    a = p.parse_args()
    main(a.panel, a.start_year)
