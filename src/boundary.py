"""
Which state each region actually sits in.

The panel was cut out with a bounding box, and a box around New South Wales
also contains the top of Victoria, the bottom of Queensland and a strip of
South Australia. That was tolerable while the output was a metric and
embarrassing as soon as the output was a ranking: the highest-risk region in
the first inspection list was near Melbourne.

Point-in-polygon against the published state boundaries fixes it. The test is
ray casting written out here rather than a geopandas dependency, because one
containment test over a few hundred centroids does not justify the install,
and the file stays readable to anyone checking the method.

A tile's centroid can fall in the sea while the tile itself covers coast, so a
point matching no state is assigned to the nearest one within 30 km rather than
discarded; dropping them would quietly delete coastal Sydney.

The Australian Capital Territory is treated as outside New South Wales. It sits
inside it geographically but is a separate jurisdiction with its own network
operators and its own maintenance budget, so a ranking that mixed them would be
handing one organisation another's work.

Usage:
    python src/boundary.py --panel data/panel.csv
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

BOUNDARIES = "data/au_states.geojson"
NAME_KEYS = ("STATE_NAME", "name", "NAME")


def _rings(geometry):
    """Every ring in a Polygon or MultiPolygon, flagged exterior or hole."""
    polys = ([geometry["coordinates"]] if geometry["type"] == "Polygon"
             else geometry["coordinates"])
    for poly in polys:
        for i, ring in enumerate(poly):
            yield np.asarray(ring, dtype=float), i == 0


def _inside(lon, lat, ring):
    """Ray casting: count crossings of the ring by a ray heading east."""
    x1, y1 = ring[:-1, 0], ring[:-1, 1]
    x2, y2 = ring[1:, 0], ring[1:, 1]
    # edges the horizontal line through lat passes between
    straddles = (y1 > lat[:, None]) != (y2 > lat[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        cross_x = x1 + (lat[:, None] - y1) * (x2 - x1) / (y2 - y1)
    return ((straddles & (lon[:, None] < cross_x)).sum(axis=1) % 2).astype(bool)


OFFSHORE_DEG = 0.3        # about 30 km; a coastal tile's centroid can be at sea


def state_of(lon, lat, path=BOUNDARIES, offshore=OFFSHORE_DEG):
    """Name the state containing each point, or the nearest coast it belongs to."""
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    out = np.array([None] * len(lon), dtype=object)
    features = json.load(open(path))["features"]
    named = []
    for feature in features:
        props = feature["properties"]
        name = next((props[k] for k in NAME_KEYS if k in props), None)
        here = np.zeros(len(lon), dtype=bool)
        for ring, exterior in _rings(feature["geometry"]):
            hit = _inside(lon, lat, ring)
            here = (here | hit) if exterior else (here & ~hit)
        out[here & (out == None)] = name          # noqa: E711 - object array
        named.append((name, feature["geometry"]))

    sea = np.array([v is None for v in out])
    if sea.any():
        best = np.full(sea.sum(), np.inf)
        who = np.array([None] * sea.sum(), dtype=object)
        for name, geometry in named:
            near = np.full(sea.sum(), np.inf)
            for ring, _ in _rings(geometry):
                d = np.hypot(lon[sea, None] - ring[None, :, 0],
                             lat[sea, None] - ring[None, :, 1]).min(axis=1)
                near = np.minimum(near, d)
            closer = near < best
            best, who = np.where(closer, near, best), np.where(closer, name, who)
        who[best > offshore] = None
        out[sea] = who
    return out


def label_states(df, path=BOUNDARIES):
    one = df.drop_duplicates("region")[["region", "lon", "lat"]]
    one = one.assign(state=state_of(one.lon.values, one.lat.values, path))
    return df.merge(one[["region", "state"]], on="region", how="left")


def main(panel_path, boundaries, keep, out):
    df = label_states(pd.read_csv(panel_path), boundaries)
    per_region = df.drop_duplicates("region")

    print("regions by state\n")
    counts = per_region.state.fillna("no state within 30 km").value_counts()
    quarters = df.state.fillna("no state within 30 km").value_counts()
    print(pd.DataFrame({"regions": counts, "region-quarters": quarters}).to_string())

    inside = per_region.state == keep
    print(f"\n{inside.sum()} of {len(per_region)} regions are in {keep}; "
          f"{(~inside).sum()} are not and should be dropped")
    stray = per_region[~inside].sort_values("lat")
    if len(stray):
        print("\nthe ones being dropped, southern-most first\n")
        print(stray[["region", "lon", "lat", "state"]].head(8).to_string(index=False))

    if out:
        kept = df[df.state == keep].drop(columns=["state"])
        kept.to_csv(out, index=False)
        print(f"\nwrote {out}: {len(kept):,} region-quarters, "
              f"{kept.region.nunique()} regions")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel.csv")
    p.add_argument("--boundaries", default=BOUNDARIES)
    p.add_argument("--keep", default="New South Wales")
    p.add_argument("--out", default="data/panel_nsw.csv")
    a = p.parse_args()
    main(a.panel, a.boundaries, a.keep, a.out)
