"""
Write docs/o2.json, the O2 page of the published site.

The site reads one JSON file per objective (docs/o2.json ... docs/o5.json) in
the format described in docs/README.md. This builds O2's from the event-study
results, adding what the page needs to draw: each event's coefficients as
percentages, where the touched and control regions are, and for towers where
the sites themselves are.

Run after event_study.py.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import event_study as es                          # noqa: E402

EVENTS = [
    {"id": "floods", "key": "floods 2022", "name": "2022 Northern Rivers floods",
     "when": "2022 Q1", "verdict": "clear", "verdict_label": "Clear trace",
     "finding": "Tests +33% in the flood quarter. Speed -23% two quarters later. "
                "Recovered within a year.",
     "caveat": "Quarterly data cannot see the outages themselves."},
    {"id": "threeg", "key": "3G off, Telstra/Optus 2024 Q4 (rest vs city)",
     "name": "Telstra and Optus 3G switch-off", "when": "2024 Q4",
     "verdict": "clear", "verdict_label": "Clear, with caveat",
     "finding": "Outside cities, speed +22% to +39% against cities a year later.",
     "caveat": "Assumes 3G-only phones were commoner outside cities. Some of the "
               "rise may be slow phones dropping out."},
    {"id": "towers", "key": "towers, 10 km", "name": "New Mobile Black Spot towers",
     "when": "2020 Q1 - 2025 Q2", "verdict": "none", "verdict_label": "No measurable trace",
     "finding": "No measurable change within 5-20 km.",
     "caveat": "Towers add coverage, which speed medians cannot see. See O5."},
    {"id": "fires", "key": "fires 2019-20", "name": "2019-20 bushfires",
     "when": "2019 Q4", "verdict": "failed", "verdict_label": "Comparison failed",
     "finding": "Burnt regions were already diverging before the fires.",
     "caveat": "Nothing here measures what the fires did."},
]


def pct(b):
    return round(float(100 * (np.exp(b) - 1)), 1)


def series(coefs, key, outcome):
    g = coefs[(coefs.event == key) & (coefs.outcome == outcome)].sort_values("k")
    return [{"k": int(r.k), "b": pct(r.beta), "lo": pct(r.lo), "hi": pct(r.hi)}
            for r in g.itertuples()]


def main():
    panel = es.load_panel()
    coords = panel.drop_duplicates("region").set_index("region")[["lon", "lat"]]
    pts = lambda regions: [[round(coords.loc[r, "lon"], 4), round(coords.loc[r, "lat"], 4)]
                           for r in regions if r in coords.index]

    eq_t, ctrl_t, _ = es.towers(panel, 10)
    eq_f, ctrl_f = es.fires(panel)
    eq_fl, ctrl_fl, _ = es.floods(panel)
    regions = panel.drop_duplicates("region")
    city = es.in_city(regions.lon.values, regions.lat.values)
    membership = {
        "towers": (list(eq_t), ctrl_t), "fires": (list(eq_f), ctrl_f),
        "floods": (list(eq_fl), ctrl_fl),
        "threeg": (regions[~city].region.tolist(), regions[city].region.tolist()),
    }

    raw = json.load(open(HERE / "data/mbsp_nsw.json"))
    sites = pd.DataFrame([f["attributes"] for f in raw["features"]])
    sites = sites[sites.Site_Status == "Complete"].dropna(subset=["Longitude", "Latitude"])

    coefs = pd.read_csv(HERE / "results/coefficients.csv")
    events = []
    for e in EVENTS:
        touched, control = membership[e["id"]]
        item = {k: v for k, v in e.items() if k != "key"}
        item.update({
            "touched": len(touched), "control": len(control),
            "series": {"speed": series(coefs, e["key"], "log_speed"),
                       "tests": series(coefs, e["key"], "log_tests")},
            "touched_pts": pts(touched), "control_pts": pts(control),
        })
        if e["id"] == "towers":
            item["sites"] = [[round(r.Longitude, 4), round(r.Latitude, 4), r.Location,
                              r.Completion_Date] for r in sites.itertuples()]
        events.append(item)

    outline = json.load(open(ROOT / "docs/data.json"))["outline"]
    out = {
        "id": "o2", "title": "Events that changed the network",
        "question": "What did new towers, the 3G switch-off, fires and floods do to the network?",
        "owner": "Renyu Yang", "status": "done",
        "answer": "Floods and the 3G switch-off left a clear trace. New towers left none "
                  "we can see. The fire comparison failed.",
        "method": "Event study with region and quarter fixed effects: touched "
                  "regions against untouched ones, quarter by quarter, relative to "
                  "the quarter before the event. Bars are 95% intervals. A result "
                  "is only believed if the two groups moved together before the event.",
        "events": events,
        "outline": outline,
        "limits": [
            "Quarterly data misses short outages.",
            "Few regions per event.",
            "Who runs tests changes during events.",
        ],
        "sources": [
            {"name": "Mobile Black Spot Program sites",
             "url": "https://spatial.infrastructure.gov.au/server/rest/services/Mobile_Black_Spot_Program_Funded/MapServer/1"},
            {"name": "NSW Fire Extent and Severity Mapping 2019-20",
             "url": "https://data.gov.au/data/dataset/nsw-fire-extent-and-severity-mapping-fesm-2019-20"},
            {"name": "NSW Reconstruction Authority, Northern Rivers",
             "url": "https://www.nsw.gov.au/departments-and-agencies/nsw-reconstruction-authority/northern-region/northern-rivers/about"},
            {"name": "Department of Infrastructure, 3G switch-offs",
             "url": "https://www.infrastructure.gov.au/department/media/news/3g-network-switch-offs"},
        ],
        "details": "https://github.com/YangRenRR/engg2112-network-decline/tree/main/experiments/events",
    }
    path = ROOT / "docs/o2.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
