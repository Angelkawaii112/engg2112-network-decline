"""Check official SA2-code compatibility before modelling."""
from settings import ROOT, SOURCE, check_source
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd



if __name__ == "__main__":
    archive = ROOT / "data/abs/SA2_2021_AUST_SHP_GDA2020.zip"
    boundaries = gpd.read_file(f"zip://{archive.as_posix()}")
    nsw = boundaries[boundaries.STE_CODE21.astype(str) == "1"]
    population = pd.read_csv(ROOT / "data/derived/population_vintages.csv", dtype={"sa2": str})
    codes = set(nsw.SA2_CODE21.astype(str))
    missing = sorted(set(population.sa2) - codes)
    if missing:
        raise ValueError(f"ERP codes absent from ASGS2021 NSW boundaries: {missing}")
    info = dict(nsw_sa2_boundary_records=len(nsw), population_sa2_codes=population.sa2.nunique(),
                unmatched_erp_codes=missing, source_crs=str(boundaries.crs),
                absent_geometry_codes=nsw.loc[nsw.geometry.isna(), "SA2_CODE21"].astype(str).tolist())
    (ROOT / "results/input_validation.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info, indent=2))
