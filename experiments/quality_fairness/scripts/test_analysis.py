"""Small constructed cases verify the definitions, not just real-data outputs."""
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from analyse import assess, assign_points, contiguous_runs, summaries, tile_polygon


def panel(down=(100, 80, 80, 100, 100), up=(20, 20, 20, 20, 20), lat=(20, 20, 20, 20, 20)):
    n = len(down)
    t = np.arange(8077, 8077+n)
    return pd.DataFrame({"region": ["311230000000"]*n, "t": t, "year": (t-1)//4, "quarter": (t-1)%4+1,
                         "down_mbps": down, "up_mbps": up, "lat_ms": lat, "tests": 50,
                         "invalid_tiles": 0, "mixed_ra_tile": False, "ra_group": "Major Cities"})


def test_inclusive_same_baseline_not_compounded():
    r = assess(panel()).iloc[0]
    assert r.status == "eligible" and r.download and not r.extra_only


def test_one_bad_quarter_not_persistent():
    assert not assess(panel(down=(100, 79, 81, 100, 100))).iloc[0].download


def test_additional_upload_latency_not_download():
    r = assess(panel(down=(100, 100, 100, 100, 100), up=(20, 16, 16, 20, 20), lat=(20, 24, 24, 20, 20))).iloc[0]
    assert r.extra_only and r.upload and r.latency and not r.download
    assert r.pattern == "Upload + latency"


def test_latency_direction_and_absolute_floor():
    p = panel(down=(100,)*5, lat=(5, 6, 6, 5, 5))
    assert assess(p).iloc[0].latency
    assert not assess(p, latency_floor=5).iloc[0].latency
    p.lat_ms = [20, 10, 10, 20, 20]
    assert not assess(p).iloc[0].latency


@pytest.mark.parametrize("bad", [0, -1, np.nan, np.inf])
def test_invalid_values_unknown_not_healthy(bad):
    p = panel()
    p["lat_ms"] = p.lat_ms.astype(float)
    p.loc[1, "lat_ms"] = bad
    r = assess(p).iloc[0]
    assert r.status == "invalid_metrics" and pd.isna(r.download)


def test_invalid_tile_rejects_otherwise_finite_aggregate():
    p = panel()
    p.loc[1, "invalid_tiles"] = 1
    assert assess(p).iloc[0].status == "invalid_metrics"


def test_all_three_quarters_need_enough_tests():
    p = panel()
    p.loc[2, "tests"] = 49
    r = assess(p).iloc[0]
    assert r.status == "low_tests" and pd.isna(r.download)
    assert assess(panel()).iloc[0].status == "eligible"


def test_missing_tests_invalid():
    p = panel()
    p.loc[0, "tests"] = np.nan
    assert assess(p).iloc[0].status == "invalid_metrics"


def test_gaps_not_replaced_by_next_observation():
    p = panel().drop(index=1)
    r = assess(p).iloc[0]
    assert r.status == "missing_future" and pd.isna(r.any_metric)


def test_last_two_unknown_even_when_speeds_positive():
    rows = assess(panel()).tail(2)
    assert rows.status.eq("right_censored").all()
    assert rows.download.isna().all()


def test_duplicate_rejected():
    p = panel()
    with pytest.raises(ValueError, match="Duplicate"):
        assess(pd.concat([p, p.iloc[:1]]))


def test_mixed_boundary_sensitivity():
    p = panel()
    p.mixed_ra_tile = True
    assert assess(p).iloc[0].status == "eligible"
    assert assess(p, exclude_mixed=True).iloc[0].status == "mixed_boundary"


def test_union_denominator_and_all_classes_present():
    p = assess(panel())
    s = summaries(p)
    assert len(s) == 6
    row = s.iloc[0]
    assert row.eligible_records == 3
    assert row.any_metric_n == row.download_n + row.extra_only_n
    assert s.iloc[-1].eligible_records == 0
    assert pd.isna(s.iloc[-1].extra_only_pct)


def test_runs_not_overlapping_window_count():
    p = pd.DataFrame({"region": ["a", "a", "a", "a", "b"], "t": [1, 2, 4, 5, 1], "extra_only": [True]*5})
    assert contiguous_runs(p) == 3


def test_spatial_boundary_is_ambiguous_and_missing_is_retained():
    ra = gpd.GeoDataFrame({"ra_code": ["10", "11"], "ra_name": ["Major Cities", "Inner Regional"]},
                          geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=4326)
    pts = gpd.GeoDataFrame({"region": ["a", "b", "c"]}, geometry=[Point(.5, .5), Point(1, .5), Point(4, 4)], crs=4326)
    out = assign_points(pts, ra).set_index("region")
    assert out.loc["a", "geography_status"] == "unique_nsw"
    assert out.loc["b", "geography_status"] == "ambiguous"
    assert out.loc["c", "geography_status"] == "unmatched"
    assert pd.isna(out.loc["b", "ra_code"])


def test_quadkey_validation():
    assert tile_polygon("311230000000").area > 0
    with pytest.raises(ValueError):
        tile_polygon("not_a_quadkey")
