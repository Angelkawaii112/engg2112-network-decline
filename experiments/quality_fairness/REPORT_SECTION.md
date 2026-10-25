# Draft report section: multi-metric quality and remoteness

This is a contribution for team review, not the completed group report. Check figures, references and wording before inclusion. It addresses only the mobile multi-metric / official-remoteness part of O3.

## Question and method

We investigated whether a download-only deterioration definition overlooks sustained upload or latency changes, and whether the available observations support comparisons by official remoteness. This complements the project's prediction objective with a retrospective measurement audit; it does not evaluate a new predictive model.

We independently queried 29 quarters of Ookla mobile tiles (2019Q1–2026Q1), aggregated zoom-16 tiles into zoom-12 grids using test-count-weighted means, and matched each grid centre to the ABS 2021 Remoteness Areas. These are average speeds and latency, not medians or household measurements. The fixed 2021 geography supports consistent retrospective grouping but does not reconstruct historical classifications. Source URLs, queries, hashes and software versions were recorded.

A baseline record was eligible only when that quarter and the following two consecutive quarters contained valid positive download, upload and latency measurements, no invalid source tiles, and at least 50 tests each. The same denominator was used for all three metrics. Download or upload deterioration required both future values to be at least 20% below the same baseline; latency deterioration required both to be at least 20% above it. Missing and insufficient observations remained unknown. The final two quarters were right-censored. These exploratory thresholds are not official adequacy standards.

## Findings

Centroid matching retained 37,449 observed NSW grid-quarter records across 4,443 grids. Of these, 3,145 baseline records across 184 grids were eligible. Download deterioration occurred in 178 records. Upload or latency deterioration without download deterioration occurred in another 259 records: 141 upload-only, 95 latency-only and 23 involving both. Thus, these additional patterns represented 59.27% of the 437 records flagged by any metric, or 8.24% of all eligible records (Figure 1). The region-cluster bootstrap 95% interval for the additional share was 55.21%–63.17% (1,000 resamples). The 259 records occurred in 125 grids and 242 contiguous flagged runs; neither records nor runs establish independent faults.

Assessability differed sharply between groups (Figure 2). Among observed mature baseline records, 77.37% qualified in Major Cities, compared with 6.87% in Inner Regional, 0.80% in Outer Regional, 0.11% in Remote and none in Very Remote areas. These percentages are not population or network coverage. Remote had only two eligible records from one grid, preventing a reliable five-group ranking. Over 27 common quarters, equal-quarter upload/latency-only rates were 10.09% in Inner Regional and 7.27% in Major Cities. This descriptive difference does not identify a causal remoteness effect.

Six pre-specified sensitivity analyses changed the relative threshold, test requirement, absolute latency increase or mixed-boundary inclusion. Additional patterns remained 51.23%–63.40% of flagged records. This supports the relevance of multiple metrics within the measured sample, but does not establish external validity.

## Implications and limitations

An operational extension could combine quarterly multi-metric flags and data-confidence indicators with the team's predictive output. Operators would first review the evidence, obtain further measurements where data are insufficient, and confirm issues before allocating maintenance. This workflow is proposed, not deployed or validated. The retrospective flags require two future quarters and must not be described as real-time forecasts.

Crowdsourced tests are self-selected; grid averages and changing device or within-grid sampling mixes can obscure individual experience. Relative deterioration also misses persistently poor but stable service. Geographic matching excludes unmatched centres and may misrepresent mixed cells. Bootstrap intervals retain within-grid histories but do not resolve between-grid spatial dependence or selection bias. Consequently, results cannot establish carrier faults, household usability or a monotonic rural disadvantage. For equitable deployment, missing-data regions should receive measurement attention rather than be classified as healthy or denied resources. Human review, transparent uncertainty, aggregate-only publication and monitoring of data drift are essential safeguards.

## Figure / source pointers (outside the draft prose)

- Figure 1: `figures/01_patterns.pdf`; record counts: `results/pattern_counts.csv` and `results/summary.csv`.
- Figure 2: `figures/03_assessability.pdf`; denominator audit: `results/summary.csv`.
- Same-quarter estimate: `results/equal_quarter_pairwise.csv`; robustness: `results/sensitivity.csv`.
- Sources: [Ookla documentation](https://github.com/teamookla/ookla-open-data); [ABS RA2021](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/remoteness-structure/remoteness-areas). Add full bibliography entries in the team's chosen citation style.
