"""
O2: how did new towers, the 3G switch-off, and bushfires and floods change
measured mobile performance in New South Wales?

Each event is an event study: regions the event touched are compared with
regions it did not, quarter by quarter, relative to the quarter before the
event. A region fixed effect absorbs each region's own level and a quarter
fixed effect absorbs everything that moved the whole state at once - 5G
rollout, seasons, Ookla's own changes - so what is left is how the touched
regions moved differently.

    log(speed)_it = region_i + quarter_t + sum_k beta_k * [t - event_i = k] + e_it

beta_k is the gap, in log points, k quarters after the event (k = -1 is fixed
at zero). Standard errors are clustered by region.

Measured, not shrunk, speeds are used. The model in src/ pulls each quarter
toward a region's own history to remove sampling noise, which is right for
ranking and wrong here: it would pull an event's effect back toward zero.

Choices that decide the answer, and are therefore stated:

  towers   a region is touched if a Mobile Black Spot site completed within
           10 km of its centre between 2020 Q1 and 2025 Q2; controls are
           regions with no completion within 10 km in 2019-2026. 5 km and
           20 km are run as checks.
  fires    touched if at least 3 of 9 sample points burnt in 2019-20 (FESM);
           event quarter 2019 Q4, when the NSW season escalated. Controls are
           unburnt regions outside the Sydney, Newcastle and Wollongong urban
           areas, because comparing burnt rural regions with cities that were
           rolling out 5G would read the 5G gap as fire damage.
  floods   touched if inside one of the seven Northern Rivers LGAs; event
           quarter 2022 Q1. Controls are other regions north of Newcastle.
  3G       there is no untouched region - every network switched off
           statewide - so it is not an event study. See three_g().

Usage:
    python experiments/events/scripts/event_study.py
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from boundary import _inside, _rings              # noqa: E402

warnings.filterwarnings("ignore")
WINDOW = (-4, 6)                  # quarters shown either side; ends are binned
EARTH_KM = 6371.0


def qindex(year, quarter):
    return 4 * int(year) + int(quarter)


def qlabel(t):
    return f"{(t - 1) // 4} Q{(t - 1) % 4 + 1}"


def load_panel():
    p = pd.read_csv(ROOT / "data/panel_nsw.csv")
    p["t"] = [qindex(y, q) for y, q in zip(p.year, p.quarter)]
    p = p[p.down_mbps > 0].copy()
    p["log_speed"] = np.log(p.down_mbps)
    p["log_tests"] = np.log(p.tests)
    p["log_latency"] = np.log(p.lat_ms.clip(lower=1))
    return p


def km(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2 +
         np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


# Greater Sydney, Newcastle and Wollongong, as boxes. Coarse on purpose: the
# point is only to keep big-city regions out of a rural control group.
CITIES = [(150.5, -34.2, 151.4, -33.5), (151.5, -33.0, 151.85, -32.75),
          (150.75, -34.6, 151.0, -34.3)]


def in_city(lon, lat):
    return np.any([(lon >= a) & (lon <= c) & (lat >= b) & (lat <= d)
                   for a, b, c, d in CITIES], axis=0)


def event_study(panel, event_q, treated, controls, outcome="log_speed"):
    """Two-way fixed effects event study. event_q maps region -> event quarter."""
    keep = set(treated) | set(controls)
    d = panel[panel.region.isin(keep)].copy()
    d["k"] = d.t - d.region.map(event_q)                # NaN for controls
    lo, hi = WINDOW
    d["k"] = d.k.clip(lower=lo, upper=hi)
    names = []
    for k in range(lo, hi + 1):
        if k == -1:
            continue
        name = f"k_m{-k}" if k < 0 else f"k_{k}"
        d[name] = (d.k == k).astype(int)
        if d[name].sum() == 0:          # outside the panel's 2019-2026 span
            d = d.drop(columns=name)
            continue
        names.append((k, name))
    formula = f"{outcome} ~ " + " + ".join(n for _, n in names) + " + C(region) + C(t)"
    fit = smf.ols(formula, d).fit(cov_type="cluster",
                                  cov_kwds={"groups": d.region.astype("category").cat.codes})
    rows = []
    for k, n in names:
        rows.append({"k": k, "beta": fit.params[n], "se": fit.bse[n],
                     "lo": fit.conf_int().loc[n, 0], "hi": fit.conf_int().loc[n, 1],
                     "treated_obs": int(d[d[n] == 1].shape[0])})
    rows.append({"k": -1, "beta": 0.0, "se": 0.0, "lo": 0.0, "hi": 0.0,
                 "treated_obs": int((d.k == -1).sum())})
    coefs = pd.DataFrame(rows).sort_values("k").reset_index(drop=True)
    return coefs, d


def summarise(name, coefs, n_treated, n_control):
    pre = coefs[coefs.k.between(-4, -2)]
    short = coefs[coefs.k.between(0, 1)]
    long = coefs[coefs.k.between(2, 6)]
    pct = lambda b: 100 * (np.exp(b) - 1)
    return {
        "event": name, "treated regions": n_treated, "control regions": n_control,
        "pre-trend (k=-4..-2), %": round(pct(pre.beta.mean()), 1),
        "short run (k=0..1), %": round(pct(short.beta.mean()), 1),
        "longer run (k=2..6), %": round(pct(long.beta.mean()), 1),
        "any short-run k significant": bool(((short.lo > 0) | (short.hi < 0)).any()),
    }


# ------------------------------------------------------------------ towers
def towers(panel, radius_km=10):
    raw = json.load(open(HERE / "data/mbsp_nsw.json"))
    s = pd.DataFrame([f["attributes"] for f in raw["features"]])
    s = s[s.Site_Status == "Complete"].copy()
    s["done"] = pd.to_datetime(s.Completion_Date, format="%b, %Y", errors="coerce")
    s = s.dropna(subset=["done", "Longitude", "Latitude"])
    s["t"] = [qindex(d.year, (d.month - 1) // 3 + 1) for d in s.done]

    regions = panel.drop_duplicates("region")[["region", "lon", "lat"]]
    dist = km(regions.lon.values[:, None], regions.lat.values[:, None],
              s.Longitude.values[None, :], s.Latitude.values[None, :])
    near = dist <= radius_km
    t_lo, t_hi = qindex(2020, 1), qindex(2025, 2)
    in_window = (s.t.values >= t_lo) & (s.t.values <= t_hi)
    any_2019_on = s.t.values >= qindex(2019, 1)

    event_q, controls = {}, []
    for i, r in enumerate(regions.region):
        hits = near[i] & in_window
        if hits.any():
            event_q[r] = int(s.t.values[hits].min())
        elif not (near[i] & any_2019_on).any():
            controls.append(r)
    # keep treated regions that have data both before and after their tower
    seen = panel.groupby("region").t.agg(["min", "max"])
    treated = [r for r, q in event_q.items()
               if r in seen.index and seen.loc[r, "min"] < q <= seen.loc[r, "max"]]
    return {r: event_q[r] for r in treated}, controls, len(s)


# ------------------------------------------------------------------- fires
def fires(panel, threshold=3 / 9):
    f = pd.read_csv(HERE / "data/region_fire.csv")
    regions = panel.drop_duplicates("region")[["region", "lon", "lat"]].merge(f, on="region")
    burnt = regions[regions.burnt_share >= threshold].region.tolist()
    rural = ~in_city(regions.lon.values, regions.lat.values)
    controls = regions[(regions.burnt_share == 0) & rural].region.tolist()
    q = qindex(2019, 4)
    return {r: q for r in burnt}, controls


# ------------------------------------------------------------------ floods
def floods(panel):
    feats = json.load(open(HERE / "data/flood_lgas_2022.geojson"))["features"]
    regions = panel.drop_duplicates("region")[["region", "lon", "lat"]].reset_index(drop=True)
    lon, lat = regions.lon.values, regions.lat.values
    lga = np.array([None] * len(regions), dtype=object)
    for ft in feats:
        inside = np.zeros(len(regions), bool)
        for ring, ext in _rings(ft["geometry"]):
            hit = _inside(lon, lat, ring)
            inside = (inside | hit) if ext else (inside & ~hit)
        lga[inside] = ft["properties"]["lga_name_2021"]
    regions["lga"] = lga
    hit = regions[regions.lga.notna()]
    north = (regions.lat > -32.75) & regions.lga.isna()
    q = qindex(2022, 1)
    return ({r: q for r in hit.region}, regions[north].region.tolist(),
            hit.set_index("region").lga)


# --------------------------------------------------------------------- 3G
def three_g(panel):
    """Statewide switch-offs: no untouched control exists, so describe only.

    TPG/Vodafone completed in January 2024 (2024 Q1); Telstra and Optus on
    28 October 2024 (2024 Q4). With every region touched at once, the quarter
    fixed effect would absorb the whole change. What can be asked is whether
    the statewide series breaks at those quarters relative to its own trend
    and season, and whether urban and non-urban regions moved differently -
    on the assumption, stated not tested, that 3G-only devices were more
    common outside the cities.
    """
    d = panel.copy()
    d["urban"] = in_city(d.lon.values, d.lat.values)
    rows = []
    for t, g in d.groupby("t"):
        for name, sub in (("city", g[g.urban]), ("rest of NSW", g[~g.urban])):
            w = sub.tests
            rows.append({"t": t, "quarter": qlabel(t), "area": name,
                         "median_mbps": float(np.exp(np.average(sub.log_speed, weights=w))),
                         "tests": int(w.sum()), "regions": len(sub)})
    s = pd.DataFrame(rows)
    s["yoy_speed_%"] = s.groupby("area").median_mbps.pct_change(4) * 100
    s["yoy_tests_%"] = s.groupby("area").tests.pct_change(4) * 100
    return s


def main():
    panel = load_panel()
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    summaries, all_coefs = [], []

    def run(name, event_q, controls, outcome="log_speed"):
        coefs, d = event_study(panel, event_q, list(event_q), controls, outcome)
        coefs.insert(0, "outcome", outcome)
        coefs.insert(0, "event", name)
        all_coefs.append(coefs)
        s = summarise(name, coefs, len(event_q), len(controls))
        s["outcome"] = outcome
        summaries.append(s)
        return coefs

    for radius in (10, 5, 20):
        eq, ctrl, n_sites = towers(panel, radius)
        tag = f"towers, {radius} km" + ("" if radius == 10 else " (check)")
        for outcome in (("log_speed", "log_tests") if radius == 10 else ("log_speed",)):
            run(tag, eq, ctrl, outcome)

    eq, ctrl = fires(panel)
    for outcome in ("log_speed", "log_tests"):
        run("fires 2019-20", eq, ctrl, outcome)
    eq_all, ctrl_all = fires(panel, threshold=1 / 9)
    run("fires, any burn (check)", eq_all, ctrl_all)

    eq, ctrl, lga = floods(panel)
    for outcome in ("log_speed", "log_tests"):
        run("floods 2022", eq, ctrl, outcome)
    lismore = {r: q for r, q in eq.items() if lga.get(r) == "Lismore"}
    if lismore:
        run("floods, Lismore only", lismore, ctrl)

    summary = pd.DataFrame(summaries)
    summary.to_csv(out_dir / "summary.csv", index=False)
    pd.concat(all_coefs).to_csv(out_dir / "coefficients.csv", index=False)
    # 3G as a difference: non-city regions against city regions, at each switch-off.
    # This rests on an assumption the data cannot check - that 3G-only devices
    # were more common outside the cities - so it is labelled as such.
    regions = panel.drop_duplicates("region")[["region", "lon", "lat"]]
    city = in_city(regions.lon.values, regions.lat.values)
    rest, cities = regions[~city].region.tolist(), regions[city].region.tolist()
    for label, q in (("3G off, TPG 2024 Q1 (rest vs city)", qindex(2024, 1)),
                     ("3G off, Telstra/Optus 2024 Q4 (rest vs city)", qindex(2024, 4))):
        for outcome in ("log_speed", "log_tests"):
            run(label, {r: q for r in rest}, cities, outcome)
    summary = pd.DataFrame(summaries)
    summary.to_csv(out_dir / "summary.csv", index=False)
    pd.concat(all_coefs).to_csv(out_dir / "coefficients.csv", index=False)

    g3 = three_g(panel)
    g3.to_csv(out_dir / "three_g_series.csv", index=False)

    pd.set_option("display.width", 200)
    print(summary.to_string(index=False))
    print("\n3G: statewide series around the switch-offs (2024 Q1 TPG, 2024 Q4 Telstra/Optus)")
    show = g3[g3.t.between(qindex(2023, 1), qindex(2025, 4))]
    print(show.pivot(index="quarter", columns="area",
                     values=["median_mbps", "tests", "yoy_speed_%", "yoy_tests_%"])
          .round(1).to_string())


if __name__ == "__main__":
    main()
