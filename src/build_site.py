"""
Write the data file the published site reads.

export_ui.py produces one quarter's ranking. This adds the three longer
horizons, the per-region history the detail chart draws, and the state outline
the map needs, in the single JSON the page fetches on load.

Keeping the numbers in a file rather than inside the HTML is what makes the
site a consumer of the pipeline rather than a copy of it: a new quarter means
rerunning this and committing docs/data.json, and the page is untouched.

Usage:
    python src/build_site.py --panel data/panel_nsw.csv --out docs
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from boundary import BOUNDARIES
from horizon import label_at
from impact import fetch_crashes, region_impact
from model import (FEATURES, LAG_FEATURES, add_area_type, add_history,
                   add_lags, add_target)
from persistence import CHRONIC, find_falls
from rankers import MeanReversion
from shrink import add_persistent, purge, shrink_speed, shrinkage_constant

LEADS = (1, 2, 3, 4)
GRID = np.round(np.arange(0, 0.51, 0.01), 2)
TOL = 0.06          # outline simplification, degrees


def outline(path=BOUNDARIES, state="New South Wales", tol=TOL):
    feats = json.load(open(path))["features"]
    geom = next(f for f in feats
                if f["properties"].get("STATE_NAME") == state)["geometry"]
    ring = max((poly[0] for poly in geom["coordinates"]), key=len)
    out = [ring[0]]
    for p in ring[1:]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > tol:
            out.append(p)
    out.append(ring[0])
    return [[round(x, 3), round(y, 3)] for x, y in out]


def dense_window(points, pad=0.08):
    """The box around the crowded half of the regions, which is Sydney.

    Hard-coding a box around Sydney worked until the panel changed under it.
    Taking the regions whose nearest neighbour is closer than the median and
    bounding those finds the same place without being told where it is.
    """
    xy = np.asarray(points, float)
    d = np.hypot(xy[:, 0, None] - xy[None, :, 0], xy[:, 1, None] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1)
    tight = xy[nn <= np.median(nn)]
    lo, hi = tight.min(axis=0) - pad, tight.max(axis=0) + pad
    return [round(lo[0], 3), round(lo[1], 3), round(hi[0], 3), round(hi[1], 3)]


def recall_curve(y, score):
    if y.sum() == 0:
        return [0.0] * len(GRID)
    order = np.argsort(score)
    cum = np.cumsum(y[order]) / y.sum()
    return [round(float(cum[max(0, int(round(b * len(y))) - 1)]), 3) for b in GRID]


def main(panel_path, split_year, out_dir, trees, seed):
    raw = pd.read_csv(panel_path)
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    base = shrink_speed(raw, shrinkage_constant(raw, split_year))
    feats = FEATURES + LAG_FEATURES

    _, falls = find_falls(base)
    per = falls.groupby("region").size()

    leads = {}
    for lead in LEADS:
        df, cols = label_at(base, lead)
        df = df.dropna(subset=feats)
        train = df.dropna(subset=cols)
        split_t = train[train.year >= split_year].t.min()
        train = pd.concat([purge(train[train.year < split_year], split_t, lead + 1),
                           train[train.year >= split_year]])
        simple = MeanReversion().fit(train, target=f"h{lead}")
        forest = RandomForestClassifier(
            n_estimators=trees, class_weight="balanced", min_samples_leaf=5,
            random_state=seed, n_jobs=-1).fit(train[feats], train.y.astype(int))

        now = df[df.t == df.t.max()].copy()
        now["exp"] = simple.predicted_change(now)
        now["risk"] = forest.predict_proba(now[feats])[:, 1]
        now["steep"] = now.risk >= now.risk.quantile(0.75)
        # the rule's score as a probability, fitted on training rows only, so a
        # consequence weight can multiply it; ordering is the rule's own
        calib = LogisticRegression().fit(train[["speed_vs_own_mean"]], train.y.astype(int))
        now["p"] = calib.predict_proba(now[["speed_vs_own_mean"]])[:, 1]
        now = now.sort_values("exp")
        now["rank"] = range(1, len(now) + 1)

        test = train[train.year >= split_year]
        y = test.y.astype(int).values
        leads[lead] = {
            "k": round(simple.k_, 5),
            "events": int(y.sum()),
            "quarters": int(test.t.nunique()),
            "curve": recall_curve(y, simple.predicted_change(test)),
            "regions": [{"rank": int(r["rank"]), "id": str(r.region),
                         "exp": round(r.exp, 4), "risk": round(r.risk, 3),
                         "p": round(r.p, 5),
                         "steep": bool(r.steep)} for _, r in now.iterrows()],
        }
        print(f"  lead {lead}: {len(now)} regions, {int(train.y.sum())} training "
              f"declines, {int(y.sum())} in the test years")

    fetch_crashes()
    road = region_impact()["rural_fast"]
    latest = base[base.t == base.t.max()]
    static = {str(r.region): {
        "lon": round(r.lon, 4), "lat": round(r.lat, 4), "area": r.area_type,
        "mbps": round(r.down_mbps, 1), "sm": round(r.smoothed_mbps, 1),
        "tests": int(r.tests), "falls": int(per.get(r.region, 0)),
        "chronic": bool(per.get(r.region, 0) >= CHRONIC),
        "road": round(float(road.get(int(r.region), 0.0)), 2)}
        for _, r in latest.iterrows() if str(r.region) in
        {x["id"] for x in leads[1]["regions"]}}

    keep = set(static)
    hist = base[base.region.astype(str).isin(keep)].sort_values(["region", "t"])
    history = {str(reg): {
        "q": [f"{int(y)}Q{int(q)}" for y, q in zip(g.year, g.quarter)],
        "raw": [round(v, 1) for v in g.down_mbps],
        "sm": [round(v, 1) for v in g.smoothed_mbps]}
        for reg, g in hist.groupby("region")}

    quarter = f"{int(latest.year.iloc[0])} Q{int(latest.quarter.iloc[0])}"
    window = dense_window([(v["lon"], v["lat"]) for v in static.values()])
    meta = {
        "quarter": quarter,
        "impact_alpha": 0.25,
        "window": window,
        "regions": len(static),
        "coverage": "urban and outer-suburban New South Wales only",
        "honesty": [
            "Ranked by a one-parameter rule; a random forest did no better.",
            "A decline is a 20%+ fall that lasts. Two in three short falls recover.",
            "Urban and outer-suburban NSW only.",
            "Shows which regions, not when. Few events: figures are rough.",
        ],
    }

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "data.json")
    with open(path, "w") as f:
        json.dump({"meta": meta, "static": static, "leads": leads,
                   "history": history, "outline": outline()}, f,
                  separators=(",", ":"))
    print(f"\nwrote {path}  ({os.path.getsize(path) / 1024:.0f} KB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default="data/panel_nsw.csv")
    p.add_argument("--split-year", type=int, default=2024)
    p.add_argument("--out", default="docs")
    p.add_argument("--trees", type=int, default=400)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    main(a.panel, a.split_year, a.out, a.trees, a.seed)
