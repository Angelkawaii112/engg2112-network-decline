"""Independent row-by-row reconciliation of the primary result and saved evidence."""
from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

from acquire import sha, save_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = pd.read_csv(ROOT / "data/panel_nsw.csv", dtype={"region": str, "ra_code": str})
    saved = pd.read_csv(ROOT / "results/record_assessments.csv", dtype={"region": str},
                        true_values=["True"], false_values=["False"])
    lookup = {(r.region, r.t): r for r in source.itertuples()}
    assert len(lookup) == len(source) == len(saved)
    end = source.t.max()
    counts = {"eligible": 0, "download": 0, "upload": 0, "latency": 0, "any_metric": 0, "extra_only": 0}
    def le(a, b):
        return a < b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0)
    def ge(a, b):
        return a > b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0)
    for r in saved.itertuples():
        triplet = [lookup.get((r.region, r.t+k)) for k in (0, 1, 2)]
        if r.t > end-2:
            status = "right_censored"
        elif any(x is None for x in triplet):
            status = "missing_future"
        elif any(not math.isfinite(getattr(x, f)) or getattr(x, f) <= 0 for x in triplet for f in ["down_mbps", "up_mbps", "lat_ms"]) or any(x.invalid_tiles != 0 or not math.isfinite(x.tests) for x in triplet):
            status = "invalid_metrics"
        elif any(x.tests < 50 for x in triplet):
            status = "low_tests"
        else:
            status = "eligible"
        assert r.status == status, (r.region, r.t, status, r.status)
        if status != "eligible":
            assert all(pd.isna(getattr(r, f)) for f in ["download", "upload", "latency", "any_metric", "extra_only"])
            continue
        counts["eligible"] += 1
        base, a, b = triplet
        d = le(a.down_mbps, .8*base.down_mbps) and le(b.down_mbps, .8*base.down_mbps)
        u = le(a.up_mbps, .8*base.up_mbps) and le(b.up_mbps, .8*base.up_mbps)
        l = ge(a.lat_ms, 1.2*base.lat_ms) and ge(b.lat_ms, 1.2*base.lat_ms)
        for key, value in zip(["download", "upload", "latency", "any_metric", "extra_only"], [d,u,l,d or u or l,(not d) and (u or l)]):
            assert bool(getattr(r, key)) == value, (r.region, r.t, key)
            counts[key] += int(value)
    summary = pd.read_csv(ROOT / "results/summary.csv")
    total = summary.iloc[0]
    assert counts["eligible"] == total.eligible_records
    for flag in ["download", "upload", "latency", "any_metric", "extra_only"]:
        assert counts[flag] == total[f"{flag}_n"]
        assert counts[flag] == summary.iloc[1:][f"{flag}_n"].sum()
    assert counts["any_metric"] == counts["download"] + counts["extra_only"]
    assert set(source.ra_code) <= {"10", "11", "12", "13", "14"}
    assert set(zip(source.year, source.quarter)) == {(y,q) for y in range(2019,2027) for q in range(1,5) if (y,q) <= (2026,1)}
    manifest = json.loads((ROOT / "results/run_metadata.json").read_text())
    assert sha(ROOT / "data/panel_nsw.csv") == manifest["panel_sha256"]
    assert sha(ROOT / "PROTOCOL.md") == manifest["protocol_sha256"]
    for name, digest in manifest["results_sha256"].items():
        assert sha(ROOT / "results" / name) == digest
    patterns = pd.read_csv(ROOT / "results/pattern_counts.csv")
    assert patterns.pattern.notna().all()
    assert patterns.records.sum() == counts["eligible"]
    acquisition = json.loads((ROOT / "provenance/acquisition.json").read_text())
    assert sha(ROOT / "data/panel_bbox.csv") == acquisition["panel_sha256"]
    for p in (ROOT / "provenance/quarters").glob("*.json"):
        m = json.loads(p.read_text())
        assert sha(ROOT / "data/quarters" / f"{p.stem}.csv") == m["aggregate_sha256"]
    result = {"verified": True, "method": "Independent scalar reconstruction from the acquired NSW panel; no assess() call", "reconstructed_counts": counts,
              "all_saved_statuses_checked": len(saved), "quarter_aggregate_hashes_checked": 29,
              "geography_join": "unique NSW codes only", "result_hashes_checked": len(manifest["results_sha256"]),
              "source_file_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "scripts").glob("*.py"))}}
    save_json(ROOT / "results/verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
