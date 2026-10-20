"""Rebuild the original panel with resumable quarter caches, without editing original/."""
from settings import ROOT, SOURCE, check_source
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sys
from threading import Lock
import time

sys.path.insert(0, str(SOURCE / "src"))


def main(benchmark_only=False, workers=3):
    import duckdb
    import pandas as pd
    import build_panel
    from boundary import label_states
    from quadkey import bbox_prefixes

    cache = ROOT / "data/network/quarters"
    cache.mkdir(parents=True, exist_ok=True)
    duck_home = ROOT / ".cache/duckdb"
    duck_home.mkdir(parents=True, exist_ok=True)
    temp = ROOT / "tmp/duckdb"
    temp.mkdir(parents=True, exist_ok=True)
    extension = ROOT / ".cache/duckdb/extensions"
    extension.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(ROOT).free / 1024**3
    if free < 15:
        raise RuntimeError(f"Only {free:.1f} GiB free; require at least 15 GiB before rebuilding")
    print(f"Available disk: {free:.1f} GiB; budget 10-15 GiB for the whole workspace.", flush=True)
    connect = duckdb.connect

    def local_connection(*args, **kwargs):
        cfg = dict(extension_directory=str(extension), temp_directory=str(temp),
                   home_directory=str(duck_home), memory_limit="2GB", threads="4")
        cfg.update(kwargs.pop("config", {}))
        return connect(*args, config=cfg, **kwargs)

    load = build_panel.load_quarter
    timing_path = ROOT / "results/network_build_timings.json"
    timings = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else {}
    timing_lock = Lock()

    def checkpoint(con, year, quarter, prefixes, min_tests, region_zoom=12):
        path = cache / f"{year}Q{quarter}.csv"
        start = time.perf_counter()
        if path.exists():
            frame = pd.read_csv(path, dtype={"region": str})
            status = "cached"
        else:
            frame = load(con, year, quarter, prefixes, min_tests, region_zoom)
            if frame.empty:
                raise RuntimeError(f"No rows in {year}Q{quarter}")
            partial = path.with_suffix(".csv.partial")
            frame.to_csv(partial, index=False)
            partial.replace(path)
            status = "queried"
        elapsed = time.perf_counter() - start
        print(f"{year}Q{quarter}: {status}, {len(frame)} rows, {elapsed:.1f}s", flush=True)
        with timing_lock:
            if status != "cached" or f"{year}Q{quarter}" not in timings:
                timings[f"{year}Q{quarter}"] = dict(seconds=elapsed, rows=len(frame), status=status)
            timing_path.write_text(json.dumps(timings, indent=2), encoding="utf-8")
        return frame

    # In-memory adapters only. All original source and working-tree files stay unchanged.
    duckdb.connect = local_connection
    build_panel.load_quarter = checkpoint
    try:
        if benchmark_only:
            con = local_connection()
            con.execute("INSTALL httpfs; LOAD httpfs;")
            box = build_panel.NSW
            prefixes = bbox_prefixes(box["xmin"], box["ymin"], box["xmax"], box["ymax"], 8)
            checkpoint(con, 2019, 1, prefixes, 50)
            con.close()
            return
        # Query independent quarters concurrently, using the original query function.
        # The final panel is still assembled and labelled by build_panel.build.
        setup = local_connection()
        setup.execute("INSTALL httpfs; LOAD httpfs;")
        setup.close()
        box = build_panel.NSW
        prefixes = bbox_prefixes(box["xmin"], box["ymin"], box["xmax"], box["ymax"], 8)

        def prefetch(yq):
            year, quarter = yq
            if (cache / f"{year}Q{quarter}.csv").exists():
                return
            connection = local_connection()
            try:
                connection.execute("LOAD httpfs;")
                checkpoint(connection, year, quarter, prefixes, 50)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(prefetch, build_panel.quarters((2019, 1), (2026, 1))))
        panel = build_panel.build(verbose=True)
    finally:
        duckdb.connect = connect
        build_panel.load_quarter = load
    expected = set(build_panel.quarters((2019, 1), (2026, 1)))
    got = set(zip(panel.year, panel.quarter))
    if got != expected:
        raise RuntimeError(f"Incomplete panel; missing quarters: {sorted(expected-got)}")
    panel.to_csv(ROOT / "data/network/panel.csv", index=False)
    panel = label_states(panel, str(SOURCE / "data/au_states.geojson"))
    nsw = panel[panel.state == "New South Wales"].drop(columns="state")
    nsw.to_csv(ROOT / "data/network/panel_nsw.csv", index=False)
    print(f"NSW panel: {len(nsw):,} rows, {nsw.region.nunique()} regions", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-only", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    main(args.benchmark_only, args.workers)
