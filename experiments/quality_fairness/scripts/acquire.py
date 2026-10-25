"""Re-acquire official inputs. No teammate panel or modelling filter is used."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import time
import urllib.request

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "src"))
from quadkey import bbox_prefixes, quadkey_to_lonlat

ABS_PAGE = "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files"
ABS_URL = ABS_PAGE + "/ASGS_Ed3_2021_RA_GPKG_GDA2020.zip"
OOKLA_BASE = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=mobile/year={y}/quarter={q}/{y}-{m:02d}-01_performance_mobile_tiles.parquet"
PERIODS = [(y, q) for y in range(2019, 2027) for q in range(1, 5) if (y, q) <= (2026, 1)]


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ENGG2112-public-data-research/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return {k: r.headers.get(k) for k in ("ETag", "Last-Modified", "Content-Length")}


def connection():
    cache = ROOT / ".cache"
    (cache / "extensions").mkdir(parents=True, exist_ok=True)
    (cache / "tmp").mkdir(parents=True, exist_ok=True)
    return duckdb.connect(config={"extension_directory": str(cache / "extensions"),
                                  "temp_directory": str(cache / "tmp"),
                                  "memory_limit": "1GB", "threads": "2",
                                  "max_temp_directory_size": "512MB"})


def acquire_abs():
    path = ROOT / "data/raw/abs_ra_2021.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = ROOT / "provenance/abs_source.json"
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if sha(path) != meta["sha256"]:
            raise ValueError("ABS cache hash mismatch; inspect before replacing")
        print("ABS boundary: verified cached original", flush=True)
        return
    meta = head(ABS_URL)
    req = urllib.request.Request(ABS_URL, headers={"User-Agent": "ENGG2112-public-data-research/1.0"})
    partial = path.with_suffix(".partial")
    with urllib.request.urlopen(req, timeout=180) as r, partial.open("wb") as f:
        shutil.copyfileobj(r, f)
    partial.replace(path)
    save_json(meta_path, {"url": ABS_URL, "source_page": ABS_PAGE, "metadata": meta,
                         "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                         "sha256": sha(path), "bytes": path.stat().st_size,
                         "classification": "ASGS 2021 Remoteness Areas, GDA2020"})
    print(f"ABS boundary: downloaded {path.stat().st_size:,} bytes", flush=True)


def acquire_quarter(yq):
    y, q = yq
    key = f"{y}Q{q}"
    path = ROOT / f"data/quarters/{key}.csv"
    meta_path = ROOT / f"provenance/quarters/{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if sha(path) != meta["aggregate_sha256"]:
            raise ValueError(f"{key}: cache hash mismatch")
        print(f"{key}: verified cached aggregate", flush=True)
        return
    url = OOKLA_BASE.format(y=y, q=q, m=3*q-2)
    prefixes = bbox_prefixes(141.0, -37.6, 154.0, -28.1, 8)
    where = " OR ".join(f"quadkey LIKE '{p}%'" for p in prefixes)
    query = f"""
        SELECT substr(quadkey, 1, 12) AS region,
          sum(avg_d_kbps * tests) / sum(tests) / 1000.0 AS down_mbps,
          sum(avg_u_kbps * tests) / sum(tests) / 1000.0 AS up_mbps,
          sum(avg_lat_ms * tests) / sum(tests) AS lat_ms,
          sum(tests) AS tests, sum(devices) AS tile_devices_sum,
          count(*) AS n_tiles,
          sum(CASE WHEN avg_d_kbps IS NULL OR avg_u_kbps IS NULL
             OR avg_lat_ms IS NULL OR avg_d_kbps <= 0 OR avg_u_kbps <= 0
             OR avg_lat_ms <= 0 OR tests IS NULL OR tests <= 0 THEN 1 ELSE 0 END) AS invalid_tiles
        FROM read_parquet('{url}') WHERE {where}
        GROUP BY 1 HAVING sum(tests) > 0 ORDER BY 1
    """
    start = time.monotonic()
    # Retry transient errors; never silently omit a planned quarter.
    for attempt in range(3):
        try:
            metadata = head(url)
            with connection() as con:
                con.execute("LOAD httpfs")
                frame = con.execute(query).df()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    if frame.empty:
        raise ValueError(f"{key}: empty quarter")
    frame["year"], frame["quarter"] = y, q
    partial = path.with_suffix(".partial")
    frame.to_csv(partial, index=False, float_format="%.12g")
    partial.replace(path)
    save_json(meta_path, {"url": url, "metadata": metadata, "query": query,
                         "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                         "elapsed_seconds": round(time.monotonic()-start, 3),
                         "aggregate_rows": len(frame), "aggregate_sha256": sha(path)})
    print(f"{key}: {len(frame):,} positive-test grid rows, {time.monotonic()-start:.1f}s", flush=True)


def main(workers=2, abs_only=False):
    acquire_abs()
    if abs_only:
        return
    with connection() as con:
        con.execute("INSTALL httpfs; LOAD httpfs;")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = [pool.submit(acquire_quarter, yq) for yq in PERIODS]
        for task in as_completed(tasks):
            task.result()
    frames = [pd.read_csv(ROOT / f"data/quarters/{y}Q{q}.csv", dtype={"region": str}) for y,q in PERIODS]
    panel = pd.concat(frames, ignore_index=True)
    panel["t"] = panel.year * 4 + panel.quarter
    panel = panel.sort_values(["region", "t"]).reset_index(drop=True)
    if panel.duplicated(["region", "t"]).any():
        raise ValueError("Duplicate region-quarter")
    if set(zip(panel.year, panel.quarter)) != set(PERIODS):
        raise ValueError("Incomplete planned period")
    coords = panel.region.map(quadkey_to_lonlat)
    panel["lon"] = coords.str[0]
    panel["lat"] = coords.str[1]
    dest = ROOT / "data/panel_bbox.csv"
    panel.to_csv(dest, index=False, float_format="%.12g")
    save_json(ROOT / "provenance/acquisition.json", {
        "planned_quarters": len(PERIODS), "rows_before_geography": len(panel),
        "unique_grids_before_geography": panel.region.nunique(), "panel_sha256": sha(dest),
        "protocol_sha256": sha(ROOT / "PROTOCOL.md"), "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in
                     ("duckdb", "pandas", "numpy", "geopandas", "shapely", "pyogrio", "pyproj", "matplotlib")},
        "source_scope": "Independent remote queries; no teammate panel imported",
        "metric": "test-count-weighted arithmetic means; device sums not unique persons"})
    print(f"Complete: {len(panel):,} grid-quarter rows across {len(PERIODS)} quarters", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--abs-only", action="store_true")
    args = parser.parse_args()
    main(args.workers, args.abs_only)
