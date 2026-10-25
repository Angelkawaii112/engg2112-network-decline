# Sources, attribution and data dictionary

## Official sources

1. **Ookla, Global Fixed and Mobile Network Performance Map Tiles**: [data documentation](https://github.com/teamookla/ookla-open-data). Mobile quarterly objects, 2019Q1–2026Q1, accessed 26 October 2026. Exact URLs, source object ETags/Last-Modified metadata, acquisition times, SQL and local hashes are in `provenance/quarters/`. Transformations: zoom-16 to zoom-12 test-weighted aggregation, NSW centroid selection, temporal comparisons and group summaries. Published fields are averages, not medians. Data may be revised after publication.
2. **Australian Bureau of Statistics, ASGS Edition 3, 2021 Remoteness Areas**: [classification](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/remoteness-structure/remoteness-areas), [boundary download page](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files). The GDA2020 GeoPackage archive URL and hash are in `provenance/abs_source.json`. The five classes describe relative access to services, not measured network speed or test frequency. The 2021 geography is held fixed retrospectively; this is not a claim that it is the newest release or a feature available to a historical forecasting model.

## Attribution / reuse

Network inputs are by Ookla. This ENGG2112 analysis of the 2019Q1–2026Q1 mobile data was conducted independently; no endorsement by Ookla is implied. The upstream dataset is distributed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The adapted network data and analytical figures in this experiment retain that non-commercial, attribution and share-alike notice. Preserve the attribution, source links and description of changes when reusing them. This notice does not change any teammate's code or the repository's overall licensing.

ABS material: © Commonwealth of Australia (Australian Bureau of Statistics). ABS's [copyright notice](https://www.abs.gov.au/website-privacy-copyright-and-disclaimer) identifies CC BY 4.0 for its website material, subject to the listed exceptions. We used official statistical geography, not ABS logos, survey forms or confidential microdata. Source geometry is not included in Git; acquisition downloads it from ABS.

## Key fields

The initial query uses zoom-8 prefixes intersecting 141.0–154.0 degrees longitude and -37.6–-28.1 degrees latitude, followed by exact centre matching. This covers the mainland study area but is not an exhaustive NSW territory/island census; grid centres and changing observed sub-tiles are another limit on representativeness.

| Field | Meaning / unit |
| --- | --- |
| `region` | 12-character quadkey string; not SA2, base station or household |
| `year`, `quarter`, `t` | Calendar year, quarter 1–4, and `year*4+quarter` |
| `down_mbps`, `up_mbps` | Test-weighted arithmetic mean speed, Mbps |
| `lat_ms` | Test-weighted mean of `avg_lat_ms`, milliseconds; not jitter or loaded latency |
| `tests` | Sum of source tile tests; eligibility uses >=50 in all three quarters |
| `tile_devices_sum` | Sum of per-tile unique device counts; not unique devices across a region/time, and not people |
| `n_tiles`, `invalid_tiles` | Contributing source tile count and count with null/nonpositive metric or test values |
| `lon`, `lat` | Derived zoom-12 centre, degrees in EPSG:4326 |
| `ra_code`, `ra_group` | Official NSW 2021 remoteness code and short class name |
| `geography_status` | Unique NSW, unique outside NSW, unmatched, or ambiguous |
| `mixed_ra_tile` | Grid footprint has positive-area intersection with more than one class; centroid label retained in primary run |
| `_1`, `_2` suffix | Exact next-quarter / two-quarters-later observations, not next nonmissing rows |
| `status` | Mutually exclusive outcome-assessment status, as defined below |
| `download`, `upload`, `latency` | Nullable Boolean flags; blank = not assessable, not false |
| `any_metric` | Union of the three flags |
| `extra_only` | Upload or latency flagged, download not flagged |
| `pattern` | One of eight disjoint patterns, including `No flagged deterioration`; blank for unassessable rows |
| `*_pct`, `*_ci_*` | Percentages on a 0–100 scale; intervals are region-cluster bootstrap percentiles |
| `*_difference_pp` | Difference in percentage points, not percent relative change |

Status priority: (1) final two baseline quarters `right_censored`; (2) missing exact future quarter `missing_future`; (3) invalid metric/source tile/test value `invalid_metrics`; (4) any quarter below required tests `low_tests`; (5) `mixed_boundary` for that sensitivity only; otherwise `eligible`. A record with several problems is counted once at the first applicable status. "Low tests" totals therefore do not include already missing-future or invalid records.

Common eligible denominator applies to every metric. `extra_share_of_any_pct = extra_only_n / any_metric_n * 100`; `extra_only_pct = extra_only_n / eligible_records * 100`. Do not confuse them. Source tests weight metric aggregation; each eligible grid-quarter has equal weight in pooled outcome rates. Equal-quarter comparisons weight each represented quarter equally, but do not equalize population, geography or sample selection.
