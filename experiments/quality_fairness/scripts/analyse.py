"""Independent descriptive extension. Never imports the team's processed panel."""
from __future__ import annotations

import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import box

from acquire import save_json, sha

CLASSES = {"10": "Major Cities", "11": "Inner Regional", "12": "Outer Regional",
           "13": "Remote", "14": "Very Remote"}
METRICS = ["down_mbps", "up_mbps", "lat_ms"]
FLAGS = ["download", "upload", "latency", "any_metric", "extra_only"]
PATTERNS = {0: "No flagged deterioration", 1: "Download only", 2: "Upload only", 3: "Download + upload",
            4: "Latency only", 5: "Download + latency", 6: "Upload + latency", 7: "All three"}


def write_csv(frame, relative):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.12g")


def tile_polygon(key):
    if len(key) != 12 or any(c not in "0123" for c in key):
        raise ValueError(f"Invalid zoom-12 quadkey: {key}")
    x = y = 0
    for c in key:
        x, y = 2*x + (int(c) & 1), 2*y + (int(c) >> 1)
    n = 2**len(key)
    lon = lambda a: a / n * 360 - 180
    lat = lambda a: math.degrees(math.atan(math.sinh(math.pi*(1-2*a/n))))
    return box(lon(x), lat(y+1), lon(x+1), lat(y))


def assign_points(points, ra):
    """No nearest match, no silent duplicate spatial joins at boundaries."""
    joined = gpd.sjoin(points, ra[["ra_code", "ra_name", "geometry"]], how="left", predicate="intersects")
    rows = []
    for region, hits in joined.groupby("region", sort=True):
        valid = hits[hits.ra_code.notna()]
        count = len(valid)
        code = str(valid.ra_code.iloc[0]) if count == 1 else None
        status = "unique_nsw" if code in CLASSES else "unique_outside_nsw" if count == 1 else "unmatched" if count == 0 else "ambiguous"
        rows.append({"region": region, "ra_code": code,
                     "ra_name": valid.ra_name.iloc[0] if count == 1 else None,
                     "geography_status": status, "polygon_matches": count})
    return pd.DataFrame(rows)


def geography(panel):
    print("Matching official ABS polygons; testing mixed-boundary tiles...", flush=True)
    raw = ROOT / "data/raw/abs_ra_2021.zip"
    ra = gpd.read_file(f"zip://{raw}!ASGS_Ed3_2021_RA_GDA2020.gpkg")
    ra = ra.rename(columns={"RA_CODE_2021": "ra_code", "RA_NAME_2021": "ra_name"})
    ra["ra_code"] = ra.ra_code.astype(str)
    ra = ra[ra.geometry.notna()].to_crs(4326)
    if not ra.geometry.is_valid.all():
        raise ValueError("Invalid official geometry: investigate, do not silently repair")
    centres = panel[["region", "lon", "lat"]].drop_duplicates("region")
    points = gpd.GeoDataFrame(centres, geometry=gpd.points_from_xy(centres.lon, centres.lat), crs=4326)
    mapping = assign_points(points, ra)
    boundaries = []
    # Positive-area intersection avoids marking a tile mixed just because it touches an edge.
    for key in mapping.region:
        polygon = tile_polygon(key)
        candidates = ra.iloc[ra.sindex.query(polygon, predicate="intersects")]
        codes = {str(r.ra_code)[-1] for r in candidates.itertuples()
                 if polygon.intersection(r.geometry).area > 1e-12 and str(r.ra_code)[-1] in "01234"}
        boundaries.append(len(codes) > 1)
    mapping["mixed_ra_tile"] = boundaries
    mapping = mapping.merge(centres, on="region", validate="one_to_one")
    joined = panel.merge(mapping.drop(columns=["lon", "lat"]), on="region", validate="many_to_one")
    assert len(joined) == len(panel)
    audit = joined.groupby("geography_status", dropna=False).agg(rows=("region", "size"), grids=("region", "nunique")).reset_index()
    write_csv(mapping, "data/region_remoteness.csv")
    write_csv(audit, "results/geography_audit.csv")
    selected = joined[joined.geography_status == "unique_nsw"].copy()
    selected["ra_group"] = selected.ra_code.map(CLASSES)
    write_csv(selected, "data/panel_nsw.csv")
    return selected, audit


def validate_panel(panel):
    if panel.duplicated(["region", "t"]).any():
        raise ValueError("Duplicate region-quarter")
    if not ((panel.quarter.between(1, 4)) & (panel.t == panel.year*4+panel.quarter)).all():
        raise ValueError("Inconsistent quarter index")
    if panel.empty:
        raise ValueError("Empty panel")


def assess(panel, threshold=.2, min_tests=50, latency_floor=0, exclude_mixed=False):
    validate_panel(panel)
    frame = panel.sort_values(["region", "t"]).copy()
    cols = ["region", "t", *METRICS, "tests", "invalid_tiles"]
    for k in (1, 2):
        future = panel[cols].copy()
        future["t"] -= k
        future[f"exists_{k}"] = True
        future = future.rename(columns={c: f"{c}_{k}" for c in cols if c not in ["region", "t"]})
        frame = frame.merge(future, on=["region", "t"], how="left", validate="one_to_one")
    # Status is mutually exclusive, in the documented priority order.
    right = frame.t > panel.t.max() - 2
    missing = frame[["exists_1", "exists_2"]].isna().any(axis=1)
    metric_cols = [f"{m}{suffix}" for suffix in ("", "_1", "_2") for m in METRICS]
    invalid = ~np.isfinite(frame[metric_cols]).all(axis=1) | frame[metric_cols].le(0).any(axis=1)
    for suffix in ("", "_1", "_2"):
        invalid |= frame[f"invalid_tiles{suffix}"].ne(0)
        invalid |= ~np.isfinite(frame[f"tests{suffix}"])
    low_tests = frame[["tests", "tests_1", "tests_2"]].lt(min_tests).any(axis=1)
    mixed = frame.mixed_ra_tile.astype(bool) if exclude_mixed else np.zeros(len(frame), dtype=bool)
    frame["status"] = np.select([right, missing, invalid, low_tests, mixed],
                                ["right_censored", "missing_future", "invalid_metrics", "low_tests", "mixed_boundary"], default="eligible")
    ok = frame.status == "eligible"
    # Small relative tolerance only to make exactly-on-threshold arithmetic reproducible.
    def le(a, b):
        return (a < b) | np.isclose(a, b, rtol=1e-12, atol=0)
    def ge(a, b):
        return (a > b) | np.isclose(a, b, rtol=1e-12, atol=0)
    d = le(frame.down_mbps_1, (1-threshold)*frame.down_mbps) & le(frame.down_mbps_2, (1-threshold)*frame.down_mbps)
    u = le(frame.up_mbps_1, (1-threshold)*frame.up_mbps) & le(frame.up_mbps_2, (1-threshold)*frame.up_mbps)
    l = ge(frame.lat_ms_1, (1+threshold)*frame.lat_ms) & ge(frame.lat_ms_2, (1+threshold)*frame.lat_ms)
    l &= ge(frame.lat_ms_1-frame.lat_ms, latency_floor) & ge(frame.lat_ms_2-frame.lat_ms, latency_floor)
    for name, flag in zip(FLAGS, [d, u, l, d|u|l, (~d)&(u|l)]):
        frame[name] = pd.Series(flag, index=frame.index, dtype="boolean").where(ok)
    pattern = d.astype(int) + 2*u.astype(int) + 4*l.astype(int)
    frame["pattern"] = pattern.map(PATTERNS).where(ok)
    return frame.drop(columns=["exists_1", "exists_2"])


def contiguous_runs(frame, flag="extra_only"):
    marked = frame[frame[flag].fillna(False)].sort_values(["region", "t"])
    starts = marked.region.ne(marked.region.shift()) | marked.t.diff().ne(1)
    return int(starts.sum())


def cluster_interval(frame, numerator, denominator=None, draws=1000):
    if frame.region.nunique() < 2:
        return np.nan, np.nan
    values = pd.DataFrame({"region": frame.region,
                           "num": frame[numerator].astype(int),
                           "den": 1 if denominator is None else frame[denominator].astype(int)})
    totals = values.groupby("region")[["num", "den"]].sum().to_numpy()
    rng = np.random.default_rng(2112)
    samples = []
    for _ in range(draws):
        selected = totals[rng.integers(0, len(totals), len(totals))].sum(axis=0)
        if selected[1] > 0:
            samples.append(100*selected[0]/selected[1])
    return tuple(np.quantile(samples, [.025, .975])) if samples else (np.nan, np.nan)


def summaries(frame, intervals=False):
    rows = []
    for name in ["All NSW sample", *CLASSES.values()]:
        group = frame if name == "All NSW sample" else frame[frame.ra_group == name]
        sample = group[group.status == "eligible"]
        n = len(sample)
        row = {"ra_group": name, "observed_records": len(group), "observed_grids": group.region.nunique(),
               "eligible_records": n, "eligible_grids": sample.region.nunique(),
               "mature_records": int((group.status != "right_censored").sum())}
        for status in ["right_censored", "missing_future", "invalid_metrics", "low_tests", "mixed_boundary"]:
            row[status] = int((group.status == status).sum())
        for f in FLAGS:
            row[f"{f}_n"] = int(sample[f].sum())
            row[f"{f}_pct"] = 100*row[f"{f}_n"]/n if n else np.nan
        row["extra_share_of_any_pct"] = 100*row["extra_only_n"]/row["any_metric_n"] if row["any_metric_n"] else np.nan
        row["extra_distinct_grids"] = sample[sample.extra_only.fillna(False)].region.nunique()
        row["extra_contiguous_runs"] = contiguous_runs(sample)
        row["assessable_mature_pct"] = 100*n/row["mature_records"] if row["mature_records"] else np.nan
        if intervals:
            for flag, denominator, prefix in [("download", None, "download"), ("extra_only", None, "extra_only"),
                                              ("extra_only", "any_metric", "extra_share_of_any")]:
                row[f"{prefix}_ci_low"], row[f"{prefix}_ci_high"] = cluster_interval(sample, flag, denominator)
        rows.append(row)
    return pd.DataFrame(rows)


def quarter_comparisons(frame):
    rows = []
    eligible = frame[frame.status == "eligible"]
    for t in sorted(frame.t.unique()):
        for name in CLASSES.values():
            group = eligible[(eligible.t == t) & (eligible.ra_group == name)]
            row = {"t": t, "quarter_label": f"{(t-1)//4}Q{(t-1)%4+1}", "ra_group": name, "n": len(group)}
            for flag in FLAGS:
                row[f"{flag}_n"] = int(group[flag].sum())
                row[f"{flag}_pct"] = 100*group[flag].sum()/len(group) if len(group) else np.nan
            rows.append(row)
    quarters = pd.DataFrame(rows)
    common = set.intersection(*[set(quarters.loc[(quarters.ra_group == g) & (quarters.n > 0), "t"]) for g in CLASSES.values()])
    standards = []
    if common:
        for name in CLASSES.values():
            group = quarters[(quarters.ra_group == name) & quarters.t.isin(common)]
            standards.append({"ra_group": name, "common_quarters": len(common),
                              **{f"{f}_pct": group[f"{f}_pct"].mean() for f in FLAGS}})
    contrasts = []
    city = quarters[(quarters.ra_group == "Major Cities") & (quarters.n > 0)]
    for name in list(CLASSES.values())[1:]:
        other = quarters[(quarters.ra_group == name) & (quarters.n > 0)]
        matched = city.merge(other, on="t", suffixes=("_city", "_other"), validate="one_to_one")
        row = {"ra_group": name, "reference": "Major Cities", "common_quarters": len(matched)}
        for flag in FLAGS:
            row[f"{flag}_other_pct"] = matched[f"{flag}_pct_other"].mean()
            row[f"{flag}_city_pct"] = matched[f"{flag}_pct_city"].mean()
            row[f"{flag}_difference_pp"] = (matched[f"{flag}_pct_other"]-matched[f"{flag}_pct_city"]).mean()
        contrasts.append(row)
    write_csv(quarters, "results/quarter_rates.csv")
    write_csv(pd.DataFrame(standards, columns=["ra_group", "common_quarters", *[f"{f}_pct" for f in FLAGS]]), "results/equal_quarter_all_classes.csv")
    write_csv(pd.DataFrame(contrasts), "results/equal_quarter_pairwise.csv")
    return sorted(common)


def figures(primary, summary, sensitivity):
    out = ROOT / "figures"
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    def save(fig, name):
        fig.savefig(out / f"{name}.png", dpi=180, bbox_inches="tight")
        fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
        plt.close(fig)
    eligible = primary[primary.status == "eligible"]
    counts = eligible.pattern.value_counts().reindex(list(PATTERNS.values())[1:], fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color=["#277DA8" if "Download" in p or p == "All three" else "#D97A24" for p in counts.index[::-1]])
    for bar, name in zip(bars, counts.index[::-1]):
        if "Download" not in name and name != "All three":
            bar.set_hatch("//")
    ax.bar_label(bars, padding=4)
    ax.set_xlim(0, max(counts.max()*1.22, 1))
    ax.set_xlabel("Eligible region–baseline-quarter records (not independent faults)")
    ax.set_title(f"Deterioration patterns; {len(eligible):,} assessable records\nOrange: upload/latency patterns without download deterioration")
    save(fig, "01_patterns")
    groups = summary[summary.ra_group != "All NSW sample"].set_index("ra_group")
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(groups))
    # Display-only safeguard: preserve all estimates in CSV; do not visually rank tiny groups.
    display_ok = (groups.eligible_records >= 30) & (groups.eligible_grids >= 5)
    ax.bar(x-.18, groups.download_pct.where(display_ok), .36, label="Download deterioration", color="#277DA8")
    ax.bar(x+.18, groups.extra_only_pct.where(display_ok), .36, label="Additional upload/latency only", color="#D97A24", hatch="//")
    for i, (_, r) in enumerate(groups.iterrows()):
        if not display_ok.iloc[i]:
            ax.text(i, 1, "Insufficient\nsample" if r.eligible_records else "No eligible\nrecords", ha="center", fontsize=9)
    ax.set_xticks(x, [f"{g}\nn={int(r.eligible_records):,}; grids={int(r.eligible_grids)}" for g,r in groups.iterrows()], fontsize=9)
    ax.set_ylabel("% of eligible records (pooled quarters)")
    ax.set_title("Observed deterioration by official ABS remoteness\nBars hidden if n<30 or grids<5; all estimates retained in CSV")
    ax.legend(loc="upper left", fontsize=9)
    save(fig, "02_remoteness_rates")
    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = np.zeros(len(groups))
    for field, label, color, hatch in [("eligible_records", "Assessable", "#277DA8", ""), ("low_tests", "<50 tests in at least one quarter", "#E3A32B", "//"),
                                      ("missing_future", "Missing future quarter", "#ADB5BD", ".."), ("invalid_metrics", "Invalid source metrics", "#DC645C", "xx")]:
        values = 100*groups[field]/groups.mature_records.replace(0, np.nan)
        ax.bar(x, values, bottom=bottom, label=label, color=color, hatch=hatch)
        bottom += values.fillna(0).to_numpy()
    ax.set_xticks(x, [f"{g}\nn={int(r.mature_records):,}" for g,r in groups.iterrows()], fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("% of observed mature baseline records")
    ax.set_title("Assessability is unequal across remoteness classes\nFinal two quarters excluded as right-censored; absent baseline cells not counted")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -.18), fontsize=9, ncol=2)
    save(fig, "03_assessability")
    all_rows = sensitivity[sensitivity.ra_group == "All NSW sample"]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(all_rows.scenario[::-1], all_rows.extra_share_of_any_pct[::-1], color="#D97A24")
    ax.bar_label(bars, fmt="%.1f%%", padding=4)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Upload/latency-only records as % of all flagged records")
    ax.set_title("All pre-specified sensitivity checks (observed NSW sample)")
    save(fig, "04_sensitivity")


def main():
    panel = pd.read_csv(ROOT / "data/panel_bbox.csv", dtype={"region": str})
    validate_panel(panel)
    selected, audit = geography(panel)
    print(audit.to_string(index=False), flush=True)
    primary = assess(selected)
    write_csv(primary, "results/record_assessments.csv")
    summary = summaries(primary, intervals=True)
    write_csv(summary, "results/summary.csv")
    counts = primary[primary.status == "eligible"].pattern.value_counts().reindex(PATTERNS.values(), fill_value=0)
    write_csv(counts.rename_axis("pattern").reset_index(name="records"), "results/pattern_counts.csv")
    common = quarter_comparisons(primary)
    variants = [("Primary: 20%, >=50 tests", {}), ("15% change", {"threshold": .15}), ("25% change", {"threshold": .25}),
                (">=100 tests", {"min_tests": 100}), ("Latency also >=5 ms", {"latency_floor": 5}),
                ("Latency also >=10 ms", {"latency_floor": 10}), ("Exclude mixed-RA tiles", {"exclude_mixed": True})]
    results = []
    for label, settings in variants:
        s = summaries(primary if not settings else assess(selected, **settings))
        s.insert(0, "scenario", label)
        results.append(s)
    sensitivity = pd.concat(results, ignore_index=True)
    write_csv(sensitivity, "results/sensitivity.csv")
    # Deterministic examples, not selected for the size of a change.
    examples = primary[primary.status == "eligible"].sort_values(["region", "t"]).groupby("pattern", sort=True).head(1)
    write_csv(examples, "results/first_example_each_pattern.csv")
    figures(primary, summary, sensitivity)
    save_json(ROOT / "results/run_metadata.json", {
        "panel_sha256": sha(ROOT / "data/panel_nsw.csv"), "abs_sha256": sha(ROOT / "data/raw/abs_ra_2021.zip"),
        "protocol_sha256": sha(ROOT / "PROTOCOL.md"), "bootstrap_draws": 1000, "bootstrap_seed": 2112,
        "common_all_five_quarters": common, "geography": "Unique centroid in NSW RA 10–14",
        "mixed_ra_selected_grids": int(selected.drop_duplicates("region").mixed_ra_tile.sum()),
        "results_sha256": {p.name: sha(p) for p in sorted((ROOT / "results").glob("*.csv"))}})
    print(summary[["ra_group", "observed_records", "eligible_records", "eligible_grids", "download_n", "extra_only_n", "any_metric_n", "extra_share_of_any_pct", "assessable_mature_pct"]].to_string(index=False), flush=True)
    print("All-five common quarters:", len(common), flush=True)


if __name__ == "__main__":
    main()
