# E1 results — NSW 2026 4G outdoor coverage gap

**Coverage-map reference date:** 31 January 2026  
**Run provenance:** The figures below were reported from the team's generated E1 outputs on 26 October 2026. The generated raster/vector files are not copied into this documentation update; check them in outputs/generated before final publication. This follow-up patch also does not include the helper-script source; confirm the team versions of prepare_coverage_stream.py and summarize_gap_raster.py are in the repository before asking others to reproduce the run.

## Main results

| Measure | Result | Interpretation |
|---|---:|---|
| Area outside all three predicted 4G outdoor coverage maps | 248,000 km² (31% of NSW) | Map-model gap, not a field measurement of signal at every point. |
| Modelled residents in the gap | 22,611 (0.27% of NSW population) | Based on the modelled population grid. |
| Selected State/Regional road length in the gap | 3,572 km (8.7% of the selected road network) | Local roads are not included in this road total. |
| Geocoded hospitals in the gap | 4 of 382 | Based on the geocoded reporting units used in E1. |
| Very Remote residents estimated in the gap | 14.5% | Share of residents in the Very Remote category. |
| Remote/Outer Regional residents estimated in the gap | 3.5% | The supplied result groups these categories; confirm whether this is combined or category-specific against population_by_remoteness.csv before publishing separately. |

## Interpretation

The mapped gap occupies a much larger share of NSW land and selected road kilometres than of the modelled population. This supports describing the main exposure as an outdoor route-continuity problem, alongside a smaller but real residential-access issue. It does not mean that no households are affected: 22,611 modelled residents are in the gap, and four geocoded hospitals are also located there.

The ACCC operator maps are predictions of outdoor coverage, not measurements at every location. The E1 result means a location falls outside all three supplied mapped layers; it does not prove that a handset will never receive a signal there.

## Method and robustness notes from the team rerun

- The Optus coverage source is about 1.3 GB. The team rerun used scripts/prepare_coverage_stream.py to read it incrementally after GDAL could not read the full source successfully.
- Dissolving roughly one million small polygons took hours. The rerun used scripts/summarize_gap_raster.py with a 100 m raster grid, producing the summary in minutes. The population, road and hospital decision rules were reported to match the earlier workflow.
- The remoteness field is RA_NAME_2021. Do not assume the older RA_NAME21 field name.
- A separate Optus–TPG MOCN shared-network map check produced the same reported results when added. Treat this as a robustness check; do not count MOCN as a fourth independent operator or add another gap reduction.
- The E1 totals use the ACCC map reference date above and selected State/Regional roads only. Recheck the output CSVs and map layers before presenting more detailed area or remoteness breakdowns.

See data/sources.yml for the public source links, map dates and data-handling notes.

