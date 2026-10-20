# Population growth experiment

Population growth **did not improve Average Precision (AP)** in this NSW
experiment. This contribution adds independent scripts and small results only;
it does not replace the project baseline or deployed model.

All values below are mean +/- population SD (`ddof=0`) over seeds 0–9.
The population experiment used **scikit-learn 1.9.1** throughout.

| Protocol (sklearn 1.9.1) | Features | AP | Recall@15% |
|---|---|---:|---:|
| Original | Devices baseline | 0.629994 +/- 0.009771 | 0.876471 +/- 0.017647 |
| Original | + population growth | 0.617377 +/- 0.005563 | 0.882353 +/- 0.000000 |
| Original | Availability control | 0.622936 +/- 0.008607 | 0.882353 +/- 0.000000 |
| Horizon-purged | Devices baseline | 0.483340 +/- 0.010577 | 0.764706 +/- 0.000000 |
| Horizon-purged | + population growth | 0.481736 +/- 0.010034 | 0.764706 +/- 0.000000 |
| Horizon-purged | Availability control | 0.482735 +/- 0.013311 | 0.764706 +/- 0.000000 |

Growth changed AP by -0.012618 in the original protocol and -0.001604 after
purging. Seed variation measures model randomness on one fixed test set;
it does not measure population sampling uncertainty or a causal congestion effect.

The unchanged `src/demand.py` scoring function uses 400 trees, minimum leaf size
5, balanced class weights, the -99 missing sentinel, and all 25 existing
network/history/demand features including `devices`. Growth adds one column;
the availability control instead adds its observed/missing indicator. Labels use
the unchanged `shrink.add_persistent`: speed is at least 20% lower in both next
consecutive quarters, with a shrinkage constant of 125 tests.

Training feature years are before 2024; testing begins in 2024. Both protocols
share the same 721 test rows and 17 positives. Recall uses a pooled top-15%
ranking: `round(0.15 * 721) = 108` rows. Horizon purging requires
`t + 2 < first_test_t`, where `t = 4 * year + quarter`. It removes 234 eligible
2023 Q3/Q4 training rows (7 positives), reducing training from 2,212 to 1,978
rows and from 33 to 26 positives. See `results/removed_training_by_quarter.csv`.
**Purging reduced AP, but the decrease cannot be attributed entirely to temporal
leakage because training samples were removed.** Training size, recency,
composition and the resulting numeric balanced class weights also changed.
No matched-size ablation was performed. Exact historical Ookla publication
timestamps are not reconstructed; this is a quarter-level horizon audit.

Quadkey centres are intersected with ASGS 2021 NSW SA2 polygons. Annual growth
is `(ERP_current - ERP_previous) / ERP_previous`, using both values from the
same historical release. Each feature quarter uses only vintages published by
quarter end; revisions are not backfilled. Compatible releases start in July
2022, leaving earlier features missing. Undefined growth and unmatched centres
remain missing, with no invented values. 408/455 centres (89.7%) match uniquely;
panel-row coverage is 87.1%. Growth is observed for 622/2,212 original training
rows, 423/1,978 purged training rows and 637/721 test rows. Missing rows remain
in both models. History features update using observed earlier test quarters,
as in the upstream pipeline.

## scikit-learn version investigation

| Environment, original devices baseline | AP mean +/- SD | Recall@15% mean |
|---|---:|---:|
| scikit-learn 1.9.1 | 0.629994 +/- 0.009771 | 0.876471 |
| scikit-learn 1.6.1, other dependencies held fixed | 0.597593 +/- 0.012702 | 0.882353 |
| scikit-learn 1.9.1, diagnostic uniform bootstrap/weighted fit | 0.596566 +/- 0.011344 | 0.882353 |

Thus AP **0.630 with 1.9.1 versus approximately 0.598 with 1.6.1** is an
environment difference on the same data, rows and scoring code. The recorded
training matrix hash is identical across versions (in
`provenance/environment_1.6.1.json`). The 1.6.1 mean rounds to the published
0.598, but its SD rounds to 0.013 rather than the published 0.012. This does
not establish the authors' exact environment or reproduce every statistic.
No population-enhanced 1.6.1 result is claimed.

Local source inspection found that the installed 1.9.1 build incorporates class
weights in bootstrap sampling; 1.6.1 samples uniformly and applies weights during
tree fitting. An in-memory bootstrap intervention in 1.9.1 explains most of the
gap. The diagnostic is isolated to its own process, restores its temporary
function replacement, and never edits installed packages or upstream models.
`results/bootstrap_1.9.1_per_seed.csv` labels intervention modes explicitly.
Archived CSVs identify their scikit-learn version; do not pool environments.

## Reproduce

Run from this directory, in a checkout retaining the upstream files recorded at
commit `336619e9dc6f43e94691f64fcc7ca2d182b93b04`. Scripts hash-check upstream
sources and fail if they change. They only write to ignored `work/` paths.
The recorded environment was Windows, Python 3.13.3. Use separate virtual
environments for each lock file; no global package installation is needed.

```powershell
python -m venv .venv-1.9.1
.\.venv-1.9.1\Scripts\python.exe -m pip install -r requirements-1.9.1.txt
.\.venv-1.9.1\Scripts\python.exe scripts/inspect_abs.py
.\.venv-1.9.1\Scripts\python.exe scripts/download_abs.py
.\.venv-1.9.1\Scripts\python.exe scripts/rebuild_panel.py --workers 3
.\.venv-1.9.1\Scripts\python.exe scripts/prepare_population.py
.\.venv-1.9.1\Scripts\python.exe scripts/validate_inputs.py
.\.venv-1.9.1\Scripts\python.exe scripts/test_experiment.py
.\.venv-1.9.1\Scripts\python.exe scripts/evaluate.py
.\.venv-1.9.1\Scripts\python.exe scripts/baseline_version.py
.\.venv-1.9.1\Scripts\python.exe scripts/diagnose_bootstrap.py
.\.venv-1.9.1\Scripts\python.exe scripts/verify_results.py

python -m venv .venv-1.6.1
.\.venv-1.6.1\Scripts\python.exe -m pip install -r requirements-1.6.1.txt
.\.venv-1.6.1\Scripts\python.exe scripts/baseline_version.py --panel work/sklearn-1.9.1/data/network/panel_nsw.csv
```

On other systems use the corresponding virtual environment Python path.
Generated outputs live in `work/sklearn-<version>/results/`; the committed
`results/` directory is never overwritten. Baseline-only runs in the two
environments should have the same training-matrix hash. The older recorded run
used an isolated package directory over the primary environment; the separate
lock holds all other package versions fixed for reproduction.

Network rebuilding reuses the original aggregation, zoom 12, minimum 50 tests,
2019 Q1–2026 Q1 inclusive, and existing NSW state filter. Quarter caches are
resumable. The 29 remote global parquet files total approximately 5.68 GB;
allow 10–15 GB free space and roughly an hour depending on network and hardware.
DuckDB downloads its `httpfs` extension into the experiment cache. All quarters
must be present; incomplete builds fail.

External sources are public: [Ookla mobile performance data](https://github.com/teamookla/ookla-open-data),
ABS [2021 ERP](https://www.abs.gov.au/statistics/people/population/regional-population/2021),
[2022 ERP](https://www.abs.gov.au/statistics/people/population/regional-population/2021-22),
[2023 ERP](https://www.abs.gov.au/statistics/people/population/regional-population/2022-23),
[2024 ERP](https://www.abs.gov.au/statistics/people/population/regional-population/2023-24),
and [ASGS 2021 boundaries](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files).
`provenance/abs_sources.json` gives exact download URLs, release dates, sizes and
SHA-256 hashes, including the August 2023 revision. The downloader rejects changed
ABS bytes. `inspect_abs.py` fetches publication evidence required by feature
preparation. The latest age/sex page is inspected for context, not used as input.

`provenance/input_hashes.json` records the local input snapshot; fresh network
aggregates can differ in row order or provider revisions. Check row counts,
labels, matrix hashes and metrics before claiming an exact replay. Historical
provider revisions may prevent bit-for-bit reproduction. Full source downloads
were not repeated for contribution packaging; archived inputs were used for
local validation. Packaging validation reproduced all 60 model/seed AP and recall
pairs using those inputs, passed the temporal integrity and SA2-code checks, and
confirmed availability of all 40 checked public source URLs on 21 October 2026.
The older package and bootstrap intervention were not rerun during packaging;
their CSVs preserve the completed investigation. No raw datasets, workbook archives, environments or caches
are included. Ookla attribution/licence: CC BY-NC-SA 4.0; ABS attribution:
Australian Bureau of Statistics, historical regional ERP and ASGS 2021.
