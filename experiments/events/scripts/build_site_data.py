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
     "finding": "In the flood quarter the seven Northern Rivers LGAs ran a third "
                "more speed tests than other northern regions. Two quarters later "
                "their median speed was 23% lower. Both were back on track within "
                "about a year.",
     "caveat": "Lismore, the worst-hit LGA, has only six regions and shows "
               "nothing on its own. A quarterly median cannot see the days-long "
               "outages themselves."},
    {"id": "threeg", "key": "3G off, Telstra/Optus 2024 Q4 (rest vs city)",
     "name": "Telstra and Optus 3G switch-off", "when": "2024 Q4",
     "verdict": "clear", "verdict_label": "Clear trace, on an assumption",
     "finding": "Outside the cities, speeds rose 22% and 39% relative to the "
                "cities four and five quarters after the switch-off, with no gap "
                "beforehand.",
     "caveat": "Every region was switched off at once, so non-city regions are "
               "compared with cities on the untested assumption that 3G-only "
               "devices were commoner outside them. Part of the rise may be the "
               "slowest devices leaving the sample, and regional 4G/5G upgrades "
               "in 2025 would look the same."},
    {"id": "towers", "key": "towers, 10 km", "name": "New Mobile Black Spot towers",
     "when": "2020 Q1 - 2025 Q2", "verdict": "none", "verdict_label": "No measurable trace",
     "finding": "No measurable change in speed or test counts within 5, 10 or "
                "20 km of a new tower.",
     "caveat": "This says speed medians cannot see coverage, not that the towers "
               "fail. They are built where there was no signal; their users are "
               "new rather than faster. O5 measures coverage directly."},
    {"id": "fires", "key": "fires 2019-20", "name": "2019-20 bushfires",
     "when": "2019 Q4", "verdict": "failed", "verdict_label": "Comparison failed",
     "finding": "Burnt regions were already moving away from the controls before "
                "the fire season, and changing what counts as burnt flips the "
                "sign of the result.",
     "caveat": "Nothing here measures what the fires did. Burnt areas are mostly "
               "forested ranges with few tests, and the outages lasted days."},
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
        "question": "How did new towers, the 3G switch-off, and the 2019-20 "
                    "bushfires and 2022 floods change measured mobile performance?",
        "owner": "Renyu Yang", "status": "done",
        "answer": "Only two events leave a clear trace in quarterly data: the 2022 "
                  "floods and the Telstra/Optus 3G switch-off. New towers leave none "
                  "that speed medians can see, and the bushfire comparison fails "
                  "its own check.",
        "method": "Event study with region and quarter fixed effects: touched "
                  "regions against untouched ones, quarter by quarter, relative to "
                  "the quarter before the event. Bars are 95% intervals. A result "
                  "is only believed if the two groups moved together before the event.",
        "events": events,
        "outline": outline,
        "limits": [
            "Quarterly medians cannot see outages that last days.",
            "Few touched regions: 22 near towers, 31 burnt, 40 flooded.",
            "Who runs tests changes with events, so a change in median speed is "
            "partly a change in who is measuring.",
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
