# Protocol recorded before the new outcomes were calculated

Date: 2026-10-26 (Australia/Sydney). Parent repository: ab85d42d99999ba238eb04bc18279e866f110384.

## Scope and questions

Independent re-acquisition of Ookla mobile data, 2019Q1–2026Q1 (29 quarters), plus ABS ASGS 2021 Remoteness Areas (RA). This implements the multi-metric and official-remoteness subset of team objective O3. Fixed-network comparisons, SEIFA extensions, absolute adequacy standards, and new predictive models are outside this experiment. No source or production ranking code is modified.

1. Which persistent upload/latency deteriorations are not covered by a download-only deterioration definition?
2. How do those measured rates differ across the five official remoteness classes, including when comparing the same quarters?
3. How much of the observed sample is not assessable, and why?

## Acquisition and geography

Query published mobile Parquet objects directly; aggregate zoom-16 tiles to zoom-12 quadkey prefixes. Retain all positive-test aggregates, before the main >=50-test eligibility restriction, to audit thin sampling. Record source URLs, object metadata, local content hashes, software versions and failed requests. Fail the full build if any planned quarter is missing. Downloads and cached aggregate CSVs must be distinguishable.

Speed/latency aggregates are test-count-weighted arithmetic means, not medians. A sum of tile device counts is not a unique regional population. Tests are self-selected measurements, not a probability sample of residents.

Read the complete official 2021 RA geometry and reproject points/boundaries correctly. Assign each zoom-12 centre to exactly one polygon. Preserve ambiguous/unmatched cases. Primary geographic sample consists of centres uniquely assigned to NSW RA codes 10–14, with no nearest-polygon substitution. This can exclude coastal/island/border cells and is not a census of NSW land or residents. Use fixed 2021 classifications throughout, including earlier years; this is a retrospective geography, not a point-in-time model feature. Flag cells intersecting multiple remoteness classes for sensitivity analysis.

## Outcomes and denominators

For each baseline quarter t, require t+1 and t+2 exactly, positive finite download/upload/latency in all three quarters, no invalid input tiles, and >=50 tests in each quarter. This common denominator applies to all three outcomes. The last two observed quarters are right-censored, not healthy and not sampling failures.

Using unsmoothed aggregates, flag download or upload if both future values are <=0.80 times the baseline value. Flag latency if both future values are >=1.20 times baseline. Boundaries are inclusive. This is two quarters below/above the same reference, not two consecutive 20% changes. Missing outcomes stay missing, not false.

Primary numerator: eligible records with upload or latency deterioration but no download deterioration. Primary denominator: eligible records with at least one of the three deteriorations. Also report its share of ALL eligible records. Unit: region–baseline-quarter, not independent faults or residents. Overlapping windows can describe the same episode; additionally report distinct regions and contiguous flagged runs.

The 20% cutoffs are exploratory project definitions, not official adequacy or fault standards. Relative change does not measure whether a service was usable in the first place. Averages do not measure individual experience, packet loss, jitter, outages, faults or causal mechanisms.

## Comparisons and robustness

Report all five RA classes with counts and missing categories, even when no outcomes are assessable. Report per-quarter summaries, pooled row-weighted summaries, and equal-quarter standardized rates over quarters represented in all five groups if such quarters exist. Do not fabricate an all-class comparison if there is no common support; report available pairwise contrasts against Major Cities with their own common-quarter counts. Small groups remain visibly small.

Run the same analysis at 15% and 25%, >=100 tests in every quarter, added latency floors of 5 and 10 ms in BOTH future quarters, and excluding mixed-RA cells. Report every planned variant rather than picking the most dramatic result. Quantify uncertainty with region-cluster resampling, retaining each selected region's complete history (1000 draws, fixed seed 2112); this does not address all spatial dependence or sampling bias. A stable descriptive association is not a causal effect.

## Deliverables and verification

Reproducible acquisition and analysis scripts, input hashes, machine-readable record-level results, denominator audit, threshold sensitivity, figures, deterministic examples, unit tests and independent reconciliation of the headline. Keep the actual AI-use log locally under notes/ai_log*.md in line with repository policy, for the school report appendix. Publish a concise method/verification disclosure without private chat text.

The school final report remains a group PDF with <=10 body pages (excluding the stated front matter/references/appendices), a public repository link, objectives/background, full methods, findings/evidence, limitations, end-to-end use, stakeholder/ethics discussion, proposal-to-outcome changes, and substantive AI prompts/outputs/team verification in an appendix. This experiment supplies evidence for that report; it is not the complete final report.
