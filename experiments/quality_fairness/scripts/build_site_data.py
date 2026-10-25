"""Write docs/o3.json from this experiment's results, in the site's format (docs/README.md)."""
import csv
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


def main():
    rows = list(csv.DictReader(open(HERE / "results/summary.csv")))
    by = {r["ra_group"]: r for r in rows}
    allr = by["All NSW sample"]
    pct = lambda v: f"{float(v):.1f}%" if v not in ("", None) else "-"
    table = [[g, by[g]["eligible_records"], pct(by[g]["assessable_mature_pct"]),
              pct(by[g]["any_metric_pct"]), pct(by[g]["extra_share_of_any_pct"])]
             for g in ("Major Cities", "Inner Regional", "Outer Regional", "Remote", "Very Remote")]
    for name in ("01_patterns.png", "03_assessability.png"):
        shutil.copy(HERE / "figures" / name, ROOT / "docs" / f"o3_{name}")
    out = {
        "id": "o3", "title": "Service quality and fairness",
        "question": "Does a download-only view miss problems, and can remoteness classes be compared?",
        "owner": "Xiangbin Chen", "status": "partial",
        "answer": (f"Download-only misses most of it: {allr['extra_only_n']} of "
                   f"{allr['any_metric_n']} flagged records ({float(allr['extra_share_of_any_pct']):.0f}%) "
                   "worsened only in upload or latency. Outside major cities too few records "
                   "qualify to rank remoteness classes."),
        "method": "Two-quarter deterioration of 20%+ in download, upload or latency, on one common "
                  "set of eligible records; official ABS 2021 remoteness areas.",
        "figures": [
            {"src": "o3_01_patterns.png", "caption": "Which metric flagged each record.",
             "alt": "Counts of records flagged by download, upload, latency and combinations"},
            {"src": "o3_03_assessability.png", "caption": "Share of records with enough data, by remoteness.",
             "alt": "Assessable share of records falling from major cities to very remote"},
        ],
        "tables": [{"title": "By official remoteness",
                    "columns": ["Area", "Eligible records", "Assessable", "Any metric worse", "Missed by download-only"],
                    "rows": table}],
        "limits": ["Grid averages, not household experience.",
                   "Fixed broadband and SEIFA not covered yet.",
                   "Remote has 2 eligible records; Very Remote none."],
        "sources": [{"name": "Ookla Open Data", "url": "https://github.com/teamookla/ookla-open-data"},
                    {"name": "ABS Remoteness Areas 2021",
                     "url": "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/remoteness-structure/remoteness-areas"}],
    }
    (ROOT / "docs/o3.json").write_text(json.dumps(out, separators=(",", ":")))
    print("wrote docs/o3.json")


if __name__ == "__main__":
    main()
