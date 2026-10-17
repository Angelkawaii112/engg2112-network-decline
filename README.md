# Where Will the Network Fail Next?

Forecasting regional mobile network decline in New South Wales to prioritise
network maintenance.

**ENGG2112 · Semester 2, 2026 · TUT05**
Renyu Yang · Jingwei Qiu · Ying Xiao · Xiangbin Chen

---

## Problem

Mobile network maintenance is mostly reactive: faults are fixed after they
appear, and maintenance attention tends to follow population density rather
than need. Regional and remote areas already have weaker coverage, and network
failures matter most during emergencies.

## What we build

A classifier that predicts, for each region, whether median mobile download
speed will fall by more than 20% in the following quarter. Regions are then
ranked by predicted probability to produce a maintenance priority list.

```
Ookla speeds + BoM weather + ABS population
        -> features per region per quarter
        -> Random Forest classifier
        -> probability of significant decline
        -> maintenance priority ranking
```

## Data

| Data | Source | Granularity | Licence |
|---|---|---|---|
| Mobile download/upload speed, latency, tests | [Ookla Open Data](https://github.com/teamookla/ookla-open-data) | Quarterly, ~600 m tile | CC BY-NC-SA 4.0 |
| Temperature, rainfall | [Open-Meteo historical archive](https://open-meteo.com/) | Daily, any coordinate | Open |
| Population | Australian Bureau of Statistics | Annual, by SA2 | Open |

Ookla tiles are available from **2019 Q1 to 2026 Q1** (28 quarters). Files are
queried remotely with DuckDB rather than downloaded in full.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Aggregate one quarter of NSW mobile performance into grid cells
python src/fetch_ookla.py --year 2026 --quarter 1 --out data/nsw_2026Q1.csv

# How often does speed fall by more than 10/20/30% between two quarters?
python src/decline_rate.py --from 2025 4 --to 2026 1

# Build the modelling table: one row per region per quarter, 2019 Q1 to 2026 Q1
python src/build_panel.py --start 2019 1 --end 2026 1 --out data/panel.csv

# Quarterly weather features for every region in the panel
python src/weather.py --panel data/panel.csv --out data/weather.csv

# Train on 2019-2023, test on 2024-2026
python src/model.py --panel data/panel.csv --split 2024 --weather data/weather.csv

# Compare feature sets on the same rows, scored on the ranking they produce
python src/compare.py

# Predict the size of the change instead of a yes/no label
python src/regress.py

# Score the model against a mean-reversion baseline
python src/baselines.py
python src/where_rf_wins.py

# Daily download speeds from Measurement Lab
python src/mlab.py --start 2026-06-01 --end 2026-08-31 --out data/mlab_daily.csv

# Ask the weather and forecasting questions again, a day at a time
python src/daily.py --daily data/mlab_daily.csv

# Everything at once: panel to inspection list
python src/pipeline.py

# Shrink the noisy medians, label lasting declines, and score the ranking
python src/shrink.py --panel data/panel.csv

# Score the ranking one quarter at a time instead of on a single split
python src/walkforward.py --panel data/panel_nsw.csv --start-year 2021

# Does the conclusion survive a different threshold?
python src/sensitivity.py --panel data/panel_nsw.csv

# Who the pipeline keeps, who it drops, and where the inspection budget goes
python src/coverage.py --panel data/panel.csv

# What the device counts add, and the bar external population data must beat
python src/demand.py --panel data/panel.csv

# The four figures the report argues from
python src/figures.py --panel data/panel.csv --out figures

# Rank every region for the next quarter and write the dashboard's input
python src/export_predictions.py --panel data/panel.csv --out ui
```

`panel.csv` is one row per region per quarter:

| region | lon | lat | year | quarter | down_mbps | tests | prev_down_mbps | pct_change | declined |
|---|---|---|---|---|---|---|---|---|---|

`region` is a zoom-12 quadkey prefix, roughly an 8 km cell, standing in for an
ABS SA2 area until the boundary files are wired in. Quadkey prefixes are used
rather than the `tile_x` / `tile_y` columns because those only exist from
2023 Q3 onward, and we need every quarter back to 2019.

## Findings so far

### The 20% threshold is workable

Aggregating NSW tiles into ~11 km cells (a stand-in for SA2), for
2025 Q4 -> 2026 Q1:

| Regions | Fell >10% | Fell >20% | Fell >30% | Median change |
|---|---|---|---|---|
| 142 | 35.9% | **19.7%** | 9.9% | -2.3% |

About one region in five is labelled a significant decline. That is frequent
enough to train on and rare enough to be worth flagging.

### The panel covers 29 quarters and is large enough to model

Building the full table from 2019 Q1 to 2026 Q1 gives:

| Rows | Regions | Quarters | Rows with a previous quarter | Declined |
|---|---|---|---|---|
| 8,873 | 768 | 29 | 7,237 | **14.2%** |

Over the full period 14.2% of region-quarters are labelled a significant
decline, against 19.7% for the single 2025 Q4 to 2026 Q1 transition. The
single-quarter figure was on the high side; 14.2% is the number to design
around.

Coverage also shrinks over time: about 330 regions per quarter in 2020-21
against 240-280 in 2025-26, with total tests roughly halving. Models trained
on older quarters are therefore fitted on denser data than they will see at
prediction time, which is worth stating as a limitation.

### First model results

Trained on 2019-2023 and tested on 2024-2026, predicting whether a region
declines in the **following** quarter:

| | Recall | Precision | Regions flagged |
|---|---|---|---|
| Baseline: never flag anything | 0.00 | – | 0% |
| Baseline: flag every region | 1.00 | 0.125 | 100% |
| **Random forest** | **0.485** | **0.367** | **16.5%** |

The model finds about half the regions that go on to decline, and when it
flags a region it is right roughly a third of the time. Against the base rate
of 12.5% that is close to a threefold improvement in precision, while
inspecting only a sixth of the state.

Neither baseline is usable: never flagging finds nothing, and flagging
everything is the reactive status quo with extra steps. The useful comparison
is the last row against the second, and it says the same budget of
inspections can be aimed about three times better.

The most useful features are the change in speed into the current quarter,
the number of tiles and tests in a region, and the current speed itself.
Weather features have not been added yet.

### A single fitted parameter recovers most of the signal

Our first baseline, assuming next quarter looks like this one, predicts no
change at all and is too weak to learn anything from. The forest's most
useful feature by a wide margin is how far a region sits from its own
long-run level, so the honest comparison is against mean reversion: predict
a fraction of the gap between a region's current speed and its own average,
with that fraction fitted on the training years.

| Predictor | MAE | Average precision | Recall @10% | @15% | @20% |
|---|---|---|---|---|---|
| No change | 0.199 | 0.130 | 2.8% | 8.3% | 13.8% |
| Seasonal average | 0.221 | 0.144 | 15.6% | 18.3% | 22.9% |
| **Mean reversion, one parameter** | 0.194 | **0.368** | **30.3%** | 43.1% | 55.0% |
| Random forest | **0.175** | **0.372** | 30.3% | **46.8%** | **56.9%** |

One line of arithmetic reaches 0.368 average precision against 0.130 for a
random ranking. The forest adds 0.004 on top of that, which is inside the
seed-to-seed noise. Put another way, essentially all of the predictable
structure in this problem, as it was framed here, is mean reversion.

That is not a reason to drop the model, but it is a reason to be precise
about what it buys. The forest improves MAE by 10% and finds 3.7 percentage
points more declining regions within a 15% inspection budget. This framing of
the problem was eventually abandoned for that reason; see the shrinkage
section below.

### The forest earns its keep on the large moves

| Size of the actual change | MAE, mean reversion | MAE, forest | Forest closer |
|---|---|---|---|
| Smallest quarter | 0.036 | 0.087 | 27% |
| Small | 0.091 | 0.104 | 46% |
| Large | 0.182 | 0.170 | 59% |
| **Largest quarter** | **0.466** | **0.338** | **82%** |

On quiet quarters the simple rule is better and the forest over-reacts. On
the largest moves the forest is 27% closer and wins four times out of five.
The gain is concentrated rather than spread thinly, and it sits exactly
where maintenance planning needs it: the regions about to fall a long way.

### Regression and classification are hard to tell apart

| | Average precision | Recall @10% | @15% | @20% | MAE |
|---|---|---|---|---|---|
| Classifier, probability of a >20% drop | **0.394** | **31.2%** | 45.0% | **58.7%** | – |
| Regressor, size of the change | 0.372 | 30.3% | **46.8%** | 56.9% | 0.175 |

The classifier ranks slightly better overall and the regressor finds slightly
more inside a 15% budget; both differences are small enough that the choice
cannot be made on these numbers. It was made on what the output has to say
instead. The regressor drops the arbitrary 20% threshold and keeps the
magnitude, so a region can be reported as "expected to fall 35%" rather than
"0.6 probability of decline". The final system returns to a classifier, because
once the label is a decline that lasts, a probability is the honest thing to
report and the threshold is no longer arbitrary.

### Multi-quarter history helps; weather does not

| Features | Average precision | Recall @15% |
|---|---|---|
| Current quarter only | 0.362 | 44.0% |
| **+ multi-quarter history** | **0.394** | **45.0%** |
| + weather | 0.352 | 42.2% |
| + both | 0.381 | 44.0% |

Four of the seven most useful features are the ones describing how a region
has been moving rather than where it is: its position relative to its own
long-run level, and its change over the last one, two and three quarters. A
region at 50 Mbit/s that fell from 80 and one that climbed from 30 face very
different next quarters, and a snapshot cannot tell them apart.

### Weather adds nothing at this granularity

| | Recall | Precision | Flagged |
|---|---|---|---|
| Without weather | 0.485 | 0.367 | 16.5% |
| With weather | 0.456 | 0.377 | 15.1% |

No weather feature appears in the eight most useful features. Hot days,
heavy rain days and quarterly rainfall totals carry almost no signal about
whether a region's speed will fall next quarter.

This is a result rather than a failure. Weather is fetched per two-degree
cell, roughly 200 km, and summarised to a whole quarter, so a storm that
knocks out a tower for two days is averaged away long before the model sees
it. The proposal assumed weather would matter; at the granularity open data
allows, it does not.

### Measuring before predicting is what made the model useful

Every result above was held back by the same thing. A region's quarterly speed
is the median of however many tests people happened to run there: 59 one
quarter, 206 the next. A 20% decline built from two such numbers is often only
that movement, and mean reversion predicts a bounce better than anything else
can, which is why the forest could only reach 0.372 against its 0.368.

Two changes follow from that diagnosis, both in `src/shrink.py`:

1. **Shrink the speed before using it.** Each quarter's median is pulled toward
   the region's own history, weighted by the number of tests behind it:
   `w = tests / (tests + c)`. The constant `c` is the median test count of the
   training years, 141, so a typical region trusts this quarter and its past
   equally. It is read from the training split and never tuned on the test
   years.
2. **Label a decline only if it lasts.** Down at least 20% next quarter *and*
   still down the quarter after. A crew should not be sent to a cell that
   recovered on its own, and a one-quarter dip is exactly what the baseline is
   good at calling.

On the 2024-2026 test years, with 17 declines among 721 New South Wales
region-quarters:

| method | average precision | recall@10% | recall@15% | recall@20% |
| --- | --- | --- | --- | --- |
| random inspection | 0.024 | 0.100 | 0.150 | 0.200 |
| mean reversion | 0.331 | 0.765 | 0.765 | 1.000 |
| **random forest** | **0.551** | **0.782** | **0.876** | **0.882** |

Inspecting the top 15% finds 88% of the regions that will decline and stay
declined, 5.8 times what inspecting 15% at random would find. The forest's lead
over the baseline widens from 0.004 to 0.220, so the earlier conclusion that
most of the signal was mean reversion was a statement about the noise, not
about the network. The baseline reaches every decline by a 20% budget, which
the forest does not; the model's advantage is concentrated in the tight budgets
where the choice actually costs something.

Three checks, because a jump this size usually means a mistake:

- **The labels describe real declines.** 94% of them also fell at least 20% on
  the unsmoothed numbers, by a median of 37%. Shrinkage removed noise, it did
  not invent a softer target.
- **No trivial rule reproduces it.** Ranking by the most recent change scores
  0.015, ranking by fewest tests 0.025, against the forest's 0.551.
- **The constant is not fitted.** c of 50, 100 and 200 all show the same
  pattern; 125 is the training median rather than the best of those.

The cost is that the test years contain only 17 declines once the label is this
strict and the panel is restricted to New South Wales. The seed-to-seed spread
on average precision is +/-0.017, and the recall figures move by whole
percentage points when a single region changes rank. These are the shape of the
result, not its precise value, and nothing here should be quoted to three
significant figures.

### The system end to end

`src/pipeline.py` runs the whole thing with one command, and its five stages are
the five jobs a deployed version would run on a schedule:

| stage | what it does | when it runs |
| --- | --- | --- |
| collect | read the quarter Ookla published, aggregate tiles into regions, drop everything outside the state | once a quarter, after the release |
| measure | shrink each region's median toward its own history | immediately after, deterministic |
| label | mark the declines that lasted | only for quarters with two quarters after them |
| learn | refit on everything whose outcome is known | each quarter, from scratch |
| rank | score the newest quarter and write the inspection list | each quarter |

The output is `ui/inspection_list.csv`: every region ranked, with an `inspect`
flag marking the 15% a crew would visit. On the current data that is 14 of 94
regions, 71% of them urban and 29% outer suburban.

Refitting from scratch each quarter is cheap here and avoids a stale model
drifting away from the network it describes, but it moves the question of what
to monitor. Accuracy on a fixed test set stops being the useful signal once the
training window keeps sliding. The check that matters is whether this quarter's
ranking resembles last quarter's: a list that reshuffles completely is evidence
that the measurement changed, not that the network did.

The ranking is a priority order for inspection, not a decision. A crew confirms
or dismisses what it finds, and those outcomes are the only labels that
describe real faults rather than movements in a crowdsourced median.

### Congestion proxies already in the data move the number slightly

Ookla reports distinct devices per tile alongside the test count, and neither
had been used. Their ratio is the interesting one: a region running many tests
per device is one where people keep re-testing a connection that is not
satisfying them.

| features | average precision | recall@15% |
| --- | --- | --- |
| current | 0.551 ± 0.017 | 0.876 ± 0.018 |
| plus demand proxies | **0.598** ± 0.012 | 0.882 ± 0.000 |

The gain is about three times the seed noise, and `tests_per_device` is the
eighth most used feature. The point of recording it is
that 0.598 is the figure external population data has to beat, not 0.551.
Census population may still do so, since device counts describe how many Ookla
users a region has now while population growth describes a region expanding
faster than its towers, but the comparison has to be made against this.

### The daily check confirms both quarterly conclusions

A quarter is a long time to average over, so weather could plausibly have been
hidden by it. Measurement Lab publishes individual speed tests with timestamps,
which allows the same two questions to be asked a day at a time. 92 days of
Australian tests were collected, 83,626 tests in total.

Weather still explains nothing. Nothing beats simply predicting the mean:

| model | MAE |
| --- | --- |
| predicting the mean | 7.24 Mbit/s |
| sample size + weekday | 7.48 Mbit/s |
| the same + weather | 7.89 Mbit/s |

The strongest weather correlation is wind speed at +0.197, and its sign is
wrong: higher wind goes with faster speeds. This is noise.

Tomorrow's change is more predictable than next quarter's, but for the same
reason as before:

| model | MAE |
| --- | --- |
| predict no change | 0.140 |
| repeat today | 0.240 |
| mean reversion (k=-0.773) | **0.105** |
| random forest | 0.108 |

The forest loses to a single fitted parameter here, where at quarterly
resolution it won narrowly. With 51 training days it has nothing to learn from.
The fitted k of -0.773 is far stronger than the quarterly 0.07, which suggests
much of the daily movement is sampling noise rebounding rather than real change:
daily test counts range from 177 to 5,152.

This series is Australia-wide rather than per region, so it cannot produce a
maintenance ranking and does not replace the panel. Its value is that the
quarterly conclusions survive a change of data source, time granularity and
target.

### Scored one quarter at a time, the forest and the baseline are a coin flip

The headline above comes from one split, and 17 declines is a thin basis for
any claim. Rolling origin tests it the way the system would be used: for each
quarter in turn, fit on everything whose outcome was known by then, rank that
quarter's regions, and score the ranking. Thirteen quarters could be scored,
holding 43 declines between them.

| | model | mean reversion | random |
| --- | --- | --- | --- |
| average precision | 0.493 | 0.443 | 0.029 |
| quarters won | **7** | 6 | – |
| recall@15% | 0.775 | **0.863** | 0.150 |
| quarters won | 2 | **5** (6 tied) | – |

The forest is marginally ahead on ranking quality and behind on the metric the
system is actually operated by. Neither result is stable: a quarter holds two
to five declines, so one region changing rank moves recall by tens of
percentage points. The single split that produced 0.551 against 0.331 was a
favourable draw rather than a demonstration.

The claim that survives is the one about the system rather than the model. Both
rankings beat random inspection by a wide margin in every quarter scored, which
is what the shrinkage and the lasting-decline label bought. Which ranker sits
inside the system is not something this data can settle, and on that evidence
the one-parameter rule is the better engineering choice: it has nothing to
retrain, nothing to drift, and nothing to explain to whoever inherits it.

The forest earns a place only where it was already shown to: the largest moves,
where it is 27% closer and right four times in five. A deployed version would
reasonably rank with the simple rule and use the forest to flag the regions it
expects to fall furthest.

### The conclusion does not depend on where the threshold was drawn

Two numbers in the label were chosen rather than measured: a 20% fall, and the
requirement that it still be there a quarter later. On a single split the
chosen setting is the one where the forest leads the baseline most widely,
which is exactly the pattern that selective reporting produces, so the sweep
below was run under rolling origin instead.

| threshold | lasting | quarters | declines | AP | baseline | AP won | recall@15% | baseline | recall won |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -15% | yes | 18 | 98 | 0.408 | 0.386 | 9/18 | 0.660 | 0.683 | 7/18 |
| -20% | yes | 13 | 43 | 0.488 | 0.443 | 8/13 | 0.796 | 0.863 | 1/13 |
| -25% | yes | 7 | 18 | 0.660 | 0.409 | 5/7 | 0.810 | 0.929 | 0/7 |
| -15% | no | 20 | 285 | 0.438 | 0.419 | 12/20 | 0.487 | 0.476 | 11/20 |
| -20% | no | 19 | 137 | 0.421 | 0.398 | 9/19 | 0.578 | 0.630 | 4/19 |
| -25% | no | 17 | 72 | 0.437 | 0.424 | 9/17 | 0.618 | 0.711 | 4/17 |

The same thing happens in every row. The forest ranks slightly better on
average precision and finds slightly fewer declines inside the budget, and
neither margin is large. The threshold decides how many events exist to be
found, not which ranker to prefer, and the headline is not an artefact of
where the line was drawn.

The bottom row is the most informative one despite being the least dramatic.
Relaxing the label to a 15% fall with no persistence requirement produces 285
declines across 20 quarters, six times the evidence, and there the two methods
are closest of all. The configurations that make the forest look best are the
ones with the fewest events to be right about.

### The system excludes regional New South Wales before it predicts anything

The earlier version of this section reported a recall of 0.00 across ten
regional areas and read as a model that performed badly there. Re-measuring it
under the current method showed something worse, and more structural: regional
areas are not predicted badly, they are dropped.

| region-quarters surviving | urban | outer | regional |
| --- | --- | --- | --- |
| in the panel | 3,030 | 1,452 | 603 |
| has every feature | 2,585 | 678 | 86 |
| outcome also known | 2,366 | 528 | **39** |

94% of regional region-quarters are gone before training starts, and the
2024-2026 test window contains none at all. The cause is visible in what each
kind of area can supply:

| | urban | outer | regional |
| --- | --- | --- | --- |
| regions | 152 | 150 | 153 |
| median tests per quarter | 231 | 79 | **60** |
| median quarters observed per region | 29 | 7 | **1** |
| share of rows missing a feature | 15% | 53% | **86%** |

The lag features need four quarters of history. The median regional region has
one quarter in the panel at all. There are as many regional regions as urban
ones; they simply cannot be seen.

This is self-reinforcing, and the loop is the finding rather than a caveat on
it. Ookla records a tile when somebody runs a speed test, so few users produce
few tests, few tests produce sparse history, sparse history excludes the region
from the model, exclusion keeps it out of the maintenance ranking, and service
there stays as it was. A system built to direct maintenance would, used
unchanged, direct it exclusively to the places already best served: at a 15%
budget, 80% of inspections go to urban regions and 20% to outer suburban ones.

The ranking should therefore be presented as covering urban and outer-suburban
New South Wales only, with regional areas handled by scheduled inspection
rather than by this model. Stating the coverage is not a disclaimer; a ranking
that silently omits a third of the state would misdirect the budget it exists
to allocate.

### The model fails where it matters most

| Area type | Regions | Base rate | Recall | Precision | Flagged |
|---|---|---|---|---|---|
| Urban | 185 | 11.3% | 0.462 | 0.400 | 13.1% |
| Outer | 54 | 20.9% | 0.442 | 0.322 | 28.6% |
| **Regional** | **10** | **5.9%** | **0.000** | **0.000** | 17.6% |

Bands are set by each region's median number of speed tests, standing in for
population until ABS figures are joined.

The regional band contains ten regions and seventeen labelled rows, and the
model catches none of their declines. This is the equity problem the proposal
predicted, measured: speed tests are run by people who choose to run them, so
sparsely populated areas produce too little data to model, and those are the
areas with the weakest coverage to begin with. Any deployment would have to
flag these regions for human review rather than trust a prediction, and a
single average score would have hidden this entirely.

### Predicting the current quarter is not a task

A first version scored perfect accuracy, which was the bug announcing itself.
The label is derived from `pct_change`, and `pct_change` was also a feature,
so the model was reading the answer rather than predicting it.

The target is now the **following** quarter's decline, and performance fell to
the numbers above. This is worth recording because the proposal did not
distinguish between describing a decline that has already happened and
forecasting one that has not.

### Aggregation is required, not optional

At the raw 600 m tile level, very few tiles have data in **both** quarters,
because a tile only appears when someone runs a speed test there:

| Minimum tests per tile | Tiles matched across both quarters |
|---|---|
| 10 | 481 |
| 30 | 86 |

86 samples cannot train a model. Aggregating to region level raises this to
142 stable regions, each with at least 50 tests in both quarters. This changed
our plan from tile-level to region-level modelling.

## Status

- [x] Confirm data availability and licence
- [x] Measure the base rate of decline at several thresholds
- [x] Build the region-quarter panel for 2019 Q1 to 2026 Q1
- [ ] Replace the coarse grid with a spatial join on ABS SA2 boundaries
- [x] Add quarterly weather features (Open-Meteo, in place of BoM)
- [x] Baselines and a first random forest, validated by time
- [x] Report recall separately for urban, outer suburban and regional areas
- [x] Evaluate against an inspection budget rather than a fixed threshold
- [x] Test the model against a mean-reversion baseline
- [x] Daily-resolution check of the weather question using M-Lab
- [ ] Variable region size so sparse areas have enough data to model
- [x] Produce the maintenance priority ranking

## Notes

Speed data reflects users who choose to run a test, so coverage is uneven.
Regions with few tests are flagged rather than ranked.
