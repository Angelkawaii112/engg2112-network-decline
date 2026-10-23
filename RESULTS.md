# Results

All measured results for O1, in full. The [README](README.md) has the summary;
[PLAN.md](PLAN.md) has the objectives and who is doing what. Every figure here
is re-derived by `src/verify_claims.py`.

Sections are grouped by what they show, current results first. The last part,
*Earlier framing*, is the record of a version of the problem this project
abandoned; its numbers come from a single-quarter label and are kept to show
how the method changed, not as current results.

## How far these evaluations can be trusted

Three limits apply to every figure below and are stated once here rather than
repeated.

**The evidence is thin.** The single split has 17 lasting declines; rolling
origin has 43 across 13 quarters, two to five in each. One region changing rank
moves a quarter's recall by tens of percentage points. Figures are given to
three decimals for reproducibility, not because the third decimal means
anything.

**The test years were looked at many times.** Weather, neighbours, national
adjustment, device and population features, five model families, six label
thresholds and four horizons were all scored on the same 2021–2026 quarters,
and decisions were made from those scores. That is model selection on the test
period. The results are an evaluation of the methods on the data available, not
an independent final validation; a quarter Ookla has not yet published is the
only test this project could not have tuned against.

**The labels are measured performance, not confirmed faults.** A lasting decline
is a lasting drop in a crowdsourced median. Upload falling with download in 86%
of cases argues that most are real changes in the link, but a quarter of them
coincide with the number of tests halving, and nothing here can separate a
degraded cell from a thinner sample of it. Only an on-site inspection turns a
flagged region into a fault, and only those inspection outcomes could train a
model on faults rather than on medians.

## How the proposal became this

Each row is one change from the proposal, the problem that forced it, and where
the evidence sits.

| Plan | Problem found | Change | Evidence |
| --- | --- | --- | --- |
| Model individual ~600 m tiles | Only 481 tiles appear in two consecutive quarters; 86 with 30+ tests | Aggregate to ~8 km regions | [Aggregation is required](#aggregation-is-required-not-optional) |
| Cut NSW out with a bounding box | 313 of 768 regions were in Victoria, Queensland, SA or the ACT; the first ranking's top region was near Melbourne | Point-in-polygon against the state boundary | [boundary.py](src/boundary.py) |
| Predict a >20% fall next quarter | Most such falls are sampling noise; the forest could not beat a one-parameter rule | Shrink each region toward its own history; label only falls that last | [Measuring before predicting](#measuring-before-predicting-is-what-made-the-model-useful) |
| Weather as a driver (BoM) | BoM blocks automated access; Open-Meteo weather adds nothing, quarterly or daily | Dropped | [Weather adds nothing](#weather-adds-nothing-at-this-granularity), [daily check](#the-daily-check-confirms-both-quarterly-conclusions) |
| Population as a driver (ABS) | Growth adds nothing; device growth is identical in declining and other regions | Dropped | [Census population](#census-population-growth-does-not-help-either) |
| Random forest as the model | Under rolling origin it trails the simple rule inside a 15% budget, at every threshold tested | Rule ranks; forest flags steep falls and predicts recovery | [Two rankers](#two-rankers-and-the-simpler-one-ships) |
| One train/test split | 17 events; training rows were labelled with test-period data | Purged rolling origin is the evaluation of record | [Purging](#the-training-set-was-leaking-into-the-test-years) |
| Serve regional NSW | 94% of regional region-quarters lack the history the method needs | Coverage stated as urban and outer-suburban; regional left to scheduled inspection | [Coverage](#the-system-excludes-regional-new-south-wales-before-it-predicts-anything) |

## How the model works

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
region-quarters and 1,978 training rows after purging:

| method | average precision | recall@10% | recall@15% | recall@20% |
| --- | --- | --- | --- | --- |
| random inspection | 0.024 | 0.100 | 0.150 | 0.200 |
| mean reversion | 0.331 | 0.765 | 0.765 | 1.000 |
| **random forest** | **0.436** | 0.759 | 0.765 | 0.788 |

Inspecting the top 15% finds 77% of the regions that will decline and stay
declined, 5.1 times what inspecting 15% at random would find. The forest leads
the baseline on average precision, 0.436 to 0.331, and matches it on recall
inside the budget while the baseline reaches every decline by a 20% budget.

These numbers were higher before a teammate found that the training set was
leaking; see the purging section below. The earlier conclusion that most of the
signal was mean reversion was still a statement about the noise rather than the
network, but the margin is narrower than this section first claimed.

Three checks, because a jump this size usually means a mistake:

- **The labels describe real declines.** 94% of them also fell at least 20% on
  the unsmoothed numbers, by a median of 37%. Shrinkage removed noise, it did
  not invent a softer target.
- **No trivial rule reproduces it.** Ranking by the most recent change scores
  0.015, ranking by fewest tests 0.025, against the forest's 0.436.
- **The constant is not fitted.** c of 50, 100 and 200 all show the same
  pattern; 125 is the training median rather than the best of those.

The cost is that the test years contain only 17 declines once the label is this
strict and the panel is restricted to New South Wales. The seed-to-seed spread
on average precision is +/-0.014, and the recall figures move by whole
percentage points when a single region changes rank. These are the shape of the
result, not its precise value, and nothing here should be quoted to three
significant figures.

### The training set was leaking into the test years

A row's label is built from the two quarters after it. A row from 2023 Q3 is
therefore labelled using 2024 Q1, which is a quarter the model was about to be
tested on. Splitting the data by the year of the features, as every evaluation
here did at first, leaves 234 such rows in the training set: all of 2023 Q3 and
Q4, and the most recent and most informative rows there are.

A teammate found this while reproducing the figures. Purging them, which is the
standard correction in time-series cross-validation, costs a fifth of the
headline:

| training set | average precision | recall@15% | rows |
| --- | --- | --- | --- |
| as first published | 0.551 | 0.876 | 2,212 |
| **purged** | **0.436** | **0.765** | 1,978 |
| control: 234 random rows removed | 0.536 | 0.876 | 1,978 |

The control answers the question the purge leaves open. Removing 234 rows at
random costs 0.015; removing the 234 leaking ones costs 0.115. Seven eighths of
the drop is the leak rather than the smaller training set.

Rolling origin barely moved, 0.491 to 0.486, and that contrast is the useful
part. Each quarter's rolling fit leaks only its last two rows out of nearly two
thousand, while the single split leaked its most recent and most relevant tenth.
The evaluation this project had already come to trust turned out to be the one
that did not need rescuing.

Every figure in this README is now measured with purging applied, and
`shrink.purge` is called by every script that builds a training set.

One related thing was checked and deliberately left alone. The urban, outer and
regional bands are cut from the whole panel rather than the training years, so
they are assigned with hindsight, which is the same kind of mistake. It is not
one: `area_type` is never a model feature, only a way of grouping results.
Recutting the bands on training years alone leaves the finding that matters
unchanged, regional areas keeping 6% of their region-quarters either way
against 78% and 79% for urban, while leaving 73 rows unlabelled because some
regions appear only in the test years. The hindsight is recorded rather than
traded for missing data.

### Scored one quarter at a time, the forest and the baseline are a coin flip

The headline above comes from one split, and 17 declines is a thin basis for
any claim. Rolling origin tests it the way the system would be used: for each
quarter in turn, fit on everything whose outcome was known by then, rank that
quarter's regions, and score the ranking. Thirteen quarters could be scored,
holding 43 declines between them.

| | model | mean reversion | random |
| --- | --- | --- | --- |
| average precision | 0.486 | 0.443 | 0.029 |
| quarters won | **7** | 6 | – |
| recall@15% | 0.811 | **0.863** | 0.150 |
| quarters won | 3 | **4** (6 tied) | – |

The forest is marginally ahead on ranking quality and behind on the metric the
system is actually operated by. Neither result is stable: a quarter holds two
to five declines, so one region changing rank moves recall by tens of
percentage points.

Rolling origin barely moved when the purge was applied, 0.491 to 0.486, because
each quarter's training set leaks only its final two rows out of nearly two
thousand. The single split lost a fifth of its score to the same correction,
because the rows it was leaking were the most recent and most informative ones.
That is a second reason to have distrusted it.

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
| -15% | yes | 18 | 98 | 0.384 | **0.386** | 8/18 | 0.625 | 0.683 | 7/18 |
| -20% | yes | 13 | 43 | **0.489** | 0.443 | 7/13 | 0.814 | 0.863 | 2/13 |
| -25% | yes | 7 | 18 | **0.673** | 0.409 | 5/7 | 0.833 | 0.929 | 0/7 |
| -15% | no | 19 | 281 | **0.429** | 0.426 | 11/19 | 0.460 | 0.475 | 6/19 |
| -20% | no | 18 | 134 | **0.420** | 0.402 | 8/18 | 0.554 | 0.628 | 3/18 |
| -25% | no | 16 | 70 | 0.420 | **0.443** | 9/16 | 0.594 | 0.724 | 2/16 |

The same thing happens in every row. The forest ranks better on average
precision in four rows of six and worse in two, finds fewer declines inside the
budget in all six, and no margin is large. The threshold decides how many events exist to be
found, not which ranker to prefer, and the headline is not an artefact of
where the line was drawn.

The bottom rows are the most informative despite being the least dramatic.
Relaxing the label to a 15% fall with no persistence requirement produces 281
declines across 19 quarters, six times the evidence, and there the two methods
are closest of all. The configurations that make the forest look best are the
ones with the fewest events to be right about.

### Two rankers, and the simpler one ships

The evaluation could not separate the forest from the one-parameter rule: ahead
on average precision, behind on recall inside the budget, in every threshold
tested. When the evidence does not favour the more complicated thing, the
simpler thing wins. `src/rankers.py` holds both behind one interface, and the
pipeline deploys mean reversion by default. It has one fitted number, cannot
drift, retrains in microseconds, and fits in a sentence an operations team can
check.

Five other ways of training were tried before settling on that, scored the
same way, purged rolling origin over 13 quarters and 43 lasting declines:

| method | AP | recall@10% | recall@15% | vs rule at 15%, by quarter |
| --- | --- | --- | --- | --- |
| **simple rule** | 0.443 | 0.585 | **0.863** | – |
| random forest | 0.492 | **0.801** | 0.801 | 1 won, 4 lost |
| gradient boosting | 0.448 | 0.544 | 0.745 | 1 won, 6 lost |
| logistic, all features | 0.436 | 0.664 | 0.819 | 1 won, 3 lost |
| logistic, rule + 2 terms | 0.305 | 0.456 | 0.635 | 0 won, 7 lost |
| blend of rule and forest ranks | **0.502** | 0.778 | 0.847 | 1 won, 2 lost |

None finds more lasting declines than the rule inside a 15% budget. At a 10%
budget the forest finds far more, 0.80 against 0.59. So the right ranker
depends on how many regions can be visited: the forest when only a handful can,
the rule at 15% and above. That is the cost analysis's conclusion reached from
the other side, and the site's cost slider is how a user would choose between
them.

The forest is kept for the one thing it was shown to do better. On the largest
moves it is 27% closer than the simple rule and right four times in five, so
the inspection list is ordered by mean reversion and carries a
`steep_fall_expected` flag from the forest. The order says where to go first;
the flag says where the fall is likely to be severe.

### Priced as a decision, the cheap ranker wins where the stakes are high

This repository kept saying the model's value depends on what an unnecessary
inspection costs, and then not pricing it. The prices are not public, but the
decision depends only on their ratio, and a ratio can be swept.

Let R be the cost of missing a lasting decline divided by the cost of one
inspection. Inspecting the top k regions costs k and leaves whatever it misses,
so a budget's expected cost is `k + R x (declines missed)`, in units of one
inspection. Scored under rolling origin, on quarters averaging 116 regions and
3.3 lasting declines:

| R | do nothing | forest budget | cost | baseline budget | cost | cheaper | saving |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 6.6 | 1% | 6.4 | 0% | 6.6 | forest | 3% |
| 5 | 16.5 | 4% | 11.6 | 5% | 12.8 | forest | 30% |
| 10 | 33.1 | 10% | 18.5 | 5% | 19.8 | forest | 44% |
| 20 | 66.2 | 11% | 25.2 | 14% | **24.0** | **baseline** | 64% |
| 50 | 165.4 | 11% | 43.6 | 14% | **35.5** | **baseline** | 79% |
| 100 | 330.8 | 32% | 60.3 | 25% | **44.5** | **baseline** | 87% |

Three things follow, and none of them is a statement about accuracy.

**Inspecting something beats inspecting nothing from R = 2 upward.** The
ranking does not have to be good for the system to pay; it has to be better
than arbitrary, and it is.

**The right budget depends on the price, not on the model.** At R = 5 the
cheapest policy inspects 4-5% of regions. At R = 50 it inspects 11-14%. A fixed
15% budget, used throughout this repository for comparability, is close to
optimal only near R = 20.

**The baseline is cheaper wherever the stakes are high.** At R of 20 and above
the one-parameter rule costs less than the forest at each one's own best
budget, by 23%, 28% and 16%. The forest's narrow lead at low R is where the
decision matters least, since little is being spent either way. This is the
recall result again, in the units an operator would actually argue about, and
it is why the pipeline ships the simple ranker.

The 68% self-recovery rate prices in here too. A system dispatching on a single
bad quarter would pay for about three visits per real fault instead of one, so
waiting the extra quarter is worth roughly 2R per fault avoided. That is the
persistence rule's justification stated as money rather than as judgement.

### It works as far ahead as you ask, which is not a compliment

Predicting four quarters out ought to be harder than predicting one. It is not.

| quarters ahead | quarters scored | events | AP | baseline | margin | recall@15% |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 13 | 43 | 0.489 | 0.443 | +0.046 | 0.814 |
| 2 | 11 | 35 | 0.450 | 0.470 | -0.019 | 0.763 |
| 3 | 12 | 35 | 0.440 | 0.373 | +0.068 | 0.723 |
| 4 | 13 | 39 | 0.415 | 0.310 | +0.105 | 0.668 |

Average precision falls from 0.489 to 0.415 across a year, a loss of 15%, while
the baseline falls from 0.443 to 0.310, a loss of 30%. The margin grows with
distance rather than shrinking.

A model detecting a fault as it develops would decay sharply, because the
evidence would not exist yet. Losing 15% of its score over a year is not that. It is recognising a standing condition: a region
sitting well above its own long-run level will come back down, and that is
visible a year before it happens because it is already true.

So this is a triage tool, not an early warning. It says which regions carry the
problem and never when the problem will arrive. A team can pick a horizon to
suit how far ahead it plans, since they are all about equally reliable, but a
four-quarter prediction is not a timetable and should not be presented as one.

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

The label costs time in deployment as well as in evaluation. A lasting decline
is only confirmed two quarters after the quarter that predicts it, so a ranking
issued for 2026 Q2 cannot be scored until 2026 Q4 data is published, and the
model is always trained on outcomes at least two quarters old. That is the
price of not dispatching on noise: two thirds of single-quarter falls undo
themselves, so a label that waited less would mostly be labelling recoveries.

The ranking is a priority order for inspection, not a decision. A crew confirms
or dismisses what it finds, and those outcomes are the only labels that
describe real faults rather than movements in a crowdsourced median.

## What the declines are

### It predicts falls, not movement

Everything here is framed around falls, and nothing had tested whether that
framing does any work. A model that ranks regions by how far they sit above
their own long-run level should also, by construction, be good at spotting
regions about to move sharply in either direction. If it predicts rises as well
as falls, it is a volatility detector with a sign written on it and the
maintenance story is wrong.

The same data relabelled three ways, refit each time, purged each time. Average
precision is not comparable across rows because the base rates differ, so the
column that matters is lift over a random ranking:

| target | train events | test events | base rate | AP | lift | recall@15% |
| --- | --- | --- | --- | --- | --- | --- |
| **lasting fall** | 26 | 17 | 0.024 | 0.436 | **18.5x** | 0.765 |
| lasting rise | 261 | 43 | 0.060 | 0.314 | 5.3x | 0.633 |
| lasting move, either way | 295 | 61 | 0.085 | 0.324 | 3.8x | 0.543 |

Falls are 3.5 times as findable as rises relative to how common each is, with
ten times fewer examples to learn from. The framing is doing real work.

One fact falls out of this and deserves stating on its own: the network mostly
improves. The test years hold 43 lasting rises against 17 lasting falls. A
maintenance tool is looking for the exception rather than the trend, and a
reader who assumes mobile service in New South Wales is broadly deteriorating
would be reading this project backwards.

### The declines are whole-link degradations, not measurement artefacts or congestion

Everything above predicts these events without ever checking what they are. A
fall in a crowdsourced download median could be a degraded cell, or the same
cell measured by different people on different plans and handsets, and only one
of those is worth sending a crew to.

Upload and latency separate the two. A cell in trouble degrades the whole link;
a change in who is testing moves download alone.

| median change in the quarter after | declines | everything else |
| --- | --- | --- |
| download speed | -38.0% | +3.7% |
| upload speed | **-34.9%** | +0.6% |
| latency (up is worse) | **+10.1%** | -0.1% |
| speed tests run | -17.0% | -0.8% |
| devices seen | -5.1% | -1.6% |

| how often the quarter looked like this | declines | everything else |
| --- | --- | --- |
| upload fell as well | **86%** | 31% |
| latency got worse | 51% | 26% |
| both, a whole-link fault | **47%** | 11% |
| devices grew, congestion | 30% | 30% |
| devices fell, users left | 44% | 32% |
| testing halved | **25%** | 4% |

Download and upload fall by almost the same proportion and latency rises with
them. These are whole-link degradations, not an artefact of which handsets
turned up, and the ranking is pointing at something real.

Congestion is not the mechanism, which is worth saying because it is the
intuitive one and the one an extension to census population growth would
assume. Device counts grow in 30% of declines and 30% of everything else. If
anything users leave rather than arrive, which is what a cell people have given
up on would look like.

One row argues against the project. In a quarter of these events the number of
speed tests halves, against 4% elsewhere. That is either a consequence of a bad
cell or part of the reason it was recorded as bad, and this data cannot
separate the two. Shrinking by test count limits the damage without ending the
argument, and it is the strongest remaining reason to treat the output as a
list of places to look rather than a list of faults.

### Most falls undo themselves, and the ones that do not are permanent

Everything else here predicts who will fall. What happens afterwards was never
asked, and it changes the operational advice more than any model comparison
does. Following all 210 falls of at least 20% forward:

| quarters later | still observed | still down 20% | share |
| --- | --- | --- | --- |
| 1 | 210 | 210 | 100% |
| 2 | 177 | 57 | **32%** |
| 3 | 161 | 49 | 30% |
| 4 | 152 | 52 | 34% |
| 5 | 150 | 44 | 29% |
| 6 | 138 | 41 | 30% |

**68% of falls undo themselves within two quarters.** Dispatching on a single
bad quarter would waste two visits in three, which is the measured
justification for the persistence rule that had until now only been argued for
on operational grounds.

**After two quarters the curve stops moving.** The share still down is 32%,
30%, 34%, 29%, 30% at two through six quarters out. The two-quarter test is
close to a perfect sieve: what survives it is permanent as far as this data
reaches, and waiting longer buys nothing but delay.

**A fifth of the affected regions produce two fifths of the falls.**

| | regions |
| --- | --- |
| fell once | 70 |
| fell twice | 30 |
| fell three or more times | **23** (one of them five times) |

Those 23 regions account for 80 of the 210 falls, 38%. They are a standing
problem rather than an event, and sending a crew to the same place five times
is the wrong response. A deployed system should separate them out: inspect the
one-off falls, and put the repeat offenders on a list for capacity planning
instead.

### Which falls will undo themselves is predictable, and here the forest wins

Two thirds of falls recover within a quarter, so the question a dispatcher
actually has at the moment a fall is first seen is not whether it happened but
whether it will stay. Every fall becomes a row, described as it looked the
quarter it was first seen and labelled by whether the region was back within 20%
of its pre-fall level a quarter later. Scored year by year, purged as everywhere
else:

| year | falls | recovered | AP forest | AP rule | top third, forest | top third, rule |
| --- | --- | --- | --- | --- | --- | --- |
| 2022 | 39 | 64% | **0.82** | 0.77 | 85% | 85% |
| 2023 | 21 | 48% | **0.75** | 0.67 | **86%** | 71% |
| 2024 | 21 | 52% | **0.75** | 0.73 | 71% | 71% |
| 2025 | 15 | 53% | **0.88** | 0.79 | **100%** | 80% |

Weighted over 96 falls the forest reaches 0.800 against 0.743 for the obvious
rule, that small falls recover, and 0.562 for guessing. It is ahead of the rule
in all four years. Predicting falls, it never once managed that against mean
reversion.

That asymmetry is the finding. Whether a region falls is mostly one number, how
far it sits above its own long-run level, so a one-parameter rule is enough.
Whether it recovers depends on several things at once: how far it fell, how
volatile it has been, latency, the two quarters before. That is the shape of
problem a tree ensemble is for, and the only place in this project where the
extra model clearly pays for itself.

Operationally it is the other half of the inspection list: the falls a crew
should not be sent to. Of the third the forest is most confident will recover,
84% do. Every year's test set is small, 15 to 39 falls, so the top-third
comparison moves by whole regions; the average-precision result is the steadier
of the two.

### Declines do not cluster in space

If a lasting decline were a shared fault, neighbouring regions should sometimes
fall together: cells lean on the same backhaul, the same power, the same
upgrade programme. A permutation test asks whether they do. Within each
quarter, measure how far each declining region sits from the nearest other
declining region, then shuffle which regions declined, keeping the count per
quarter fixed, and measure again.

| | km to the nearest other decline |
| --- | --- |
| observed | 158.9 |
| shuffled, mean | 179.3 |
| shuffled, 5th percentile | 119.0 |
| proportion of shuffles closer than observed | 0.332 |

Declines are no closer together than chance. This agrees with the earlier
result that neighbour features added nothing, 0.380 to 0.384 against a seed
spread of 0.005, and the two together are the same finding reached twice.

Each decline has to stand on its own evidence. A neighbour falling in the same
quarter is not, on this data, a reason to believe a region more. The caveat is
scale: these are 8 km cells and the median decline is 159 km from the next one,
so an effect operating at the scale of a single tower would not be visible
here. What can be ruled out is region-wide shared causes, not local ones.

## What does not help

### Census population growth does not help either

A teammate joined ABS population to the panel and tested whether a region's
annual growth rate improves the ranking. It does not. Their numbers, on
scikit-learn 1.9.1, ten seeds, under the purged protocol:

| features | average precision | recall@15% |
| --- | --- | --- |
| devices baseline | 0.4833 ± 0.0106 | 0.7647 |
| plus population growth | 0.4817 ± 0.0100 | 0.7647 |
| availability control | 0.4827 ± 0.0133 | 0.7647 |

Growth moves average precision by -0.0016 against a seed spread of ±0.010, and
recall inside the budget not at all. The availability control is the careful
part: it adds only an indicator for whether population was observed, so a gain
from the growth column could not be mistaken for a gain from knowing which
regions have ABS coverage. Neither column does anything.

This agrees with a result measured here earlier from the other direction.
Congestion is the mechanism population growth would have to work through, and
device counts grow in 30% of lasting declines and in 30% of everything else.
Two independent tests of the same mechanism, both null.

Their work is in `experiments/population_growth/`, with ABS source
provenance, input hashes, pinned requirements for both scikit-learn versions
and per-seed results. It also carries the quadkey-to-SA2 intersection this
repository had listed as outstanding: region centroids against ASGS 2021 SA2
polygons, with each quarter using only the ABS vintages published by then.

Their write-up notes one thing it could not settle, that the purge removed
training rows as well as leaking ones, so the drop could not be attributed
entirely to leakage. The matched-size control above answers it: removing 234
rows at random costs 0.015 and removing the leaking 234 costs 0.115.

### Congestion proxies already in the data move the number slightly

Ookla reports distinct devices per tile alongside the test count, and neither
had been used. Their ratio is the interesting one: a region running many tests
per device is one where people keep re-testing a connection that is not
satisfying them.

| features | average precision | recall@15% |
| --- | --- | --- |
| current | 0.436 ± 0.014 | 0.765 ± 0.000 |
| plus demand proxies | **0.493** ± 0.010 | 0.765 ± 0.000 |

The gain is about four times the seed noise on average precision and nothing at
all inside the inspection budget, which is the pattern every feature in this
project has shown. The point of recording it is
that 0.493 is the figure external population data has to beat, not 0.436.
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

## Who the system serves

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
budget, 81% of inspections go to urban regions and 19% to outer suburban ones.

The ranking should therefore be presented as covering urban and outer-suburban
New South Wales only, with regional areas handled by scheduled inspection
rather than by this model. Stating the coverage is not a disclaimer; a ranking
that silently omits a third of the state would misdirect the budget it exists
to allocate.

### The unfairness follows geography, not income

Regional New South Wales is dropped before the model runs. The obvious next
worry is that this is the same as dropping poor areas, and Lee et al. found
crowdsourced speed-test samples skewed by income, education and age. ABS
publishes the Index of Relative Socio-economic Disadvantage (IRSD) for every
SA2, so the question can be asked directly. Regions are matched by the rule the
population experiment used: the centre falls in exactly one SA2, no nearest-area
substitution. 397 of 455 regions match.

| IRSD quintile | lasting-decline rate | share of rows | share of a 15% budget |
| --- | --- | --- | --- |
| 1 most disadvantaged | 1.5% | 18% | 20% |
| 2 | 1.8% | 23% | 23% |
| 3 | 1.6% | 27% | 26% |
| 4 | 1.1% | 15% | 20% |
| 5 least disadvantaged | **2.7%** | 17% | 11% |

Declines do not concentrate in disadvantaged areas; the least disadvantaged
quintile has the highest rate. The budget reaches the most disadvantaged
quintile slightly more than its share. And the regional band the model drops
has a median IRSD decile of 5, the middle of the distribution.

One pattern had to be taken apart before it could be reported. The panel seems
to reach the most advantaged SA2s least often, 22% of them against 38% of the
most disadvantaged, which would reverse the published bias. It is geometry.
Inner-city SA2s are small and an 8 km tile centre lands in one at a time:

| SA2 size band | advantaged reached | disadvantaged reached |
| --- | --- | --- |
| smallest | 0.05 | 0.04 |
| small | 0.11 | 0.03 |
| mid | 0.19 | 0.21 |
| large | 0.68 | 0.73 |
| largest | 0.94 | 0.79 |

Reach rises from 5% to over 80% with size and does not follow income within any
band. Reporting the raw 22% against 38% would have been reporting the shape of
inner Sydney.

So the system's equity problem is geographic rather than socio-economic. It
fails people in low-usage rural areas and does not, on this evidence, fail
people for being poor. That is a narrower claim than the one an ethics section
would usually reach for, and it is the one the data supports. IRSD describes
residents rather than the commuters and visitors who also run tests, and 58
regions match no SA2, so it is evidence about the regions the model sees.

## Earlier framing

These sections predicted a fall in the very next quarter, before the speeds
were shrunk, the label required the fall to last, the panel was clipped to New
South Wales, and training rows were purged. Their numbers are not comparable
with the sections above and are not current results. They are kept because
they are where each later change came from.

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

### Predicting the current quarter is not a task

A first version scored perfect accuracy, which was the bug announcing itself.
The label is derived from `pct_change`, and `pct_change` was also a feature,
so the model was reading the answer rather than predicting it.

The target is now the **following** quarter's decline, and performance fell to
the numbers above. This is worth recording because the proposal did not
distinguish between describing a decline that has already happened and
forecasting one that has not.

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

## Reproducing the figures

Every measured number in this README is asserted by `src/verify_claims.py`,
which re-derives it and fails if it has moved:

```bash
python src/verify_claims.py --panel data/panel_nsw.csv
```

It takes a few minutes. Running it caught the first discrepancy this README had:
`walkforward.py` defaulted to a start year the documented command did not use,
so running it bare reported a different rolling-origin recall from the one in
this file. Neither number was wrong, and anyone reproducing the work would have
concluded otherwise. The default now matches the documentation.

Two more came from a teammate reproducing the figures on their own machine,
and both are recorded here because finding them was the useful part.

**The library versions are not interchangeable.** They measured 0.630 where
this repository reported 0.598, and the difference was scikit-learn alone:
1.9.1 gave 0.630, 1.6.1 gave 0.598. With seventeen declines in the test years,
a change in how a forest breaks ties moves average precision further than any
feature in this project does. Seeding the model does not protect against that,
so `requirements.txt` now pins every version and says why.

**The training set was leaking.** See the next section; it cost a fifth of the
headline figure.

The one thing a fresh clone cannot do is start from nothing. `data/*.csv` is
not in the repository, so the panel has to be rebuilt first:

```bash
python src/build_panel.py                      # reads Ookla's public bucket
python src/boundary.py --panel data/panel.csv  # writes data/panel_nsw.csv
```

That first command queries 29 quarterly parquet files of roughly 175 MB each
and takes hours. The state boundaries it needs are committed, so nothing else
has to be downloaded by hand. Keeping the panel out of the repository is
deliberate — it is derived data under a share-alike licence, and committing a
40 MB CSV to make a report reproducible trades one problem for another — but it
does mean reproduction starts with a long wait rather than a clone.
