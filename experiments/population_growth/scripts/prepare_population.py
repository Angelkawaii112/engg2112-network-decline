"""Parse release-specific ERP growth and match NSW quadkey centres to ASGS2021 SA2s."""
from settings import ROOT, SOURCE, check_source
import argparse
import json
from pathlib import Path
import re
import sys

import geopandas as gpd
import numpy as np
import openpyxl
import pandas as pd

sys.path.insert(0, str(SOURCE / "src"))
from quadkey import quadkey_to_lonlat


def parse_vintages():
    manifest = json.loads((ROOT / "data/abs/manifest.json").read_text(encoding="utf-8"))
    rows, checks = [], []
    for asset in manifest["assets"]:
        if asset["erp_year"] is None:
            continue
        year = asset["erp_year"]
        workbook = openpyxl.load_workbook(ROOT / asset["path"], read_only=True, data_only=True)
        # Bound the columns: some ABS workbooks have thousands of styled empty columns.
        table = list(workbook["Table 1"].iter_rows(max_col=64, values_only=True))
        header_idx = next(i for i, row in enumerate(table[:20]) if "SA2 code" in row)
        code_col = table[header_idx].index("SA2 code")
        name_col = table[header_idx].index("SA2 name")
        year_row = next(row for row in table[:header_idx] if year in row and year - 1 in row)
        current_col, previous_col = year_row.index(year), year_row.index(year - 1)
        dates = [str(value) for row in table[:header_idx] for value in row
                 if value and "Released at" in str(value)]
        page_evidence = (ROOT / asset["publication_evidence"]).read_text(encoding="utf-8")
        page_date = pd.Timestamp(asset["published"]).strftime("%d/%m/%Y")
        if page_date not in page_evidence:
            raise ValueError(f"No archived page evidence for {asset['key']} publication date {page_date}")
        if dates:
            expected = pd.Timestamp(asset["published"]).strftime("%d %B %Y").lstrip("0")
            if expected not in dates[0]:
                raise ValueError(f"Workbook date mismatch for {asset['key']}: {dates}")
        count = 0
        for row in table[header_idx + 1:]:
            code = str(row[code_col])
            if not re.fullmatch(r"1\d{8}", code):
                continue
            previous = pd.to_numeric(row[previous_col], errors="coerce")
            current = pd.to_numeric(row[current_col], errors="coerce")
            rate = (current - previous) / previous if pd.notna(previous) and previous > 0 and pd.notna(current) else np.nan
            rows.append(dict(sa2=code, sa2_name=row[name_col], erp_year=year,
                             erp_previous=previous, erp_current=current, growth_rate=rate,
                             published=asset["published"], vintage=asset["key"],
                             source_path=asset["path"], source_url=asset["url"]))
            count += 1
        workbook.close()
        checks.append(dict(vintage=asset["key"], nsw_sa2_rows=count, published=asset["published"],
                           workbook_release_text=dates, date_evidence=asset["publication_evidence"]))
        if count < 600:
            raise ValueError(f"Unexpected NSW SA2 coverage in {asset['key']}: {count}")
    population = pd.DataFrame(rows)
    if population.duplicated(["sa2", "published"]).any():
        raise ValueError("Duplicate SA2 and publication date in population vintages")
    output = ROOT / "data/derived"
    output.mkdir(exist_ok=True)
    population.to_csv(output / "population_vintages.csv", index=False)
    (ROOT / "results/population_publication_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(f"Prepared {len(population)} NSW SA2-vintage rows; {population.growth_rate.isna().sum()} undefined growth values", flush=True)
    return population


def spatial_match(panel):
    boundary_path = ROOT / "data/abs/SA2_2021_AUST_SHP_GDA2020.zip"
    boundaries = gpd.read_file(f"zip://{boundary_path.as_posix()}")
    boundaries = boundaries[boundaries.STE_CODE21.astype(str) == "1"].copy().to_crs("EPSG:4326")
    boundaries = boundaries.rename(columns={"SA2_CODE21": "sa2", "SA2_NAME21": "sa2_name"})
    boundaries.sa2 = boundaries.sa2.astype(str)
    regions = panel[["region", "lon", "lat"]].drop_duplicates("region").copy()
    regions["region"] = regions.region.astype(str)
    centres = regions.region.map(quadkey_to_lonlat)
    regions["centre_lon"] = [value[0] for value in centres]
    regions["centre_lat"] = [value[1] for value in centres]
    if not np.allclose(regions[["lon", "lat"]].values, regions[["centre_lon", "centre_lat"]].values, atol=1e-7):
        raise ValueError("Panel coordinates differ from decoded quadkey centres")
    points = gpd.GeoDataFrame(regions, geometry=gpd.points_from_xy(regions.centre_lon, regions.centre_lat), crs="EPSG:4326")
    joined = gpd.sjoin(points, boundaries[["sa2", "sa2_name", "geometry"]], how="left", predicate="intersects")
    matches = joined.groupby("region").sa2.nunique()
    joined = joined.drop_duplicates("region").drop(columns=["geometry", "index_right"])
    joined["match_count"] = joined.region.map(matches)
    joined["match_status"] = joined.match_count.map({0: "unmatched", 1: "matched"}).fillna("ambiguous")
    joined.loc[joined.match_count != 1, ["sa2", "sa2_name"]] = None
    joined.to_csv(ROOT / "data/derived/region_sa2.csv", index=False)
    counts = joined.match_status.value_counts().to_dict()
    rows = panel.merge(joined[["region", "match_status"]], on="region", how="left")
    coverage = dict(regions=len(joined), region_counts={k: int(v) for k, v in counts.items()},
                    region_matching_fraction=float((joined.match_status == "matched").mean()),
                    panel_rows=len(rows), panel_row_matching_fraction=float((rows.match_status == "matched").mean()),
                    method="Quadkey centres intersecting exactly one NSW ASGS2021 SA2 polygon; no nearest-area substitution",
                    limitation="Centres can be offshore; a quadkey region can overlap multiple SA2s. The original NSW state filter also retains some coastal centres.")
    (ROOT / "results/geographic_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    return joined


def join_available_population(panel, mapping, population):
    panel = panel.merge(mapping[["region", "sa2", "match_status"]], on="region", how="left", validate="many_to_one")
    panel["prediction_date"] = pd.PeriodIndex.from_fields(year=panel.year.astype(int), quarter=panel.quarter.astype(int), freq="Q").end_time.normalize()
    panel["row_id"] = np.arange(len(panel))
    population = population.copy()
    population["published"] = pd.to_datetime(population.published)
    matched = panel[panel.sa2.notna()].sort_values("prediction_date")
    unmatched = panel[panel.sa2.isna()].copy()
    joined = pd.merge_asof(matched, population.drop(columns="sa2_name").sort_values("published"),
                           left_on="prediction_date", right_on="published", by="sa2", direction="backward")
    joined = pd.concat([joined, unmatched], ignore_index=True).sort_values("row_id")
    have = joined.published.notna()
    if (joined.loc[have, "published"] > joined.loc[have, "prediction_date"]).any():
        raise AssertionError("Population release from the future")
    joined["population_missing_reason"] = np.select(
        [joined.match_status != "matched", joined.published.isna(), joined.growth_rate.isna()],
        ["no_unique_sa2_match", "no_historical_release_available", "undefined_growth"], default="available")
    joined.to_csv(ROOT / "data/derived/panel_population.csv", index=False)
    missing = joined.groupby(["year", "population_missing_reason"]).size().rename("rows").reset_index()
    missing.to_csv(ROOT / "results/population_missingness_by_year.csv", index=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    counts = missing.pivot(index="year", columns="population_missing_reason", values="rows").fillna(0)
    proportions = counts.div(counts.sum(axis=1), axis=0)
    ax = proportions.plot.bar(stacked=True, figsize=(10, 4.5), colormap="tab20")
    ax.set_ylabel("Fraction of network panel rows")
    ax.set_xlabel("Feature year")
    ax.set_ylim(0, 1)
    ax.set_title("Historical population growth availability at prediction time")
    ax.legend(title="Population data", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.figure.tight_layout()
    ax.figure.savefig(ROOT / "results/population_availability.png", dpi=180)
    plt.close(ax.figure)
    print(missing.to_string(index=False), flush=True)
    return joined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--population-only", action="store_true")
    args = parser.parse_args()
    population = parse_vintages()
    if not args.population_only:
        panel = pd.read_csv(ROOT / "data/network/panel_nsw.csv", dtype={"region": str})
        mapping = spatial_match(panel)
        join_available_population(panel, mapping, population)


if __name__ == "__main__":
    main()
