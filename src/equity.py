"""
Does the system's unfairness follow income, or only geography?

The coverage analysis showed regional New South Wales is dropped before the
model runs. The obvious next worry is that this is the same thing as dropping
poor areas, and Lee et al. found crowdsourced speed-test samples skewed by
income, education and age, so the worry is not idle. ABS publishes the Index
of Relative Socio-economic Disadvantage (IRSD) for every SA2; joining it asks
the question directly.

Regions are matched to SA2s by the rule the population experiment used: the
region centre must fall in exactly one SA2, with no nearest-area substitution.
Boundaries come from the ABS ASGS 2021 map service, SEIFA from the ABS 2021
release; both are fetched if absent.

The answer is no, on every measure. Lasting declines are not concentrated in
disadvantaged areas - if anything the least disadvantaged quintile has the
highest rate. A 15% inspection budget reaches the most disadvantaged quintile
slightly more than its share of rows. And the regional band that the model
drops has a median IRSD decile of 5, the middle of the distribution.

One apparent pattern had to be taken apart before it could be reported. The
panel seems to reach the most advantaged SA2s least often, 22% against 38% for
the most disadvantaged, which would be the reverse of the published bias. It is
geometry. Inner-city SA2s are small, and an 8 km tile centre lands in one SA2
at a time, so small SA2s are rarely reached whatever their income; within any
band of SA2 size, advantaged and disadvantaged SA2s are reached about equally.

So the system's equity problem is geographic, not socio-economic: it fails
people in low-usage rural areas, and does not on this evidence fail people for
being poor. IRSD describes residents, not the commuters and visitors who also
run tests, and 47 of 455 regions match no SA2 at all, so this is evidence about
the regions the model sees rather than about the state.

Usage:
    python src/equity.py --panel data/panel_nsw.csv
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from boundary import _inside, _rings
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from rankers import MeanReversion
from shrink import add_persistent, purge, shrink_speed, shrinkage_constant

SA2_FILE = "data/nsw_sa2_2021.geojson"
SEIFA_FILE = "data/seifa_sa2_2021.xlsx"
SA2_SERVICE = ("https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SA2/"
               "MapServer/0/query")
SEIFA_URL = ("https://www.abs.gov.au/statistics/people/people-and-communities/"
             "socio-economic-indexes-areas-seifa-australia/2021/"
             "Statistical%20Area%20Level%202%2C%20Indexes%2C%20SEIFA%202021.xlsx")
QUINTILES = ["1 most disadvantaged", "2", "3", "4", "5 least disadvantaged"]
BUDGET = 0.15


def fetch_sa2(path=SA2_FILE):
    if os.path.exists(path):
        return
    features = []
    for offset in (0, 500):
        url = (f"{SA2_SERVICE}?where=state_code_2021%3D%271%27"
               f"&outFields=sa2_code_2021,sa2_name_2021&returnGeometry=true"
               f"&maxAllowableOffset=0.002&outSR=4326&resultOffset={offset}"
               f"&resultRecordCount=500&f=geojson")
        with urllib.request.urlopen(url, timeout=120) as r:
            features += json.load(r).get("features", [])
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f,
                  separators=(",", ":"))


def fetch_seifa(path=SEIFA_FILE):
    if not os.path.exists(path):
        urllib.request.urlretrieve(SEIFA_URL, path)


def match_sa2(points, path=SA2_FILE):
    """Each region centre to the single SA2 containing it, or none."""
    lon, lat = points.lon.values, points.lat.values
    hits = [[] for _ in range(len(points))]
    for f in json.load(open(path))["features"]:
        if not f.get("geometry"):               # "no usual address" and the like
            continue
        inside = np.zeros(len(points), bool)
        for ring, exterior in _rings(f["geometry"]):
            hit = _inside(lon, lat, ring)
            inside = (inside | hit) if exterior else (inside & ~hit)
        for i in np.where(inside)[0]:
            hits[i].append(f["properties"]["sa2_code_2021"])
    return points.assign(sa2=[h[0] if len(h) == 1 else None for h in hits])


def load_irsd(path=SEIFA_FILE):
    t = pd.read_excel(path, "Table 2", header=None, skiprows=6).iloc[:, [0, 2, 6]]
    t.columns = ["sa2", "population", "decile"]
    t = t[pd.to_numeric(t.sa2, errors="coerce").notna()].copy()
    t["sa2"] = t.sa2.astype(int).astype(str)
    t["decile"] = pd.to_numeric(t.decile, errors="coerce")
    t["quintile"] = pd.cut(t.decile, [0, 2, 4, 6, 8, 10], labels=QUINTILES)
    return t


def sa2_area_km2(path=SA2_FILE):
    rows = []
    for f in json.load(open(path))["features"]:
        if not f.get("geometry"):
            continue
        total = 0.0
        for ring, exterior in _rings(f["geometry"]):
            x, y = ring[:, 0], ring[:, 1]
            a = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
            a *= 111.32 ** 2 * np.cos(np.radians(y.mean()))
            total += a if exterior else -a
        rows.append({"sa2": f["properties"]["sa2_code_2021"], "km2": total})
    return pd.DataFrame(rows)


def main(panel_path, split_year):
    fetch_sa2()
    fetch_seifa()
    raw = pd.read_csv(panel_path)
    points = raw.drop_duplicates("region")[["region", "lon", "lat"]]
    mapping = match_sa2(points)
    irsd = load_irsd()
    mapping = mapping.merge(irsd[["sa2", "quintile", "decile"]], on="sa2", how="left")
    print(f"{mapping.quintile.notna().sum()} of {len(mapping)} regions matched "
          f"to an SA2 with an IRSD score\n")

    raw = add_area_type(add_lags(add_history(add_target(raw))))
    df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, split_year)))
    df = df.merge(mapping[["region", "quintile", "decile"]], on="region", how="left")
    feats = FEATURES + LAG_FEATURES
    kept = df.dropna(subset=feats + ["fwd_1", "fwd_2"])

    print("Do lasting declines concentrate in disadvantaged areas?")
    t = kept.groupby("quintile", observed=False).persistent.agg(["sum", "size"])
    t["rate"] = (t["sum"] / t["size"] * 100).round(1)
    print(t.rename(columns={"sum": "declines", "size": "rows", "rate": "rate %"}).to_string())

    train, test = kept[kept.year < split_year], kept[kept.year >= split_year].copy()
    train = purge(train, test.t.min())
    test["score"] = MeanReversion().fit(train).score(test)
    k = int(round(BUDGET * len(test)))
    test["inspect"] = test.score.rank(ascending=False, method="first") <= k
    print(f"\nDoes a {BUDGET:.0%} budget reach them in proportion? (test years)")
    b = test.groupby("quintile", observed=False).agg(rows=("inspect", "size"),
                                                     inspected=("inspect", "sum"))
    b["share of rows %"] = (b.rows / b.rows.sum() * 100).round(0)
    b["share of budget %"] = (b.inspected / b.inspected.sum() * 100).round(0)
    print(b.to_string())

    bands = df.drop_duplicates("region").groupby("area_type", observed=False).decile
    print("\nIs the dropped regional band a poor band? (median IRSD decile, 1 = most disadvantaged)")
    print(bands.median().to_string())

    sizes = sa2_area_km2().merge(irsd, on="sa2")
    sizes["reached"] = sizes.sa2.isin(set(mapping.sa2.dropna()))
    sizes["size"] = pd.qcut(sizes.km2, 5, labels=["smallest", "small", "mid",
                                                  "large", "largest"])
    sizes["half"] = np.where(sizes.decile <= 5, "disadvantaged", "advantaged")
    print("\nThe panel seems to miss advantaged SA2s. Within a size band, does it?")
    print(sizes.pivot_table(index="size", columns="half", values="reached",
                            aggfunc="mean", observed=False).round(2).to_string())
    print("\nReach follows SA2 size, not income. The bias is geographic, not socio-economic.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    a = p.parse_args()
    main(a.panel, a.split_year)
