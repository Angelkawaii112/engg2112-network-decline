"""
How much of each region burned in the 2019-20 fire season.

The NSW Fire Extent and Severity Mapping (FESM) 2019-20 raster is queried
through its public map service rather than downloaded: nine points on a 3x3
grid across each ~8 km region, each returning the severity class at that
pixel. The share of points inside any burnt class is the region's exposure.

Nine points is coarse - a region a third burned can read anywhere from 2/9 to
4/9 - but the analysis only needs to separate regions the fires went through
from regions they did not, and the threshold used downstream is deliberately
blunt for that reason.

Source: NSW DPE / NSW RFS, FESM v3, 2019-20, CC BY 3.0 AU.
https://data.gov.au/data/dataset/nsw-fire-extent-and-severity-mapping-fesm-2019-20
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SERVICE = ("https://mapprod3.environment.nsw.gov.au/arcgis/rest/services/Fire/"
           "FESM_2016_2021/MapServer/identify")
LAYER = 4                       # 2019-20 FESM severity classes
DLON, DLAT = 0.03, 0.025        # grid offsets inside a zoom-12 tile
UNBURNT = {"", "Unburnt", "Unburnt or unknown", "No data"}


def is_burnt(label):
    """Unburnt pixels come back labelled with a single space, not an empty string."""
    return label is not None and label.strip() not in UNBURNT


def query(lon, lat, tries=4):
    url = (f"{SERVICE}?geometry={lon},{lat}&geometryType=esriGeometryPoint"
           f"&sr=4326&layers=all:{LAYER}&tolerance=1&mapExtent=140,-38,154,-28"
           f"&imageDisplay=1000,800,96&returnGeometry=false&f=json")
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                res = json.load(r).get("results", [])
            return res[0]["attributes"].get("LABEL", "") if res else ""
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None                 # unreachable after retries; kept as missing


def region_points(lon, lat):
    return [(lon + i * DLON, lat + j * DLAT) for i in (-1, 0, 1) for j in (-1, 0, 1)]


def main():
    panel = pd.read_csv(ROOT / "data/panel_nsw.csv")
    regions = panel.drop_duplicates("region")[["region", "lon", "lat"]]
    jobs = [(r.region, p) for r in regions.itertuples()
            for p in region_points(r.lon, r.lat)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        labels = list(ex.map(lambda j: query(*j[1]), jobs))
    rows = pd.DataFrame({"region": [j[0] for j in jobs],
                         "lon": [j[1][0] for j in jobs], "lat": [j[1][1] for j in jobs],
                         "label": labels})
    rows.to_csv(HERE / "data/fire_points.csv", index=False)
    out = rows.groupby("region").agg(
        points=("label", "size"),
        answered=("label", lambda s: s.notna().sum()),
        burnt=("label", lambda s: s.map(is_burnt).sum()),
        worst=("label", lambda s: ", ".join(sorted({x for x in s if is_burnt(x)}))))
    out["burnt_share"] = out.burnt / out.answered.where(out.answered > 0)
    out.reset_index().to_csv(HERE / "data/region_fire.csv", index=False)
    print(f"{len(out)} regions, {int(out.answered.sum())} of {int(out.points.sum())} "
          f"points answered, {int((out.burnt_share > 0).sum())} regions with any burn")
    print(rows.label.map(lambda x: repr(x)).value_counts().to_string())


if __name__ == "__main__":
    main()
